"""
scripts/audit_reconstruct.py — Model-visible = Logged 审计 (可重建性 + 循环检测)

校验 llm_audit.jsonl 中每条请求是否可完整重建模型所见:
  - 必填字段齐全 (call_id/model/ts/messages)
  - messages 非空且每项 content 非空
  - prompt_hash 与 messages 一致 (防篡改)

循环检测: 同 source 同 prompt_hash 在 10 分钟窗口内 >=3 次 = 疑似死循环。

用法:
  uv run python -m scripts.audit_reconstruct            # 最近 7 天报告
  uv run python -m scripts.audit_reconstruct --days 1   # 最近 1 天
  uv run python -m scripts.audit_reconstruct --ci       # CI 模式: 完整率<100% 或发现循环 → exit 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict

from pulse.llm_audit import AUDIT_PATH, _prompt_hash

REQUIRED = ("call_id", "ts", "model", "messages")
LOOP_WINDOW_S = 600
LOOP_THRESHOLD = 3


def load(days: int) -> tuple[list[dict], list[dict]]:
    """返回 (requests, results); 解析失败的行计入损坏。"""
    cutoff = time.time() - days * 86400
    requests: list[dict] = []
    results: list[dict] = []
    bad: list[dict] = []
    if not AUDIT_PATH.exists():
        return requests, results
    with AUDIT_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                bad.append({"kind": "corrupt", "ts_epoch": None})
                continue
            if (e.get("ts_epoch") or 0) < cutoff:
                continue
            (requests if e.get("kind") == "request" else results).append(e)
    return requests, results


def reconstructable(e: dict) -> tuple[bool, list[str]]:
    """单条可重建性: 返回 (ok, 缺失项列表)。"""
    missing = [k for k in REQUIRED if not e.get(k)]
    msgs = e.get("messages") or []
    if not msgs:
        missing.append("messages.empty")
    else:
        empty = [i for i, m in enumerate(msgs)
                 if not isinstance(m.get("content"), str) or not m["content"].strip()]
        if empty:
            missing.append(f"messages[{empty[0]}].content.empty")
    if not missing and e.get("prompt_hash"):
        actual = _prompt_hash(msgs)
        if actual != e.get("prompt_hash"):
            missing.append("prompt_hash.mismatch")
    return (not missing, missing)


def find_loops(requests: list[dict]) -> list[dict]:
    """10 分钟窗口内同 source+hash >=3 次的疑似循环。"""
    by_key: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in requests:
        by_key[(r.get("source", "?"), r.get("prompt_hash", "?"))].append(r.get("ts_epoch") or 0)
    loops = []
    for (source, h), stamps in by_key.items():
        stamps.sort()
        for i in range(len(stamps) - LOOP_THRESHOLD + 1):
            if stamps[i + LOOP_THRESHOLD - 1] - stamps[i] <= LOOP_WINDOW_S:
                loops.append({
                    "source": source,
                    "prompt_hash": h,
                    "count": len(stamps),
                    "window_s": round(stamps[-1] - stamps[0], 1),
                    "first": time.strftime("%m-%d %H:%M:%S", time.localtime(stamps[0])),
                })
                break
    return loops


def main() -> int:
    ap = argparse.ArgumentParser(description="Model-visible = Logged 可重建性审计")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--ci", action="store_true", help="CI 门禁: 非 100% 完整或发现循环则退出 1")
    args = ap.parse_args()

    requests, results = load(args.days)
    if not requests:
        print(f"[audit] 无请求记录 (最近 {args.days} 天) — 审计路径为空: {AUDIT_PATH}")
        return 0

    ok = 0
    gaps: list[dict] = []
    for r in requests:
        good, missing = reconstructable(r)
        if good:
            ok += 1
        else:
            gaps.append({"call_id": r.get("call_id"), "source": r.get("source"),
                         "ts": r.get("ts"), "missing": missing})
    rate = ok / len(requests) * 100
    loops = find_loops(requests)
    failed = sum(1 for x in results if not x.get("ok"))
    avg_ms = (sum(x.get("duration_ms", 0) for x in results) / len(results)) if results else 0

    print(f"[audit] 窗口 {args.days} 天 | 请求 {len(requests)} | 结果 {len(results)}"
          f" | 可重建率 {rate:.1f}% ({ok}/{len(requests)})")
    print(f"[audit] 失败请求 {failed} | 平均耗时 {avg_ms:.0f}ms")
    if gaps:
        print("[audit] 缺口清单 (违反 model-visible=logged):")
        for g in gaps[:20]:
            print(f"  - {g['ts']} {g['source']} {g['call_id']}: {','.join(g['missing'])}")
        if len(gaps) > 20:
            print(f"  ... 共 {len(gaps)} 条缺口")
    if loops:
        print(f"[audit] ⚠ 疑似循环 {len(loops)} 处 (10min 内同 prompt >=3 次):")
        for lp in loops[:10]:
            print(f"  - {lp['first']} {lp['source']} x{lp['count']} ({lp['window_s']}s) {lp['prompt_hash']}")
    else:
        print("[audit] 无循环模式")

    if args.ci and (rate < 100.0 or loops):
        print("[audit] CI FAIL: 完整率 <100% 或存在循环", file=sys.stderr)
        return 1
    print("[audit] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
