"""
pulse/fetcher.py — 工业级网络抓取层

特性:
  - 指数退避 + 抖动 (Exponential Backoff + Jitter)
  - HTTP 429/5xx 优雅降级 → DLQ
  - 代理轮换接口
  - 零阻断: 任何异常不抛至上層, 返回 FetchResult
"""
import time
import random
import logging
from dataclasses import dataclass
from typing import Optional, Callable
from urllib.parse import urlparse

logger = logging.getLogger("pulse.fetcher")


@dataclass
class FetchResult:
    """抓取结果 — 成功或失败, 从不抛出异常"""
    url: str
    success: bool
    status_code: int = 0
    html: str = ""
    error_type: str = ""
    error_message: str = ""
    latency_ms: float = 0.0


class NetworkFetcher:
    """带 DLQ 容错的网络抓取器"""

    def __init__(self, proxies: list[str] | None = None,
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 dlq_callback: Optional[Callable] = None):
        self.proxies = proxies or []
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.dlq_callback = dlq_callback
        self._proxy_index = 0
        self._session = None

    def _get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_index % len(self.proxies)]
        self._proxy_index += 1
        return proxy

    def _backoff_delay(self, attempt: int):
        """指数退避 + 随机抖动"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, delay * 0.5)
        total = delay + jitter
        logger.debug(f"Backoff: attempt={attempt}, delay={total:.1f}s")
        time.sleep(total)

    def fetch(self, url: str, timeout: int = 30) -> FetchResult:
        """抓取单条 URL，永不抛出异常"""
        t0 = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                import httpx
                # 构建请求
                kwargs = {"timeout": timeout, "follow_redirects": True}
                proxy = self._get_proxy()
                if proxy:
                    kwargs["proxies"] = {"all://": proxy}

                resp = httpx.get(url, **kwargs)
                latency = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    return FetchResult(
                        url=url, success=True, status_code=200,
                        html=resp.text, latency_ms=latency
                    )

                # HTTP 429/5xx → 重试, 但不记录 DLQ (只有最终失败才记录)
                if resp.status_code in (429, 502, 503, 504):
                    logger.warning(f"HTTP {resp.status_code} for {url}, attempt {attempt+1}")
                    if attempt < self.max_retries:
                        self._backoff_delay(attempt)
                        continue
                    # 超过重试次数 → 真正失败, 写入 DLQ
                    self._report_dlq(url, f"HTTP_{resp.status_code}", str(resp.status_code), resp.status_code)
                    return FetchResult(
                        url=url, success=False, status_code=resp.status_code,
                        error_type=f"HTTP_{resp.status_code}",
                        error_message=f"Exceeded {self.max_retries} retries",
                        latency_ms=latency
                    )

                # 其他 4xx → 不重试, 直接 DLQ
                self._report_dlq(url, f"HTTP_{resp.status_code}", resp.text[:500], resp.status_code)
                return FetchResult(
                    url=url, success=False, status_code=resp.status_code,
                    error_type=f"HTTP_{resp.status_code}",
                    error_message=resp.text[:200], latency_ms=latency
                )

            except httpx.TimeoutException:
                logger.warning(f"Timeout for {url}, attempt {attempt+1}")
                if attempt < self.max_retries:
                    self._backoff_delay(attempt)
                    continue
                # 最终超时, 写入 DLQ
                self._report_dlq(url, "TIMEOUT", f"timeout={timeout}s")
                return FetchResult(url=url, success=False, error_type="TIMEOUT",
                                   error_message=f"timeout={timeout}s", latency_ms=(time.time()-t0)*1000)

            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                if attempt < self.max_retries:
                    self._backoff_delay(attempt)
                    continue
                # 最终异常, 写入 DLQ
                self._report_dlq(url, "UNEXPECTED", str(e)[:500])
                return FetchResult(url=url, success=False, error_type="UNEXPECTED",
                                   error_message=str(e)[:200], latency_ms=(time.time()-t0)*1000)
        return FetchResult(url=url, success=False, error_type="UNKNOWN")

    def _report_dlq(self, url: str, error_type: str, message: str,
                    http_status: Optional[int] = None):
        if self.dlq_callback:
            try:
                self.dlq_callback(url, error_type, message, http_status)
            except Exception as e:
                logger.error(f"DLQ callback failed: {e}")

    def fetch_batch(self, urls: list[str], concurrency: int = 5,
                    timeout: int = 30) -> list[FetchResult]:
        """批量抓取，带并发限制"""
        results = []
        for i in range(0, len(urls), concurrency):
            batch = urls[i:i + concurrency]
            for url in batch:
                results.append(self.fetch(url, timeout))
            if i + concurrency < len(urls):
                time.sleep(random.uniform(0.5, 1.5))  # 批次间隔
        return results
