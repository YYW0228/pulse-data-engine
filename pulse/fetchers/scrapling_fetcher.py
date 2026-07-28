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

    # ── CDP 后端 (Raw WebSocket, 无 Playwright) ────────────────────────
    _cdp_ws = None
    _cdp_sid = None  # page session ID
    _cdp_target_id = None
    _cdp_brave_proc = None

    # XHR-in-page 模板 — 从 boss-zhipin-scraper 吞噬
    FETCH_API_JS = """(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__API_URL__', false);
    xhr.send();
    if (xhr.status !== 200) return JSON.stringify({error: xhr.status});
    var data = JSON.parse(xhr.responseText);
    var jobs = (data.zpData || {}).jobList || [];
    var results = jobs.map(function(j) {
        var s = j.salaryDesc || '';
        var sm = s.match(/(\\d+)(?:K|k)?\\s*[-~–至]\\s*(\\d+)(?:K|k)?/);
        var minK = sm ? parseInt(sm[1]) : null;
        var maxK = sm ? parseInt(sm[2]) : null;
        if (!sm) {
            var sv = s.match(/(\\d+)(?:K|k)/);
            if (sv) { minK = maxK = parseInt(sv[1]); }
        }
        if (minK > 1000) minK = Math.round(minK/1000);
        if (maxK > 1000) maxK = Math.round(maxK/1000);
        return {
            url: 'https://www.zhipin.com/job_detail/' + (j.encryptJobId || '') + '.html',
            job_title: j.jobName || '',
            company_name: j.brandName || '',
            city: j.cityName || '',
            salary_min_k: minK,
            salary_max_k: maxK,
            education: j.jobDegree || '',
            experience: j.jobExperience || '',
            keyword: '__KEYWORD__',
            source: 'boss',
            domain: 'zhipin.com',
        };
    });
    return JSON.stringify(results);
    })()"""

    BACKGROUND_VISIBILITY_JS = (
        "Object.defineProperty(document, 'hidden', {get: () => false});"
        "Object.defineProperty(document, 'visibilityState', {get: () => 'visible'});"
    )

    def _send_cdp(self, method: str, params: dict | None = None, sid: str | None = None) -> dict:
        """发送 CDP 命令并等待响应"""

        self._mid = getattr(self, "_mid", 0) + 1
        msg = {"id": self._mid, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        self._cdp_ws.send(json.dumps(msg))

        while True:
            raw = self._cdp_ws.recv()
            try:
                r = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if r.get("id") == self._mid:
                return r

    def _eval_js(self, js: str, sid: str) -> str | None:
        """在页面中执行 JS, 返回 result.value"""
        r = self._send_cdp("Runtime.evaluate", {
            "expression": js, "returnByValue": True,
        }, sid)
        return r.get("result", {}).get("result", {}).get("value")

    def _ensure_cdp(self):
        """启动 Brave + 建立 CDP WebSocket 连接"""
        if self._cdp_ws is not None:
            return  # 已有连接

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

        # 持久化 Chrome 数据目录
        profile_dir = Path.home() / ".pulse" / "boss_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # 启动 Brave (CDP 模式)
        logger.info("启动 Brave (CDP) ...")
        self._cdp_brave_proc = subprocess.Popen(
            [self._brave_path,
             f"--remote-debugging-port={CDP_PORT}",
             f"--user-data-dir={profile_dir}",
             "--remote-allow-origins=*",
             "--no-first-run",
             "--no-default-browser-check",
             ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 等 CDP 就绪
        import urllib.request
        for _ in range(30):
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3
                )
                ws_url = json.loads(resp.read())["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(1)
        else:
            raise TimeoutError("Brave CDP 启动超时")

        # 建立 WebSocket 连接
        import websocket
        self._cdp_ws = websocket.create_connection(ws_url, timeout=30)
        logger.info("CDP WebSocket 已连接")

        # 创建隐藏页面 target (不抢焦点)
        target = self._send_cdp("Target.createTarget", {
            "url": "about:blank", "background": True,
        })
        self._cdp_target_id = target["result"]["targetId"]
        attached = self._send_cdp("Target.attachToTarget", {
            "targetId": self._cdp_target_id, "flatten": True,
        })
        self._cdp_sid = attached["result"]["sessionId"]

        # 注册 visibility override (防止 BOSS 检测到后台 tab)
        self._send_cdp("Page.addScriptToEvaluateOnNewDocument", {
            "source": self.BACKGROUND_VISIBILITY_JS,
        }, self._cdp_sid)

        # 启用必要域
        self._send_cdp("Page.enable", sid=self._cdp_sid)
        self._send_cdp("Network.enable", sid=self._cdp_sid)

        # 注入 cookies (如果有保存的)
        state_path = Path(__file__).resolve().parent.parent.parent / "data" / "boss_storage_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                for c in state.get("cookies", []):
                    self._send_cdp("Network.setCookie", {
                        "name": c["name"], "value": c["value"],
                        "domain": c.get("domain", ".zhipin.com"),
                        "path": c.get("path", "/"),
                    }, self._cdp_sid)
                logger.info("已注入 %d cookies", len(state.get("cookies", [])))
            except Exception as e:
                logger.warning("Cookie 注入失败: %s", e)

        logger.info("CDP 会话已建立 (target=%s)", self._cdp_target_id[:12])

    def _cdp_navigate(self, url: str):
        """在 CDP page 中导航并等待渲染"""
        self._send_cdp("Page.navigate", {"url": url}, self._cdp_sid)
        time.sleep(6)  # 等 SPA 完全渲染

    def _fetch_cdp(
        self,
        url: str,
        timeout: int,
        capture_xhr: str | None = None,
    ) -> FetchResult:
        """Raw CDP WebSocket: 在页面内执行 XHR 获取 API 数据"""
        self._ensure_cdp()
        t0 = time.time()

        # 先导航到 BOSS (建立 SPA 上下文 + cookies)
        self._cdp_navigate("https://www.zhipin.com/web/geek/job?query=AI&city=100010000")

        # 构建 API URL
        keyword = ""
        city_code = "100010000"
        page_num = 1
        if "query=" in url:
            params = dict(qp.split("=") for qp in url.split("?")[1].split("&") if "=" in qp)
            keyword = params.get("query", "")
            city_code = params.get("city", "100010000")
            page_num = int(params.get("page", "1"))
        api_url = f"/wapi/zpgeek/search/joblist.json?query={keyword}&city={city_code}&page={page_num}"

        js = self.FETCH_API_JS.replace("__API_URL__", api_url).replace("__KEYWORD__", keyword)
        result_json = self._eval_js(js, self._cdp_sid)

        latency = (time.time() - t0) * 1000

        if not result_json:
            return FetchResult(
                success=False, url=url, error_type="CDP_EMPTY",
                error_message="XHR returned no data",
                latency_ms=latency,
            )

        try:
            jobs = json.loads(result_json)
        except json.JSONDecodeError as e:
            return FetchResult(
                success=False, url=url, error_type="CDP_JSON_ERROR",
                error_message=str(e),
                latency_ms=latency,
            )

        if isinstance(jobs, dict) and jobs.get("error"):
            return FetchResult(
                success=False, url=url, error_type="CDP_XHR_ERROR",
                error_message=str(jobs["error"]),
                latency_ms=latency,
            )

        # 保存原始 JSON 到 html 字段, 提取到 captured_xhr
        raw_body = json.dumps(jobs)
        self.captured_xhr = [{
            "url": url,
            "status": 200,
            "body": raw_body,
        }]

        return FetchResult(
            success=True,
            url=url,
            status_code=200,
            html=raw_body,
            latency_ms=latency,
        )

    def close_cdp(self):
        """关闭 CDP WebSocket 和 Brave 进程"""
        if self._cdp_ws:
            try:
                self._cdp_ws.close()
            except Exception:
                pass
            self._cdp_ws = None
        if self._cdp_brave_proc:
            try:
                self._cdp_brave_proc.terminate()
                self._cdp_brave_proc.wait(timeout=5)
            except Exception:
                try:
                    self._cdp_brave_proc.kill()
                except Exception:
                    pass
            self._cdp_brave_proc = None
        self._cdp_sid = None
        self._cdp_target_id = None
        logger.info("CDP 已关闭")
