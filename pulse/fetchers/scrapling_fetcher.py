"""
pulse/fetchers/scrapling_fetcher.py — Scrapling 适配器 (可选采集后端)

Harness 抽象: Fetcher v2 的可选后端, Pipeline 零改动.
  - VPS 上: 自动降级为 httpx
  - Mac 上: 可用 StealthyFetcher 解 Cloudflare/JS 渲染

用法:
  from pulse.fetchers.scrapling_fetcher import ScraplingFetcher
  
  # Mac 上 (有浏览器)
  fetcher = ScraplingFetcher(mode="stealth")
  result = fetcher.fetch("https://example.com")
  
  # VPS 上 (无浏览器, 自动降级)
  fetcher = ScraplingFetcher(mode="auto")
  result = fetcher.fetch("https://example.com")
"""

import logging
import time

from pulse.fetcher import FetchResult

logger = logging.getLogger("pulse.fetcher.scrapling")

try:
    from scrapling.fetchers import StealthyFetcher

    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False
    logger.info("Scrapling not installed, falling back to httpx")

# ── FetchResult 兼容 (Scrapling 版) ─────────────────────────────────

class ScraplingAdapter:
    """Scrapling 适配器 — 统一接口, 支持多模式"""

    def __init__(self, mode: str = "auto"):
        """
        mode:
          - "auto": 优先 StealthyFetcher, 不可用时降级 httpx
          - "httpx": 强制 httpx (VPS)
          - "stealth": 强制 StealthyFetcher (Mac)
          - "dynamic": 强制 DynamicFetcher (全浏览器)
        """
        self.mode = mode
        self._available = SCRAPLING_AVAILABLE

    def fetch(self, url: str, timeout: int = 30) -> FetchResult:
        t0 = time.time()
        method = self.mode

        # auto 模式: 有 Scrapling 就用 stealth, 不然 httpx
        if method == "auto":
            if self._available:
                method = "stealth"
            else:
                method = "httpx"

        try:
            if method == "httpx" or not self._available:
                return self._fetch_httpx(url, timeout)
            elif method == "stealth":
                return self._fetch_stealth(url, timeout)
            else:
                return self._fetch_httpx(url, timeout)
        except Exception as e:
            logger.warning(f"Scrapling fetch failed ({method}): {e}")
            return FetchResult(
                success=False,
                url=url,
                error_type="SCRAPLING_ERROR",
                error_message=str(e),
                latency_ms=(time.time() - t0) * 1000,
            )

    def _fetch_httpx(self, url: str, timeout: int) -> FetchResult:
        """降级回 httpx"""
        from pulse.fetcher import NetworkFetcher as HttpxFetcher

        f = HttpxFetcher(max_retries=2)
        return f.fetch(url, timeout=timeout)

    def _fetch_stealth(self, url: str, timeout: int) -> FetchResult:
        """StealthyFetcher + 自动降级"""
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

    def fetch_json(self, url: str, timeout: int = 30) -> dict | list | None:
        """获取 JSON API 响应"""
        import json

        result = self.fetch(url, timeout)
        if result.success and result.content:
            try:
                return json.loads(result.content)
            except json.JSONDecodeError:
                pass
        return None

    @property
    def can_run_stealth(self) -> bool:
        """检查当前环境能否跑 StealthyFetcher"""
        return self._available
