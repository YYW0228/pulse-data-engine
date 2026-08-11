#!/usr/bin/env python3
"""x_intel_collect.py — X 大 V 推文 → 知识库情报 (dap L4 采集)

数据流: dap x @handle → 过滤开发信号 → 生成 x-intel-<date>.md
  → kb_refresh sync_reports 模式 (pulse/data/intel_knowledge/) → 8502 索引

大 V 清单: 开发/商业/开源思想领袖 (可扩展)

用法:
  python scripts/x_intel_collect.py              # 全部大 V
  python scripts/x_intel_collect.py --handles a,b
  python scripts/x_intel_collect.py --dry-run    # 只打印将采集的
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DAP_ROOT = Path.home() / "projects" / "data-acquisition-pipeline"
OUT_DIR = Path.home() / "projects" / "pulse-data-engine" / "data" / "intel_knowledge"

# 大 V 清单: handle → (领域, 关注理由)
BIG_VS = {
    "turingou": ("harness/agent", "wanman 作者, agent matrix 设计哲学"),
    "karpathy": ("AI/教育", "vibe coding 提出者, LLM 认知"),
    "sama": ("AI/商业", "OpenAI CEO, 行业方向"),
    "miramurati": ("AI/商业", "OpenAI CTO, 产品与安全"),
    "garrytan": ("YC/创业", "YC CEO, agent brain 作者 (gbrain)"),
    "swyx": ("AI/工程", "AI 工程化, agent 生态观察"),
    "lmsys": ("开源/模型", "LLM 评测, 模型排行"),
}

# 开发信号关键词 (过滤日常)
SIGNAL_RE = re.compile(
    r"harness|agent|wanman|vibe|开发|工程|产品|代码|sandbank|chatben|tuwa|"
    r"codex|claude|github|git|编程|startup|yc|openai|llm|模型|训练|推理|"
    r"api|cloud|deploy|ship|发布|开源|open.?source|脑|brain|记忆|memory", re.I)


def fetch_handle(handle: str, limit: int = 20) -> list[dict]:
    """调 dap x 采集推文 (JSONL stdout)"""
    cmd = [str(DAP_ROOT / ".venv/bin/python"), "-m", "dap", "x",
           f"@{handle}", "--limit", str(limit)]
    r = subprocess.run(cmd, cwd=DAP_ROOT, capture_output=True, text=True,
                       timeout=120)
    tweets = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
            if d.get("text"):
                tweets.append(d)
        except json.JSONDecodeError:
            continue
    return tweets


def clean_text(raw: str) -> str:
    """清洗: 去 @handle 前缀/尾部噪音/登录墙残留"""
    t = re.sub(r"^@\w+(?=\d|\w{3})", "", raw)  # 去 @handle+时间 前缀
    t = re.sub(r"\d{2}:\d{2}.*$", "", t)  # 去视频时长
    t = re.sub(r"(Log in or sign up|Continue with|Scan to get|Terms·Privacy|© 2026).*$",
               "", t, flags=re.S)
    t = re.sub(r"\s*\d{2,}K?\s*$", "", t)  # 去尾部浏览数
    return t.strip()


def build_report(handle: str, meta: tuple, tweets: list[dict]) -> str:
    domain, reason = meta
    lines = [
        f"# X 信号: @{handle} ({domain})",
        f"> 来源: x.com/{handle} | 采集: dap L4 登录态 | {datetime.now():%Y-%m-%d %H:%M}",
        f"> 关注理由: {reason}",
        "",
    ]
    n = 0
    for t in tweets:
        text = clean_text(t["text"])
        if len(text) < 30 or not SIGNAL_RE.search(text):
            continue
        n += 1
        lines.append(f"## 信号 {n}")
        lines.append(text[:400])
        lines.append("")
    if n == 0:
        return ""
    lines.insert(0, f"> 本批 {n} 条开发信号 (过滤后)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handles", default="", help="逗号分隔, 覆盖默认清单")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    handles = [h.strip() for h in args.handles.split(",") if h.strip()] or list(BIG_VS)
    if args.dry_run:
        print(f"将采集 {len(handles)} 个大 V: {', '.join(handles)}")
        print(f"输出: {OUT_DIR}/x-intel-<date>.md → kb_refresh 索引")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"x-intel-{date_str}.md"
    all_lines: list[str] = []
    total = 0
    for h in handles:
        if h not in BIG_VS:
            print(f"⚠️ 未知 handle {h}, 跳过 (加入 BIG_VS 清单)")
            continue
        try:
            tweets = fetch_handle(h, args.limit)
            report = build_report(h, BIG_VS[h], tweets)
            if report:
                all_lines.append(report)
                total += 1
            print(f"✓ @{h}: {len(tweets)} 推文 → {len(report.splitlines()) if report else 0} 行报告")
        except Exception as e:
            print(f"✗ @{h}: {e}")

    if not all_lines:
        print("无信号产出 (所有大 V 无开发内容或采集失败)")
        return 1
    out_file.write_text("\n\n---\n\n".join(all_lines), encoding="utf-8")
    print(f"\n✅ {total}/{len(handles)} 大 V 产出 → {out_file}")
    print(f"   kb_refresh 将自动同步索引 (scene2_intel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
