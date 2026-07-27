"""Tests for pulse/fetcher.py — Circuit Breaker + NetworkFetcher"""
import time

import pytest

from pulse.fetcher import CircuitBreaker, FetchResult, NetworkFetcher


class TestCircuitBreaker:
    """Circuit Breaker 状态机"""

    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test", threshold=3, window_seconds=60, cooldown_seconds=30)
        assert cb.state == "CLOSED"
        assert not cb.is_open

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(name="test", threshold=3, window_seconds=60, cooldown_seconds=30)
        assert not cb.is_open
        cb.record_failure()
        assert not cb.is_open  # 1/3
        cb.record_failure()
        assert not cb.is_open  # 2/3
        cb.record_failure()
        assert cb.is_open  # 3/3
        assert cb.state == "OPEN"

    def test_recovers_after_cooldown(self):
        cb = CircuitBreaker(name="test", threshold=1, window_seconds=60, cooldown_seconds=0.1)
        cb.record_failure()
        assert cb.is_open
        time.sleep(0.15)
        assert not cb.is_open
        assert cb.state == "CLOSED"

    def test_failures_expire_after_window(self):
        cb = CircuitBreaker(name="test", threshold=2, window_seconds=0.1, cooldown_seconds=30)
        cb.record_failure()
        time.sleep(0.15)
        cb.record_failure()  # 第一个已过期, 仍 1/2
        assert not cb.is_open  # 不应触发


class TestNetworkFetcher:
    """NetworkFetcher 行为验证"""

    def test_fetch_returns_result_type(self):
        fetcher = NetworkFetcher(max_retries=0)
        result = fetcher.fetch("http://invalid.local", timeout=2)
        assert isinstance(result, FetchResult)
        assert not result.success  # 预期失败 (无法连接)

    def test_circuit_breaker_skips_on_open(self, monkeypatch):
        cb = CircuitBreaker(name="test", threshold=1, window_seconds=60, cooldown_seconds=30)
        cb.record_failure()  # 触发 OPEN
        assert cb.is_open

        fetcher = NetworkFetcher(max_retries=3, circuit_breaker=cb)
        result = fetcher.fetch("http://any.url", timeout=1)
        assert not result.success
        assert result.error_type == "CIRCUIT_OPEN"

    def test_retry_after_respected(self):
        """验证 Retry-After header 逻辑"""
        fetcher = NetworkFetcher(max_retries=0)
        # 模拟 Retry-After header
        class MockHeaders:
            def get(self, key, default=None):
                if key == "Retry-After":
                    return "5"
                return default

        retry_after = fetcher._parse_retry_after(MockHeaders())
        assert retry_after == 5

    def test_retry_after_none(self):
        fetcher = NetworkFetcher(max_retries=0)
        assert fetcher._parse_retry_after(object()) is None
