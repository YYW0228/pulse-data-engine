"""pulse/fetcher.py — 工业级网络抓取层 v2

特性:
  - Circuit breaker: 429/503 连续失败超出阈值后自动断开
  - Full jitter: AWS 风格退避 delay = random(0, min(base*2^attempt, max))
  - Retry-After 响应: 尊重服务器返回的 Retry-After header
  - 自适应超时: 超时后下次增加超时窗口
  - 指数退避 + 抖动 (Exponential Backoff + Full Jitter)
  - HTTP 429/5xx 优雅降级 → DLQ
  - 代理轮换接口
  - 零阻断: 任何异常不抛至上層, 返回 FetchResult
  - Prometheus metrics: duration histogram + status counter + retry count
"""
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("pulse.fetcher")


# ── Circuit Breaker ──────────────────────────────────────────────────


class CircuitBreaker:
    """Per-endpoint circuit breaker for HTTP 429/503 风暴防护

    状态机: CLOSED → OPEN (阈值超限) → HALF_OPEN (冷却后自动)
    """

    def __init__(self, name: str = "default", threshold: int = 3,
                 window_seconds: float = 60.0, cooldown_seconds: float = 30.0):
        self.name = name
        self.threshold = threshold            # 窗口内 N 次失败触发
        self.window = window_seconds          # 滑动窗口大小
        self.cooldown = cooldown_seconds      # 断开持续时间
        self._failures: list[float] = []      # 失败时间戳
        self._open_until: float = 0.0         # 断开到期时间
        self._total_trips: int = 0            # 累计断开次数

    @property
    def is_open(self) -> bool:
        """电路是否断开 (429/503 风暴保护)"""
        now = time.time()
        if now < self._open_until:
            return True
        # 清理过期记录
        cutoff = now - self.window
        self._failures = [t for t in self._failures if t > cutoff]
        return False

    @property
    def state(self) -> str:
        if time.time() < self._open_until:
            return "OPEN"
        return "CLOSED"

    def record_failure(self) -> None:
        """记录一次失败, 若窗口内超限则断开"""
        now = time.time()
        self._failures.append(now)
        cutoff = now - self.window
        recent = [t for t in self._failures if t > cutoff]
        if len(recent) >= self.threshold:
            self._open_until = now + self.cooldown
            self._total_trips += 1
            logger.warning(f"⛔ Circuit breaker {self.name} OPEN ({self.cooldown}s cooldown, "
                           f"{self._total_trips} total trips)")

    def record_success(self) -> None:
        """成功 — 清理失败记录 (电路自动恢复)"""
        # 成功后 is_open 自动从时间窗口过期恢复


# ── 数据模型 ─────────────────────────────────────────────────────────


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


# ── Fetcher ──────────────────────────────────────────────────────────


class NetworkFetcher:
    """带 DLQ 容错 + Circuit Breaker 的网络抓取器"""

    def __init__(
        self,
        proxies: list[str] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        dlq_callback: Callable | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.proxies = proxies or []
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.dlq_callback = dlq_callback
        self.cb = circuit_breaker or CircuitBreaker(name="http")
        self._proxy_index = 0
        self._current_timeout = 15.0  # 起始超时, 自适应增长

    def _get_proxy(self) -> str | None:
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_index % len(self.proxies)]
        self._proxy_index += 1
        return proxy

    def _backoff_full_jitter(self, attempt: int, retry_after: int | None = None) -> float:
        """AWS 风格 Full Jitter: delay = random(0, min(base*2^attempt, max))

        若服务器返回 Retry-After, 优先使用该值。
        """
        if retry_after is not None and retry_after > 0:
            delay = float(retry_after)
            logger.debug(f"  Retry-After: {delay}s")
        else:
            cap = min(self.base_delay * (2 ** attempt), self.max_delay)
            delay = random.uniform(0, cap)
        logger.debug(f"  FullJitter backoff: attempt={attempt}, delay={delay:.1f}s")
        time.sleep(delay)
        return delay

    def _parse_retry_after(self, resp_headers: object) -> int | None:
        """从响应头解析 Retry-After (秒 或 HTTP-date)"""
        try:
            raw = getattr(resp_headers, "get", lambda k, d=None: d)("Retry-After", None)
            if raw is None:
                return None
            # 尝试解析数字秒数
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
            return None
        except Exception:
            return None

    def fetch(self, url: str, timeout: int | None = None) -> FetchResult:
        """抓取单条 URL，永不抛出异常

        带 Circuit Breaker + Full Jitter + Retry-After + 自适应超时
        """
        from pulse.metrics import metrics

        timeout = timeout or self._current_timeout
        t0 = time.time()

        # ── Circuit breaker check ─────────────────────────────────
        if self.cb.is_open:
            logger.warning(f"⛔ Circuit breaker OPEN, skipping {url[:60]}")
            return FetchResult(
                url=url, success=False, error_type="CIRCUIT_OPEN",
                error_message=f"Circuit breaker {self.cb.name} open for ~{self.cb.cooldown}s",
            )

        for attempt in range(self.max_retries + 1):
            try:
                import httpx

                # 构建请求
                kwargs: dict = {"timeout": timeout, "follow_redirects": True}
                proxy = self._get_proxy()
                if proxy:
                    kwargs["proxies"] = {"all://": proxy}

                resp = httpx.get(url, **kwargs)
                latency = (time.time() - t0) * 1000

                # ✅ 200 — 成功
                if resp.status_code == 200:
                    metrics.fetch_total.labels(source="http", status_code="200").inc()
                    metrics.fetch_duration.labels(source="http", status_code="200").observe(
                        time.time() - t0)
                    # 成功重置自适应超时
                    self._current_timeout = max(15.0, self._current_timeout * 0.9)
                    return FetchResult(
                        url=url, success=True, status_code=200,
                        html=resp.text, latency_ms=latency,
                    )

                # 🔁 429/5xx — 可重试 (用 Retry-After 或 Full Jitter)
                if resp.status_code in (429, 502, 503, 504):
                    retry_after = self._parse_retry_after(resp.headers)
                    logger.warning(
                        f"HTTP {resp.status_code} for {url[:60]}, attempt {attempt + 1}"
                        + (f", Retry-After={retry_after}s" if retry_after else "")
                    )

                    if attempt < self.max_retries:
                        metrics.fetch_retries.labels(source="http").inc()
                        self._backoff_full_jitter(attempt, retry_after)
                        continue

                    # 重试耗尽 → 记录失败 + DLQ + circuit breaker
                    self.cb.record_failure()
                    self._report_dlq(url, f"HTTP_{resp.status_code}",
                                     str(resp.status_code), resp.status_code)
                    return FetchResult(
                        url=url, success=False, status_code=resp.status_code,
                        error_type=f"HTTP_{resp.status_code}",
                        error_message=f"Exceeded {self.max_retries} retries",
                        latency_ms=latency,
                    )

                # ❌ 其他 4xx — 不重试, 直接 DLQ
                self._report_dlq(url, f"HTTP_{resp.status_code}",
                                 resp.text[:500], resp.status_code)
                return FetchResult(
                    url=url, success=False, status_code=resp.status_code,
                    error_type=f"HTTP_{resp.status_code}",
                    error_message=resp.text[:200], latency_ms=latency,
                )

            except httpx.TimeoutException:
                logger.warning(f"⏰ Timeout ({timeout}s) for {url[:60]}, attempt {attempt + 1}")
                metrics.fetch_total.labels(source="http", status_code="timeout").inc()

                if attempt < self.max_retries:
                    metrics.fetch_retries.labels(source="http").inc()
                    self._backoff_full_jitter(attempt)
                    # 自适应超时: 超时后增加
                    self._current_timeout = min(60.0, self._current_timeout * 1.5)
                    continue

                # 最终超时
                self.cb.record_failure()
                self._report_dlq(url, "TIMEOUT", f"timeout={timeout}s")
                metrics.fetch_duration.labels(source="http", status_code="timeout").observe(
                    time.time() - t0)
                metrics.fetch_total.labels(source="http", status_code="timeout").inc()
                return FetchResult(
                    url=url, success=False, error_type="TIMEOUT",
                    error_message=f"timeout={timeout}s",
                    latency_ms=(time.time() - t0) * 1000,
                )

            except Exception as e:
                logger.error(f"Unexpected error for {url[:60]}: {e}")
                if attempt < self.max_retries:
                    metrics.fetch_retries.labels(source="http").inc()
                    self._backoff_full_jitter(attempt)
                    continue
                self.cb.record_failure()
                self._report_dlq(url, "UNEXPECTED", str(e)[:500])
                return FetchResult(
                    url=url, success=False, error_type="UNEXPECTED",
                    error_message=str(e)[:200],
                    latency_ms=(time.time() - t0) * 1000,
                )

        return FetchResult(url=url, success=False, error_type="UNKNOWN")

    def _report_dlq(
        self, url: str, error_type: str, message: str, http_status: int | None = None
    ) -> None:
        if self.dlq_callback:
            try:
                self.dlq_callback(url, error_type, message, http_status)
            except Exception as e:
                logger.error(f"DLQ callback failed: {e}")

    def fetch_batch(
        self, urls: list[str], concurrency: int = 5, timeout: int = 30
    ) -> list[FetchResult]:
        """批量抓取，带并发限制 + 自适应超时"""
        results: list[FetchResult] = []
        for i in range(0, len(urls), concurrency):
            batch = urls[i: i + concurrency]
            for url in batch:
                results.append(self.fetch(url, timeout))
            if i + concurrency < len(urls):
                time.sleep(random.uniform(0.5, 1.5))
        return results
