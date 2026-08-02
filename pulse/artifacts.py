"""
pulse/artifacts.py — 证据包 Artifacts (源自 Kun 证据化交付)

Kun 思路: 交付物 (diff/测试/截图) 打包可验收, 而非"Agent 自称完成"。
我们适配: 每次问答输出完整证据包:
  answer  + citations(引用) + evidence(依据片段) + guardrails(护栏报告)
         + cost(成本摘要) + trace_id(可追溯)

用途: 客户验收金标 (P0 引用100% / P1 命中≥80% / P2 抽检) 的底层结构。
      sales 卖点: "不依赖 Agent 自称完成, 每次回答附完整证据链"
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVIDENCE_OUTPUT_DIR = Path("data/artifacts")


@dataclass
class EvidenceArtifact:
    """单次问答的证据包"""

    task_id: str = ""
    query: str = ""
    answer: str = ""
    citations: list[dict] = field(default_factory=list)      # [文档|章节]
    evidence: list[dict] = field(default_factory=list)       # 依据片段
    confidence: str = "medium"
    guardrails: dict = field(default_factory=dict)           # 意图分类/注入/循环检测
    cost: dict = field(default_factory=dict)                 # tokens/耗时/费用
    review: dict | None = None                               # 子代理评审
    trace_id: str = ""                                       # 可追溯
    ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query[:200],
            "answer": self.answer,
            "citations": self.citations,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "guardrails": self.guardrails,
            "cost": self.cost,
            "review": self.review,
            "trace_id": self.trace_id,
            "ts": self.ts,
        }

    def save(self) -> Path:
        """存 JSON + Markdown 双格式"""
        EVIDENCE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_id = (self.task_id or f"art_{int(time.time())}").replace("/", "_")

        # JSON (机器可读, 验收程序用)
        jpath = EVIDENCE_OUTPUT_DIR / f"{safe_id}.json"
        jpath.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        # Markdown (人可读, 客户验收用)
        mpath = EVIDENCE_OUTPUT_DIR / f"{safe_id}.md"
        mpath.write_text(self.to_markdown(), encoding="utf-8")
        return mpath

    def to_markdown(self) -> str:
        """Markdown 证据报告 (客户可直接看)"""
        lines = [
            f"# 证据包 {self.task_id}",
            f"**时间**: {self.ts} | **Trace**: `{self.trace_id}`",
            f"**问题**: {self.query}",
            f"**置信度**: {self.confidence}",
            "",
            "## 回答",
            self.answer,
            "",
            f"## 引用 ({len(self.citations)})",
        ]
        for c in self.citations:
            lines.append(f"- `{c.get('doc','')}` | {c.get('section','')}")
        lines += [
            "",
            f"## 依据片段 ({len(self.evidence)})",
        ]
        for e in self.evidence[:5]:
            lines.append(f"- [{e.get('doc','')}] {e.get('snippet','')[:120]}...")
        lines += [
            "",
            "## 护栏",
            f"- 意图分类: {self.guardrails.get('intent', 'factual_query')}",
            f"- 注入/越权: {self.guardrails.get('injection_checked', 'n/a')}",
            f"- 低置信度闸门: {self.guardrails.get('approval_needed', False)}",
            "",
            "## 成本",
            f"- tokens: {self.cost.get('tokens_in', 0)} in → {self.cost.get('tokens_out', 0)} out",
            f"- 耗时: {self.cost.get('ms', 0)}ms",
            f"- 估算费用: ${self.cost.get('cost_usd', 0):.5f}",
            "",
        ]
        if self.review:
            lines += [
                "## 子代理评审",
                f"- verdict: {self.review.get('verdict', '?')}",
            ]
            for issue in self.review.get("issues", [])[:3]:
                lines.append(f"- ⚠️ {issue}")
        return "\n".join(lines)


def build_artifact(**kwargs: Any) -> EvidenceArtifact:
    """工厂: 构建证据包"""
    art = EvidenceArtifact(**kwargs)
    if not art.ts:
        art.ts = time.strftime("%Y-%m-%d %H:%M:%S")
    return art


if __name__ == "__main__":
    art = build_artifact(
        task_id="demo_001",
        query="算法备案的要求是什么",
        answer="根据资料, 算法备案需在十个工作日内完成...",
        citations=[{"doc": "cac-algorithm-filing-guide.md", "section": "一"}],
        evidence=[{"doc": "cac-algorithm-filing-guide.md", "snippet": "备案义务主体..."}],
        confidence="high",
        guardrails={"intent": "factual_query", "injection_checked": True, "approval_needed": False},
        cost={"tokens_in": 1241, "tokens_out": 460, "ms": 2100, "cost_usd": 0.0009},
        trace_id="run_abc123",
    )
    path = art.save()
    print(f"✅ 证据包已保存: {path}")
