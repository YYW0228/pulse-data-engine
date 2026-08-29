#!/usr/bin/env python3
"""Flywheel → GitHub Issues 对接 (半自动)

用法:
  python flywheel/to_issues.py --dry-run            # 生成草稿 (默认)
  python flywheel/to_issues.py --create             # 审批后创建 (gh issue create)
  python flywheel/to_issues.py --create --repo YYW0228/hermes-brain

纪律: pattern ≥2 次才建 Issue (聚类纪律); 已晋升/已建过的 pattern 跳过; 创建前人工过目。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

FLYWHEEL = Path(__file__).resolve().parent
CANDIDATES = FLYWHEEL / "candidates"
DEFAULT_REPO = "YYW0228/pulse-data-engine"

TEMPLATE = """## 错误签名
<!-- pattern_id: {pid} | 计数: {count} | 首次: {first_seen} -->

{representative}

## 复现命令
```bash
{command}
```

## 相关机器
{hosts}

## 建议修复方向
<!-- 候选技能提案: flywheel/proposals/ 或飞轮 REVIEW_QUEUE -->

## 失败痕迹
{failure_ids}

---
_由 fail-cluster 飞轮对接生成 (pattern ≥2 次触发), 详见 agentic-flywheel 技能_
"""


def load_patterns() -> list[dict]:
    if not CANDIDATES.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CANDIDATES.glob("*.json"))]


def build_issue_body(p: dict) -> str:
    return TEMPLATE.format(
        pid=p["pattern_id"], count=p["count"], first_seen=str(p.get("first_seen", ""))[:10],
        representative=str(p.get("representative", ""))[:300],
        command=str(p.get("command", ""))[:200] if p.get("command") else "(见痕迹)",
        hosts=", ".join(f"{k}({v})" for k, v in p.get("hosts", {}).items()),
        failure_ids=", ".join(p.get("failure_ids", [])),
    )


def create_issue(repo: str, title: str, body: str, labels: str) -> bool:
    r = subprocess.run(
        ["gh", "issue", "create", "-R", repo, "--title", title, "--body", body, "--label", labels],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if r.returncode == 0:
        print(f"  ✓ {r.stdout.strip()}")
        return True
    print(f"  ✗ {r.stderr.strip()[:200]}", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Flywheel → Issues 对接")
    ap.add_argument("--create", action="store_true", help="实际创建 (缺省=草稿)")
    ap.add_argument("--dry-run", action="store_true", help="草稿模式 (默认行为, 显式声明)")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--label", default="agent-failure,tech-debt")
    args = ap.parse_args()

    patterns = load_patterns()
    if not patterns:
        print("无 pattern (先跑 cluster.py)")
        return 0

    for p in patterns:
        title = f"[agent-failure] 失败模式 {p['pattern_id'][:8]} ({p['count']}次) {str(p.get('representative', ''))[:40]}"
        if args.create:
            create_issue(args.repo, title, build_issue_body(p), args.label)
        else:
            print(f"  [草稿] {title}")
            print(build_issue_body(p)[:200] + "\n")
    print(f"共 {len(patterns)} 个 pattern" + (" — 已创建" if args.create else " — 草稿模式, 加 --create 创建"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
