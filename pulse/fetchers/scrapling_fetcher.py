"""
pulse/fetchers/scrapling_fetcher.py — 统一采集适配器

Harness 抽象: Fetcher v2 的可选后端, Pipeline 零改动.
  - VPS:   mode="httpx" 或 "auto" → NetworkFetcher (CircuitBreaker + DLQ)
  - Mac:   mode="cdp" → Brave CDP + capture_xhr (过 BOSS 反爬)
  - Cloud: mode="stealth" → Scrapling StealthyFetcher (Cloudflare bypass)

用法:
  # Mac 上 BOSS 直聘 (推荐)
  adapter = ScraplingAdapter(mode='cdp')
  result = adapter.fetch('https://...', capture_xhr='search/joblist.json')
  for xhr in adapter.captured_xhr:
      print(xhr.json())

  # VPS 上
  adapter = ScraplingAdapter(mode='httpx')
  result = adapter.fetch('https://...')
"""
import json
import logging
import os
import subprocess
import time
from pathlib import Path

from pulse.fetcher import FetchResult

logger = logging.getLogger("pulse.fetcher.scrapling")

# ── Scrapling StealthyFetcher 可选 ───────────────────────────────────
try:
    from scrapling.fetchers import StealthyFetcher

    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False
    logger.info("Scrapling not installed, falling back to httpx")

# ── Brave / Chrome 路径 ──────────────────────────────────────────────
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9222


def _find_browser() -> str | None:
    for p in [BRAVE_PATH, CHROME_PATH]:
        if os.path.exists(p):
            return p
    return None


def _is_process_running(name: str) -> bool:
    try:
        return bool(
            subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
        )
    except Exception:
        return False


# ── ScraplingAdapter ─────────────────────────────────────────────────


class ScraplingAdapter:
    """统一采集适配器 — 三种后端, 同一接口

    mode:
      "auto"    — 有 Scrapling → stealth, 否则 httpx
      "httpx"   — NetworkFetcher (CircuitBreaker + DLQ)
      "stealth" — StealthyFetcher (Cloudflare bypass)
      "cdp"     — Brave/Chrome CDP (反爬最严的站)
    """

    def __init__(
        self,
        mode: str = "auto",
        cdp_url: str | None = None,
        brave_path: str | None = None,
    ):
        self.mode = mode
        self._available = SCRAPLING_AVAILABLE
        self._cdp_url = cdp_url or f"http://127.0.0.1:{CDP_PORT}"
        self._brave_path = brave_path or _find_browser()
        # 每次 fetch 后保留捕获的 XHR
        self.captured_xhr: list[dict] = []
        # CDP 进程管理
        self._browser_proc: subprocess.Popen | None = None

    # ── 公共接口 ───────────────────────────────────────────────────────

    def fetch(
        self,
        url: str,
        timeout: int = 30,
        capture_xhr: str | None = None,
    ) -> FetchResult:
        """统一采集入口

        Args:
            url: 目标 URL
            timeout: 超时秒数
            capture_xhr: CDP 模式下捕获匹配该模式的 XHR 响应
        """
        self.captured_xhr = []
        t0 = time.time()
        method = self.mode

        if method == "auto":
            method = "stealth" if self._available else "httpx"

        try:
            if method == "httpx":
                return self._fetch_httpx(url, timeout)
            elif method == "stealth":
                if self._available:
                    return self._fetch_stealth(url, timeout)
                logger.warning("Stealth not available, falling back to httpx")
                return self._fetch_httpx(url, timeout)
            elif method == "cdp":
                return self._fetch_cdp(url, timeout, capture_xhr)
            else:
                return self._fetch_httpx(url, timeout)
        except Exception as e:
            logger.warning("Scrapling fetch failed (%s): %s", method, e)
            return FetchResult(
                success=False,
                url=url,
                error_type="SCRAPLING_ERROR",
                error_message=str(e),
                latency_ms=(time.time() - t0) * 1000,
            )

    def fetch_json(
        self, url: str, timeout: int = 30
    ) -> dict | list | None:
        """便捷方法: 直接获取 JSON 响应"""
        result = self.fetch(url, timeout)
        if result.success and result.html:
            try:
                return json.loads(result.html)
            except json.JSONDecodeError:
                pass
        return None

    @property
    def can_run_stealth(self) -> bool:
        return self._available

    # ── 上下文管理 ─────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """清理 CDP 浏览器进程"""
        if self._browser_proc:
            try:
                self._browser_proc.terminate()
                self._browser_proc.wait(timeout=5)
            except Exception:
                try:
                    self._browser_proc.kill()
                except Exception:
                    pass
            self._browser_proc = None

    # ── httpx 后端 ─────────────────────────────────────────────────────

    def _fetch_httpx(self, url: str, timeout: int) -> FetchResult:
        from pulse.fetcher import NetworkFetcher as HttpxFetcher

        f = HttpxFetcher(max_retries=2)
        return f.fetch(url, timeout=timeout)

    # ── StealthyFetcher 后端 ───────────────────────────────────────────

    def _fetch_stealth(self, url: str, timeout: int) -> FetchResult:
        t0 = time.time()
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            solve_cloudflare=True,
            timeout=timeout,
        )
        return FetchResult(
            success=page.status < 400,
            url=url,
            status_code=page.status,
            html=str(page.text) if hasattr(page, "text") else "",
            error_type="" if page.status < 400 else "HTTP_ERROR",
            latency_ms=(time.time() - t0) * 1000,
        )

    # ── CDP 后端 (Brave/Chrome + Playwright) ──────────────────────────
    _cdp_context = None
    _cdp_page = None

    def _ensure_browser(self):
        """启动 Brave 实例 (用真实用户数据目录的复制)
        
        Playwright + Brave CDP 不兼容 (Browser.setDownloadBehavior).
        改用 launch_persistent_context + 复制的用户数据目录.
        """
        if self._cdp_context is not None:
            return  # 已有会话
        
        if not self._brave_path:
            raise FileNotFoundError("未找到 Brave 或 Chrome, CDP 模式不可用")

        # 关掉已有 Brave 进程
        if _is_process_running("Brave Browser") or _is_process_running("Google Chrome"):
            name = "Brave Browser" if _is_process_running("Brave Browser") else "Google Chrome"
            logger.info("关闭 %s...", name)
            subprocess.run(
                ["osascript", "-e", f'tell application "{name}" to quit'],
                timeout=5,
            )
            time.sleep(2)

        # 复制用户数据目录 (避免锁冲突)
        import shutil
        src_dir = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
        tmp_dir = Path("/tmp/boss_profile_copy")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        # 复制关键的认证和存储数据
        _copied = 0
        for sub in [
            "Default/Cookies", "Default/Cookies-journal",
            "Default/Local Storage", "Default/Session Storage",
            "Default/IndexedDB",
            "Default/Service Worker/CacheStorage",
        ]:
            s = src_dir / sub
            d = tmp_dir / sub
            if s.exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                if s.is_file():
                    shutil.copy2(s, d)
                    _copied += 1
                else:
                    shutil.copytree(s, d, dirs_exist_ok=True)
                    _copied += 1
        logger.info("用户数据已复制 (%d 项) → %s", _copied, tmp_dir)

        from playwright.sync_api import sync_playwright

        self._pw_mgr = sync_playwright()
        self._pw = self._pw_mgr.__enter__()
        context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(tmp_dir),
            headless=False,
            executable_path=self._brave_path,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        # 注入反检测 JS
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
        """)

        self._cdp_context = context
        self._cdp_page = page
        logger.info("CDP 会话已建立")

    def _get_bst_cookie(self) -> str:
        """从已加载的 cookies 中提取 bst (用作 zp_token header)"""
        if not self._cdp_context:
            return ""
        cookies = self._cdp_context.cookies()
        for c in cookies:
            if c.get("name") == "bst":
                return c.get("value", "")
        return ""

    def _fetch_cdp(
        self,
        url: str,
        timeout: int,
        capture_xhr: str | None = None,
    ) -> FetchResult:
        """通过 launch_persistent_context 用真实浏览器采集"""
        self._ensure_browser()
        t0 = time.time()
        html_content = ""

        page = self._cdp_page
        logger.info("CDP fetch: %s, capture_xhr=%s", url[:60], capture_xhr)

        # 设置 zp_token header (BOSS 反爬需要)
        try:
            cookies = self._cdp_context.cookies()
            bst = next((c["value"] for c in cookies if c["name"] == "bst"), "")
            if bst:
                page.set_extra_http_headers({
                    "zp_token": bst,
                    "x-requested-with": "XMLHttpRequest",
                })
        except Exception:
            pass

        # 注册 XHR 捕获
        self.captured_xhr = []
        if capture_xhr:
            def _on_response(response):
                if capture_xhr in response.url:
                    try:
                        body = response.body()
                        self.captured_xhr.append({
                            "url": response.url,
                            "status": response.status,
                            "body": body.decode("utf-8", errors="replace"),
                        })
                    except Exception:
                        pass  # 第一条 body 会被 Playwright 内部消费, 后续可用
            page.on("response", _on_response)

        # 导航 (等待网络空闲确保 SPA 完全渲染)
        page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
        page.wait_for_timeout(3000)

        # 取页面 HTML
        try:
            html_content = page.content()
        except Exception:
            pass

        return FetchResult(
            success=True,
            url=url,
            status_code=200,
            html=html_content,
            latency_ms=(time.time() - t0) * 1000,
        )

    def close_cdp(self):
        """关闭 CDP 会话"""
        if self._cdp_context:
            try:
                self._cdp_context.close()
            except Exception:
                pass
            self._cdp_context = None
            self._cdp_page = None
        if hasattr(self, "_pw_mgr") and self._pw_mgr:
            try:
                self._pw_mgr.__exit__(None, None, None)
            except Exception:
                pass
            self._pw_mgr = None
            self._pw = None
