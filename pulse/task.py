"""
pulse/task.py — 统一 Task Object (7层 Surface 层核心)

多入口 (CLI / API / Webhook / 前端 / 定时任务) 归一成单一 Task 形状。
后续所有层只处理这一个对象: Orchestration/Context/Model/Tools 全部消费 Task。

设计原则:
  - Many doors, one task object — 入口差异在 Surface 层吸收
  - Task 是 Pydantic 模型 (契约校验, 输出解析复用)
  - source 记录入口, 支持审计溯源
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EntrySource = Literal["cli", "api", "webhook", "frontend", "schedule", "telegram", "unknown"]


class Task(BaseModel):
    """统一任务对象 — 所有入口归一成此形状"""

    task_id: str = Field(..., description="任务唯一 ID (uuid 或 hash)")
    source: EntrySource = "unknown"
    intent: str = Field(..., description="任务意图/查询, 归一后的原始输入")
    payload: dict[str, Any] = Field(default_factory=dict, description="结构化附加参数 (领域相关)")
    domain: str = Field(default="compliance", description="领域 (compliance/retail/jobs/...)")
    budget: dict[str, float] = Field(
        default_factory=lambda: {"context_chars": 6000, "max_tokens": 1000},
        description="资源预算 (Context 层消费)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="来源元数据 (入口/用户/时间)")

    @field_validator("intent")
    @classmethod
    def _intent_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("intent 不能为空")
        return v

    @classmethod
    def from_cli(cls, query: str, **meta: Any) -> Task:
        """CLI 入口归一"""
        return cls(task_id=_gen_id(), source="cli", intent=query, metadata=meta)

    @classmethod
    def from_api(cls, body: dict, **meta: Any) -> Task:
        """API 入口归一 (body: {query, domain?, payload?, budget?})"""
        return cls(
            task_id=_gen_id(),
            source="api",
            intent=body.get("query", ""),
            domain=body.get("domain", "compliance"),
            payload=body.get("payload", {}),
            budget=body.get("budget", {"context_chars": 6000, "max_tokens": 1000}),
            metadata=meta,
        )

    @classmethod
    def from_webhook(cls, event: dict, **meta: Any) -> Task:
        """Webhook 入口归一 (event: {type, data})"""
        return cls(
            task_id=_gen_id(),
            source="webhook",
            intent=str(event.get("type", "")),
            payload={"event_data": event.get("data", {})},
            metadata=meta,
        )

    @classmethod
    def from_frontend(cls, query: str, **meta: Any) -> Task:
        """前端入口归一 (Streamlit/Web)"""
        return cls(task_id=_gen_id(), source="frontend", intent=query, metadata=meta)


def _gen_id() -> str:
    import hashlib
    import time

    return hashlib.sha1(f"{time.time_ns()}".encode()).hexdigest()[:12]


# ── 示例: 多入口归一 ──────────────────────────────────────────────────
if __name__ == "__main__":
    t1 = Task.from_cli("算法备案的要求是什么", user="baiyun")
    t2 = Task.from_api({"query": "跨境数据传输限制", "domain": "compliance"}, api_key="xxx")
    t3 = Task.from_webhook({"type": "ticket.created", "data": {"title": "合规咨询"}})
    t4 = Task.from_frontend("深度合成需要标识吗", session="s1")

    for t in (t1, t2, t3, t4):
        print(f"[{t.source}] {t.task_id} | {t.intent[:25]} | domain={t.domain}")
