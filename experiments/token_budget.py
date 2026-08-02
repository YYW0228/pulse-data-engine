"""
experiments/token_budget.py — Token Budget 硬闸门 (源自 DeerFlow)

DeerFlow 思路: 累计 input/output token, 超预算 → budget_capped 优雅终止
(不抛异常, 与正常完成可区分)。

我们的适配: 合规问答 — 每次问答前检查会话累计 token:
  1. 从 compliance_metrics.jsonl 读取当前会话累计
  2. 超 budget → 返回 budget_capped 提示 (不发起 LLM 调用)
  3. 成本可承诺: "这个会话最多花 X 元"

状态: EXPERIMENT (未合入主线)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# DeepSeek 价格 (近似): $0.27/M in + $1.10/M out
PRICE_IN_PER_M = 0.27
PRICE_OUT_PER_M = 1.10


@dataclass
class TokenBudget:
    """Token 预算闸门 — 会话级"""

    max_tokens_in: int = 500_000      # 会话累计 input 上限 (约 $0.135)
    max_tokens_out: int = 100_000     # 会话累计 output 上限 (约 $0.11)
    metrics_path: Path = Path("data/compliance_metrics.jsonl")

    def session_usage(self, session_key: str | None = None) -> dict:
        """从 metrics 读取累计用量 (可按 query 前缀过滤会话)"""
        import json

        total_in = 0
        total_out = 0
        if not self.metrics_path.exists():
            return {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}

        with self.metrics_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if session_key and session_key not in r.get("query", ""):
                    continue
                total_in += r.get("tokens_in", 0)
                total_out += r.get("tokens_out", 0)

        cost = total_in / 1e6 * PRICE_IN_PER_M + total_out / 1e6 * PRICE_OUT_PER_M
        return {"tokens_in": total_in, "tokens_out": total_out, "cost_usd": round(cost, 4)}

    def check(self, session_key: str | None = None) -> dict:
        """检查预算: 返回 {allowed, reason, usage}"""
        usage = self.session_usage(session_key)
        if usage["tokens_in"] > self.max_tokens_in:
            return {"allowed": False, "reason": "budget_capped (input 超限)",
                    "usage": usage}
        if usage["tokens_out"] > self.max_tokens_out:
            return {"allowed": False, "reason": "budget_capped (output 超限)",
                    "usage": usage}
        return {"allowed": True, "reason": "ok", "usage": usage}


if __name__ == "__main__":
    b = TokenBudget()
    usage = b.session_usage()
    print(f"当前会话累计: {usage['tokens_in']} in / {usage['tokens_out']} out / ${usage['cost_usd']}")
    r = b.check()
    print(f"预算检查: allowed={r['allowed']} ({r['reason']})")

    # 模拟超预算: 调小上限
    b2 = TokenBudget(max_tokens_in=100)
    r2 = b2.check()
    print(f"小预算检查: allowed={r2['allowed']} ({r2['reason']})")
    assert r2["allowed"] is False
    print("✅ Token Budget 硬闸门生效")
