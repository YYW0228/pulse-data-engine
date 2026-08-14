"""
pulse/llm_audit.py — Model-visible = Logged 运行时不变量 (简化版)

不变量: 任何发送给模型的请求, 其完整输入必须在调用前落盘。
审计路径 data/llm_audit.jsonl 可 100% 重建模型所见 (prompt 全量 + 元数据)。

用法 (调用点接入样板 — 对调用方透明):
    from pulse.llm_audit import audited_post
    resp = audited_post(url, headers, json=body, timeout=45, source="subagent.review")

    # 原 httpx.post 直接替换为 audited_post, 其余参数语义一致。

审计:
    uv run python -m scripts.audit_reconstruct --days 7     # 可重建率 + 循环检测
    uv run python -m scripts.audit_reconstruct --ci         # CI 门禁模式 (非 100% 退出 1)
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

AUDIT_PATH = Path("data/llm_audit.jsonl")
_lock = threading.Lock()


def _append(entry: dict[str, Any]) -> None:
    """线程安全追加一条审计记录; 写失败只告警, 绝不阻塞模型调用。"""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _lock, AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # 审计故障不允许打断业务
        print(f"[llm_audit] WARN 写入失败: {exc}", flush=True)


def _prompt_hash(messages: list[dict]) -> str:
    return hashlib.md5(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()[:16]


def audited_post(
    url: str,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: float = 45,
    source: str = "unknown",
    **kwargs: Any,
):
    """httpx.post 的审计包装: 调用前完整落盘请求, 调用后记录结果。

    参数与 httpx.post 一致 (url/headers/json/timeout), 额外 source 标注调用方。
    """
    import httpx

    call_id = f"llm_{uuid.uuid4().hex[:10]}"
    messages = (json or {}).get("messages") or []
    body: dict[str, Any] = {
        "call_id": call_id,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_epoch": time.time(),
        "source": source,
        "url": url,
        "model": (json or {}).get("model", "?"),
        "temperature": (json or {}).get("temperature"),
        "max_tokens": (json or {}).get("max_tokens"),
        "messages": messages,          # 全量: 模型所见 = 已记录
        "prompt_hash": _prompt_hash(messages),
        "reconstructable": bool(messages) and all(
            isinstance(m.get("content"), str) and m["content"].strip() for m in messages
        ),
    }
    _append({"kind": "request", **body})

    t0 = time.time()
    try:
        resp = httpx.post(url, headers=headers, json=json, timeout=timeout, **kwargs)
        _append({
            "kind": "result",
            "call_id": call_id,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts_epoch": time.time(),
            "status": resp.status_code,
            "duration_ms": round((time.time() - t0) * 1000, 1),
            "ok": resp.status_code == 200,
            "error": None,
        })
        return resp
    except Exception as exc:
        _append({
            "kind": "result",
            "call_id": call_id,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts_epoch": time.time(),
            "status": None,
            "duration_ms": round((time.time() - t0) * 1000, 1),
            "ok": False,
            "error": str(exc),
        })
        raise
