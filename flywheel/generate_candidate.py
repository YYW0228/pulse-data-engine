#!/usr/bin/env python3
"""Flywheel 候选技能生成 — REVIEW_QUEUE pattern → 本地 llama 提案 → proposals/

用法:
  python flywheel/generate_candidate.py                 # 全部 pending pattern
  python flywheel/generate_candidate.py <pattern_id>    # 单个 pattern
  python flywheel/generate_candidate.py --example       # 生成样例 failures + 聚类 + 提案 (端到端冒烟)

边界: 调用本地 llama-server (127.0.0.1:8080), 无外部可见性 → llm_audit 豁免 (与 ingest_* 同款架构边界)
纪律: propose-never-auto-apply — 只写提案区 proposals/, 绝不直接改技能库
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FLYWHEEL = Path(__file__).resolve().parent
CANDIDATES = FLYWHEEL / "candidates"
PROPOSALS = FLYWHEEL / "proposals"
REVIEW_QUEUE = FLYWHEEL / "REVIEW_QUEUE.md"
LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"

PROMPT_TEMPLATE = """你是一个技能工程师。根据下面的失败模式聚类, 生成一份可晋升的技能提案 (SKILL.md 格式)。

失败模式聚类:
{pattern_json}

要求:
1. 输出 markdown, 结构: # <技能名> / ## When to Use (触发条件) / ## 步骤 (编号, 可执行) / ## 验证 (明确命令或检查项) / ## 坑 (2-4条)
2. 触发描述用英文开头: "Use when <触发场景>."
3. 内容必须直接源于失败数据, 不得虚构系统能力
4. 控制在 40 行内, 具体可执行, 不要泛泛而谈
"""


def load_patterns() -> list[dict]:
    if not CANDIDATES.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CANDIDATES.glob("*.json"))]


def call_llama(prompt: str) -> str | None:
    payload = {
        "model": "qwen3.5",
        "messages": [{"role": "user", "content": prompt}],
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": 1200,
        "temperature": 0.3,
    }
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "120", LLAMA_URL, "-H", "Content-Type: application/json",
             "-d", json.dumps(payload, ensure_ascii=False)],
            capture_output=True, text=True, timeout=130, check=False,
        )
        data = json.loads(r.stdout)
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ! llama 调用失败: {e}", file=sys.stderr)
        return None


def generate(pattern: dict) -> Path | None:
    pid = pattern["pattern_id"]
    out = PROPOSALS / f"{pid}.md"
    if out.exists():
        print(f"  = {pid} 已有提案, 跳过")
        return out

    prompt = PROMPT_TEMPLATE.format(pattern_json=json.dumps(pattern, ensure_ascii=False, indent=2))
    content = call_llama(prompt)
    if not content or len(content) < 200:
        print(f"  ! {pid} 生成失败/过短, 放弃")
        return None

    header = (
        f"<!-- proposal: {pid} | count: {pattern['count']} | "
        f"generated: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')} "
        f"| status: pending-review -->\n"
    )
    out.write_text(header + content, encoding="utf-8")
    print(f"  ✓ {pid} → proposals/{pid}.md ({len(content)} 字符)")
    return out


def update_queue(patterns: list[dict], proposals: set[str]) -> None:
    """REVIEW_QUEUE 状态同步: 有提案的 pattern 标 [提案就绪]"""
    if not REVIEW_QUEUE.exists():
        return
    text = REVIEW_QUEUE.read_text(encoding="utf-8")
    for p in patterns:
        if p["pattern_id"] in proposals:
            # 兼容带序号格式: ### 1. [pid]
            text = re.sub(rf"(### \d+\. )\[{p['pattern_id']}\]", rf"\1[提案就绪] [{p['pattern_id']}]", text)
            text = text.replace(f"[{p['pattern_id']}]", f"[提案就绪] [{p['pattern_id']}]", 1)
    REVIEW_QUEUE.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Flywheel 候选技能生成 (本地 llama 8080)")
    ap.add_argument("pattern_id", nargs="?", help="指定 pattern_id, 缺省全部")
    ap.add_argument("--example", action="store_true", help="端到端冒烟 (样例→聚类→提案)")
    args = ap.parse_args()

    PROPOSALS.mkdir(exist_ok=True)
    patterns = load_patterns()
    if args.pattern_id:
        patterns = [p for p in patterns if p["pattern_id"] == args.pattern_id]
    if not patterns:
        print("无待生成 pattern (先跑 cluster.py)")
        return 0

    print(f"生成候选技能: {len(patterns)} 个 pattern → llama 8080")
    done: set[str] = set()
    for p in patterns:
        out = generate(p)
        if out:
            done.add(p["pattern_id"])
    if done:
        update_queue(patterns, done)
        print(f"完成 {len(done)} 个提案 → flywheel/proposals/ (等待人工审批)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
