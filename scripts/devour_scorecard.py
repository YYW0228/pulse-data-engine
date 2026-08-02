"""
scripts/devour_scorecard.py — 吞噬评分卡 (质量门禁)

让"吞得好不好"可量化。每次吞噬完成后运行, 产出评分:
  - 模式提取质量 (是否给全了 9 维度)
  - 裁决质量 (是否过双过滤: 未来证明 + 当前价值)
  - 落地质量 (是否给了最小可验证改动 + 测试建议)
  - License 合规 (是否标注)

评分 < 60 → 标记"需重做" (质量门禁)

用法:
  uv run python -m scripts.devour_scorecard --report <吞噬报告路径>
  uv run python -m scripts.devour_scorecard --report docs/deep-analysis.md --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── 评分维度 (与 harness-devour skill 对齐) ──
DIMENSIONS = [
    {
        "key": "phase0_summary",
        "label": "Phase 0 摘要 (License/定位/规模)",
        "weight": 10,
        "checks": [
            (r"License|MIT|Apache|PolyForm", "标注了 License"),
            (r"定位|核心卖点|是什么", "有定位描述"),
        ],
    },
    {
        "key": "phase1_architecture",
        "label": "Phase 1 架构拆解",
        "weight": 20,
        "checks": [
            (r"架构|Architecture|架构图", "有架构描述"),
            (r"循环|loop|Loop", "有核心循环"),
            (r"组件|组件清单|Orchestrator|Planner|Executor|Memory", "有组件清单"),
            (r"数据流|状态|持久化|恢复", "有数据流/状态"),
            (r"不变量|关键不变量|cache-first|single-writer", "有不变量"),
        ],
    },
    {
        "key": "phase2_patterns",
        "label": "Phase 2 模式提取 (9 维度)",
        "weight": 25,
        "checks": [
            (r"模式 1|### 模式 1|## 模式 1|模式提取", "有模式提取章节"),
            (r"原实现|原位置|实现位置", "标注了原实现位置"),
            (r"可迁移|迁移建议|接口建议", "给了迁移建议"),
            (r"潜在坑|陷阱|风险", "标注了坑"),
            (r"编排|Multi-Agent|Graph", "覆盖编排维度"),
            (r"记忆|Memory", "覆盖记忆维度"),
            (r"沙箱|Sandbox|隔离", "覆盖沙箱维度"),
            (r"上下文|Context|compact|Compaction", "覆盖上下文维度"),
            (r"恢复|Checkpoint|WAL|recovery", "覆盖恢复维度"),
            (r"证据|验收|Artifact|evidence", "覆盖证据交付"),
        ],
    },
    {
        "key": "phase3_comparison",
        "label": "Phase 3 对比矩阵",
        "weight": 15,
        "checks": [
            (r"对比|矩阵|comparison", "有对比矩阵"),
            (r"最值得.*(迁移|先做)|迁移.*3|3.*模式", "给出最值得迁移的模式"),
            (r"冲突点|冲突|不兼容|风险", "指出冲突点"),
        ],
    },
    {
        "key": "phase4_adaptation",
        "label": "Phase 4 适配方案",
        "weight": 15,
        "checks": [
            (r"最小.*改动|PR|diff|骨架|skeleton|接口", "给了最小改动方案"),
            (r"测试|验证|如何验证", "有测试建议"),
            (r"迁移|Checklist|清单", "有迁移清单"),
        ],
    },
    {
        "key": "phase5_iteration",
        "label": "Phase 5 迭代沉淀",
        "weight": 5,
        "checks": [
            (r"下一轮|下一步|深化方向", "有下一步方向"),
        ],
    },
    {
        "key": "verdict_filter",
        "label": "双过滤裁决",
        "weight": 10,
        "checks": [
            (r"未来证明|模型变强|Future", "过了未来证明测试"),
            (r"裁决|值得|观察|不做|迁移", "有明确裁决"),
            (r"试点|客户价值|当前价值|价值", "过了当前价值过滤"),
        ],
    },
]


def score_report(report_path: Path) -> dict:
    """评分一份吞噬报告"""
    text = report_path.read_text(encoding="utf-8", errors="ignore")

    results: dict[str, dict] = {}
    total_score = 0.0
    total_weight = 0
    passed_checks = 0
    total_checks = 0

    for dim in DIMENSIONS:
        hits: list[str] = []
        for pattern, label in dim["checks"]:
            total_checks += 1
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(label)
                passed_checks += 1
        weight = float(dim["weight"])
        dim_score = len(hits) / len(dim["checks"]) * weight
        total_score += dim_score
        total_weight += int(weight)
        results[dim["key"]] = {
            "label": dim["label"],
            "weight": dim["weight"],
            "score": round(dim_score, 1),
            "hits": hits,
            "missing": [c[1] for c in dim["checks"] if c[1] not in hits],
        }

    final_score = round(total_score / total_weight * 100, 1)
    verdict = "✅ 通过" if final_score >= 60 else "❌ 需重做"
    return {
        "report": report_path.name,
        "score": final_score,
        "verdict": verdict,
        "dimensions": results,
        "stats": {
            "checks_passed": passed_checks,
            "checks_total": total_checks,
            "coverage": round(passed_checks / total_checks * 100, 1),
        },
    }


def print_report(r: dict) -> None:
    print(f"\n{'='*56}")
    print(f"  吞噬评分卡: {r['report']}")
    print(f"  总分: {r['score']}/100 → {r['verdict']}")
    print(f"  覆盖: {r['stats']['checks_passed']}/{r['stats']['checks_total']} 检查项 ({r['stats']['coverage']}%)")
    print(f"{'='*56}")
    for dim in r["dimensions"].values():
        mark = "✅" if dim["score"] >= dim["weight"] * 0.6 else ("⚠️" if dim["score"] >= dim["weight"] * 0.3 else "❌")
        print(f"  {mark} {dim['label']}: {dim['score']}/{dim['weight']}")
        if dim["missing"]:
            print(f"     缺: {', '.join(dim['missing'][:3])}")


def main():
    parser = argparse.ArgumentParser(description="吞噬评分卡")
    parser.add_argument("--report", required=True, help="吞噬报告路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"❌ 报告不存在: {path}")
        sys.exit(1)

    result = score_report(path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result["score"] >= 60 else 1)


if __name__ == "__main__":
    main()
