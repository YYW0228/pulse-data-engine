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
import gzip
import json
import sys
import time
from collections import defaultdict

from pulse.llm_audit import AUDIT_PATH, _prompt_hash

REQUIRED = ("call_id", "ts", "model", "messages")
LOOP_WINDOW_S = 600
LOOP_THRESHOLD = 3


def load(days: int) -> tuple[list[dict], list[dict], list[dict]]:
    """返回 (requests, results, events); events = 压缩/其他一等审计事件。"""
    cutoff = time.time() - days * 86400
    requests: list[dict] = []
    results: list[dict] = []
    events: list[dict] = []
    if not AUDIT_PATH.exists():
        return requests, results, events
    with AUDIT_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (e.get("ts_epoch") or 0) < cutoff:
                continue
            kind = e.get("kind")
            if kind == "request":
                requests.append(e)
            elif kind == "result":
                results.append(e)
            else:
                events.append(e)
    return requests, results, events


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
    """10 分钟窗口内同 source+hash >=3 次的疑似循环 (eval 标记记录排除)。"""
    by_key: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in requests:
        if r.get("eval"):
            continue                          # eval 批量评测 = 合法重复, 非死循环
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


def find_compaction_orphans(events: list[dict]) -> list[dict]:
    """孤儿压缩检测: compaction/start 无配对 compaction/end (崩溃/异常中道)。

    压缩中途崩溃 = 压缩后重发从未发生或未收尾, 审计链在该点断裂。
    """
    starts, ends = {}, set()
    for e in events:
        if e.get("kind") == "compaction/start":
            starts[e.get("compaction_id", "")] = e
        elif e.get("kind") == "compaction/end":
            ends.add(e.get("compaction_id", ""))
    return [v for cid, v in starts.items() if cid and cid not in ends]


def archive(days: int) -> int:
    """审计膨胀控制: 超过 days 天的记录 gzip 归档, 主文件只留窗口内。

    归档保留完整原文 (gzip), 主链保持轻量可解析; 与 compaction 语义一致:
    最近完整原文 + 更早摘要指针 (hash 校验能力随原文入档保留)。
    返回归档条数。
    """
    cutoff = time.time() - days * 86400
    if not AUDIT_PATH.exists():
        return 0
    keep, stale = [], []
    with AUDIT_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                stale.append(line)   # 损坏行随归档移走, 不阻塞主链
                continue
            if (e.get("ts_epoch") or 0) < cutoff:
                stale.append(line)
            else:
                keep.append(line)
    if not stale:
        return 0
    archive_dir = AUDIT_PATH.parent / "llm_audit_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    month = time.strftime("%Y%m")
    gz = archive_dir / f"llm_audit.{month}.jsonl.gz"
    with gzip.open(gz, "at", encoding="utf-8") as f:
        f.writelines(stale)
    AUDIT_PATH.write_text("".join(keep), encoding="utf-8")
    print(f"[audit] 归档 {len(stale)} 条 (> {days} 天) → {gz} | 主链剩 {len(keep)} 条")
    return len(stale)


def main() -> int:
    ap = argparse.ArgumentParser(description="Model-visible = Logged 可重建性审计")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--ci", action="store_true", help="CI 门禁: 非 100% 完整或发现循环则退出 1")
    ap.add_argument("--archive-days", type=int, default=0,
                    help="先归档超过 N 天的记录 (gzip, 原文保留), 再报告")
    args = ap.parse_args()

    if args.archive_days:
        archive(args.archive_days)

    requests, results, events = load(args.days)
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
    orphans = find_compaction_orphans(events)
    failed = sum(1 for x in results if not x.get("ok"))
    avg_ms = (sum(x.get("duration_ms", 0) for x in results) / len(results)) if results else 0
    compactions = sum(1 for e in events if e.get("kind") == "compaction/start")

    print(f"[audit] 窗口 {args.days} 天 | 请求 {len(requests)} | 结果 {len(results)}"
          f" | 可重建率 {rate:.1f}% ({ok}/{len(requests)})")
    print(f"[audit] 失败请求 {failed} | 平均耗时 {avg_ms:.0f}ms | 压缩 {compactions} 次"
          f" | 孤儿 {len(orphans)}")
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

    if orphans:
        print(f"[audit] ⚠ 孤儿压缩 {len(orphans)} 处 (start 无 end, 审计链断裂点):")
        for o in orphans[:10]:
            print(f"  - {o.get('ts')} {o.get('source')} {o.get('compaction_id')}"
                  f" trigger={o.get('trigger')} dropped={o.get('dropped_count')}")
    else:
        print("[audit] 无孤儿压缩")

    if args.ci and (rate < 100.0 or loops or orphans):
        print("[audit] CI FAIL: 完整率 <100% 或存在循环/孤儿压缩", file=sys.stderr)
        return 1
    print("[audit] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
