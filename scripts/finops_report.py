#!/usr/bin/env python3
"""
scripts/finops_report.py — Agent 成本核算 CLI (Pattern 16 落地)

用法:
  python scripts/finops_report.py                    # 报告 (默认注册表)
  python scripts/finops_report.py --refresh          # 在线刷新 OpenRouter 价目表
  python scripts/finops_report.py --json             # JSON 输出
  python scripts/finops_report.py --usage usage.json # 从文件读 usage

usage.json 格式:
  [{"id":"u1","provider":"deepseek","model":"deepseek-chat",
    "metric":"input_tokens","unit":"1M tokens","quantity":0.5,
    "companyId":"co1","productId":"hermes"}, ...]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("pulse_finops", ROOT / "pulse" / "finops.py")
finops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finops)


def load_usage(path: Path) -> list[dict]:
    if not path.exists():
        print(f"❌ usage 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description="Agent 成本核算")
    parser.add_argument("--refresh", action="store_true", help="在线刷新 OpenRouter 价目表")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--usage", type=Path, default=None, help="usage JSON 文件路径")
    parser.add_argument("--company", default="starTalent", help="company ID")
    args = parser.parse_args()

    # 1. 价目表 (在线刷新或默认)
    registry = finops.refresh_provider_pricing(
        include_openrouter=args.refresh,
        timeout=10,
    ) if args.refresh else finops.DEFAULT_PRICING_REGISTRY

    # 2. usage 数据 (文件或空)
    usage = load_usage(args.usage) if args.usage else []

    # 3. 成本估算 + 汇总
    models = registry["entries"]
    costs = finops.estimate_costs_from_usage(usage, models, args.company)
    summary = finops.summarize_finops(costs, [], args.company)

    if args.json:
        print(json.dumps({
            "generatedAt": summary["generatedAt"],
            "companyId": args.company,
            "costCount": len(costs),
            "totalCost": finops.round_money(sum(c["amount"] for c in costs)),
            "byProvider": _by_provider(costs),
            "byProduct": summary["byProduct"],
            "pricingEntries": len(models),
            "pricingSources": registry["sources"],
        }, ensure_ascii=False, indent=2))
    else:
        print(finops.render_cost_report(costs, summary))
        print()
        print(f"*价目表条目: {len(models)} (含 OpenRouter 在线条目: {args.refresh})*")
        # 提示: 无 usage 数据
        if not usage:
            print()
            print("ℹ️  未提供 usage 数据 (--usage usage.json)。示例:")
            print("""  [{"id":"u1","provider":"deepseek","model":"deepseek-chat","metric":"input_tokens","unit":"1M tokens","quantity":10.0,"companyId":"co1","productId":"hermes"}]""")


def _by_provider(costs: list[dict]) -> dict:
    out: dict[str, float] = {}
    for c in costs:
        out[c["provider"]] = out.get(c["provider"], 0) + float(c["amount"])
    return {k: finops.round_money(v) for k, v in sorted(out.items(), key=lambda x: -x[1])}


if __name__ == "__main__":
    main()
