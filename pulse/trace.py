"""
pulse/trace.py — 全链路 Trace + Replay (7层 Observability 深化)

记录每次问答的完整步骤轨迹:
  query → 检索(候选块+相似度) → 路由(模型决策) → 编译(最终块) → 回答(tokens/引用)

支持:
  - trace: 每次问答存 JSONL (可审计)
  - replay: 按 run_id 回放某次问答的完整决策链 (调试"为什么偏离")

用法:
  uv run python -m pulse.trace --tail 3        # 最近 3 条 trace
  uv run python -m pulse.trace --run <id>      # 回放指定 run
"""

import argparse
import json
import time
import uuid
from pathlib import Path

TRACE_PATH = Path("data/compliance_traces.jsonl")


class Tracer:
    """单次问答的 trace 记录器"""

    def __init__(self, query: str, source: str = "cli"):
        self.run_id = f"run_{uuid.uuid4().hex[:10]}"
        self.query = query
        self.source = source
        self.steps: list[dict] = []
        self.started = time.time()

    def step(self, name: str, detail: dict) -> None:
        """记录一步"""
        self.steps.append({
            "step": name,
            "ts": round((time.time() - self.started) * 1000, 1),
            **detail,
        })

    def save(self, result: dict) -> dict:
        """落盘 trace"""
        entry = {
            "run_id": self.run_id,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": self.query[:100],
            "source": self.source,
            "duration_ms": round((time.time() - self.started) * 1000, 1),
            "steps": self.steps,
            "result": {k: v for k, v in result.items() if k != "steps"},
        }
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


def replay(run_id: str) -> dict | None:
    """按 run_id 回放"""
    if not TRACE_PATH.exists():
        return None
    for line in TRACE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["run_id"] == run_id:
            return entry
    return None


def tail(n: int = 3) -> list[dict]:
    """最近 N 条 trace"""
    if not TRACE_PATH.exists():
        return []
    entries = [json.loads(l) for l in TRACE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    return entries[-n:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail", type=int, default=0, help="最近 N 条")
    parser.add_argument("--run", help="回放指定 run_id")
    args = parser.parse_args()

    if args.run:
        e = replay(args.run)
        if not e:
            print(f"未找到 run: {args.run}")
            return
        print(f"=== Replay {e['run_id']} ===")
        print(f"Q: {e['query']} | {e['source']} | {e['duration_ms']}ms\n")
        for s in e["steps"]:
            name = s.pop("step")
            ts = s.pop("ts")
            print(f"[{ts:>8}ms] {name}: {json.dumps(s, ensure_ascii=False)[:200]}")
        print(f"\n结果: {json.dumps(e['result'], ensure_ascii=False)[:300]}")
        return

    entries = tail(args.tail or 3)
    if not entries:
        print("暂无 trace")
        return
    for e in entries:
        print(f"{e['run_id']} | {e['ts']} | {e['query'][:35]} | {e['duration_ms']:.0f}ms | "
              f"{len(e['steps'])} 步 | {e['result'].get('model', '?')}")


if __name__ == "__main__":
    main()
