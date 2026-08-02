"""
scripts/compliance_service.py — 合规问答统一服务层 (Surface Task Object)

多入口 (CLI/前端/API/Telegram) → Task Object → 统一处理 → 结构化结果

流程:
  Task (from_cli/from_api/...) → classify_intent → answer → ComplianceParser → 结果

这完成了 7 层 Surface: 后续所有入口只构造 Task, 服务层统一消费。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pulse.parsing import ComplianceParser, ParseResult
from pulse.task import Task


class ComplianceService:
    """合规问答服务 — 统一入口消费 Task Object"""

    def __init__(self) -> None:
        self.parser = ComplianceParser()

    def handle(self, task: Task) -> dict:
        """处理一个 Task, 返回结构化结果"""
        t0 = time.time()

        # 1. 意图分类 (非事实查询前置拒绝)
        from compliance_qa import INTENT_REJECT, classify_intent

        intent = classify_intent(task.intent)
        if intent != "factual_query":
            return {
                "task_id": task.task_id,
                "source": task.source,
                "intent": intent,
                "rejected": True,
                "answer": INTENT_REJECT.get(intent, INTENT_REJECT["instruction_attack"]),
                "citations": [],
                "confidence": "low",
                "ms": round((time.time() - t0) * 1000, 1),
            }

        # 2. 问答 (检索+路由+回答, 传 history 供 PrefixCache)
        from compliance_qa import answer as qa_answer

        history = task.payload.get("history") if isinstance(task.payload.get("history"), list) else None
        if history is None:
            history = task.metadata.get("history") if isinstance(task.metadata.get("history"), list) else None
        raw = qa_answer(task.intent, mask_metadata=True, history=history)

        # 3. 结构化解析
        parsed: ParseResult = self.parser.parse(raw)

        # 4. 子 Agent 评审 (主-从模式, 独立找茬)
        review = None
        if parsed.answer is not None and not parsed.fallback:
            try:
                from pulse.subagent import review_answer

                review = review_answer(
                    task.intent,
                    parsed.answer.answer,
                    [c.model_dump() for c in parsed.answer.citations],
                )
            except Exception:
                review = None

        # 5. 组装结果
        result = {
            "task_id": task.task_id,
            "source": task.source,
            "intent": task.intent[:100],
            "rejected": False,
            "answer": parsed.answer.answer if parsed.answer else raw,
            "citations": [c.model_dump() for c in parsed.answer.citations] if parsed.answer else [],
            "confidence": parsed.answer.confidence if parsed.answer else "low",
            "disclaimer": parsed.answer.disclaimer if parsed.answer else "",
            "fallback": parsed.fallback,
            "review": {
                "verdict": review.verdict,
                "issues": review.issues,
                "suggestions": review.suggestions,
            } if review else None,
            "ms": round((time.time() - t0) * 1000, 1),
        }

        # 6. 证据包 Artifact (Kun 证据化交付 — 可验收交付物)
        try:
            from pulse.artifacts import build_artifact

            art = build_artifact(
                task_id=task.task_id,
                query=task.intent,
                answer=result["answer"],
                citations=result["citations"],
                confidence=result["confidence"],
                guardrails={"intent": intent, "approval_needed": result["confidence"] == "low"},
                cost={"tokens_in": 0, "tokens_out": 0, "ms": result["ms"], "cost_usd": 0},
                review=result["review"],
            )
            result["artifact_path"] = str(art.save())
        except Exception:
            result["artifact_path"] = None

        return result


def cli_entry(query: str, source: str = "cli") -> None:
    """CLI 入口"""
    task = Task.from_cli(query, user="cli")
    svc = ComplianceService()
    result = svc.handle(task)
    print(f"\n[{result['intent']}] {result['answer']}")
    if result.get("citations"):
        print("\n引用来源:")
        for c in result["citations"]:
            print(f"  - {c['doc']} | {c['section']}")
    if result.get("confidence") == "low":
        print("\n⚠️ 低置信度 — 建议人工复核")
    print(f"\n(耗时 {result['ms']}ms, 模型结果 {'结构化' if not result['fallback'] else '降级'})")


def api_entry(body: dict) -> dict:
    """API 入口 (FastAPI/Flask 兼容)"""
    task = Task.from_api(body)
    svc = ComplianceService()
    return svc.handle(task)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="合规问答服务 (Task Object 入口)")
    parser.add_argument("query", nargs="?", default="算法备案的要求是什么")
    parser.add_argument("--source", default="cli", choices=["cli", "api", "webhook", "frontend"])
    args = parser.parse_args()
    cli_entry(args.query, args.source)
