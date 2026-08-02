"""
experiments/loop_detection.py — Loop Detection 模式迁移 (源自 DeerFlow)

DeerFlow 思路: 每次模型响应后 hash tool_calls (name+args),
滑动窗口内同 hash ≥ warn_threshold → 注入提示打断; ≥ hard_threshold → 终止。

我们的适配: 合规问答场景 — 检测"重复检索/重复回答"模式:
  1. 记录每次问答的 (query 规范化 hash + 检索 top_doc 组合)
  2. 滑动窗口 (最近 N 次) 内重复 ≥ warn_threshold → 返回 loop 警告
  3. ≥ hard_threshold → 强制终止 (避免 token 浪费)

状态: EXPERIMENT (未合入主线, 用对抗评测验证后再决定)
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field


@dataclass
class LoopDetector:
    """循环检测器 — 滑动窗口 + hash 匹配"""

    window_size: int = 10          # 滑动窗口大小 (最近 N 次)
    warn_threshold: int = 3        # 同 hash 出现 ≥3 次 → 警告
    hard_threshold: int = 5        # ≥5 次 → 强制终止
    _recent: deque = field(default_factory=lambda: deque(maxlen=10))

    def __post_init__(self) -> None:
        self._recent = deque(maxlen=self.window_size)

    @staticmethod
    def fingerprint(query: str, top_docs: list[str]) -> str:
        """生成指纹: query 规范化 + top 文档组合 → hash"""
        norm = "".join(query.split()).lower()  # 去空格 + 小写
        docs = "|".join(sorted(top_docs))
        return hashlib.sha256(f"{norm}::{docs}".encode()).hexdigest()[:16]

    def record(self, fp: str) -> str:
        """记录一次调用, 返回状态: ok / warn / capped"""
        self._recent.append(fp)
        count = sum(1 for x in self._recent if x == fp)
        if count >= self.hard_threshold:
            return "capped"  # 强制终止
        if count >= self.warn_threshold:
            return "warn"   # 注入提示打断
        return "ok"

    def reset(self) -> None:
        self._recent.clear()


if __name__ == "__main__":
    # 验证: 模拟 6 次相同查询
    d = LoopDetector(window_size=10, warn_threshold=3, hard_threshold=5)
    for i in range(1, 7):
        status = d.record(d.fingerprint("算法备案要求", ["cac.md", "ai-core.md"]))
        print(f"第 {i} 次: {status}")
    assert d.record(d.fingerprint("算法备案要求", ["cac.md", "ai-core.md"])) == "capped"
    print("\n✅ 第 7 次强制终止 (capped) — 循环检测生效")
