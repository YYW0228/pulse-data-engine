"""scripts/kb_gap.py — 知识库补料缺口扫描器 (零 LLM, 补料流水线半自动化)

补料闭环 (半自动):
  1. [自动] kb_gap 扫描 golden 期望词 → 定位知识缺口 (sim < 阈值 = 主题无文档覆盖)
  2. [人工] 按报告补文档 → 放入 china-ai-governance 对应 references/
  3. [自动] kb_refresh --no-scrape 入库 (04:00 cron 或手动)
  4. [自动] golden_eval 复评命中率

用法:
  uv run python scripts/kb_gap.py                 # 扫描 golden_set 期望词缺口 → data/kb_gap_report.md
  uv run python scripts/kb_gap.py --json          # stdout JSON (供管道/CI)
  uv run python scripts/kb_gap.py --set custom.json  # 自定义题目集 {question, expect}

判定:
  - 知识缺口: expect 词检索最高相似度 < SIM_THRESHOLD (0.52) → 知识库无该主题
  - 覆盖缺口: 有料 (sim >= 阈值) 但 golden 命中率低 → prompt/期望词问题, 非补料
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET = ROOT / "data" / "golden_set.json"
REPORT = ROOT / "data" / "kb_gap_report.md"
DEFAULT_THRESHOLD = 0.52  # 与 compliance_qa.SIM_THRESHOLD 对齐


def load_golden(path: Path) -> list[dict]:
    """加载题目集 [{question, expect}]"""
    if not path.exists():
        print(f"❌ 题目集不存在: {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else data.get("questions", [])


def scan_gap(golden: list[dict], top_k: int = 5, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """扫描: 对每题 expect 词逐个检索, 输出缺口判定 (零 LLM, 只跑 embedding+检索)

    返回:
      {
        "scanned": N, "threshold": t,
        "concept_gaps": [{"question", "expect_word", "max_sim", "hits_docs"}],
        "question_gaps": [{"question", "hit_rate", "max_sim", "gap_type"}],
        "covered": M,
      }
    """
    from scripts.compliance_qa import retrieve  # 延迟导入 (加载 embedding)

    concept_gaps: list[dict] = []
    question_gaps: list[dict] = []
    covered = 0
    skipped_short = 0

    for q in golden:
        question = q["question"]
        expects = q.get("expect", [])
        q_max_sim = 0.0
        q_gaps = []

        for word in expects:
            # 短词 (<2 字符, 如 "K") embedding 不可靠, 跳过 (非知识缺口)
            if len(word) < 2:
                skipped_short += 1
                continue
            t0 = time.time()
            try:
                hits = retrieve(word, top_k=top_k)
            except Exception as exc:  # noqa: S110 — 单词检索失败不中断
                print(f"  ⚠️ 检索失败 [{word}]: {exc}", file=sys.stderr)
                continue
            max_sim = max((c.get("hits", 0.0) for c in hits), default=0.0)
            q_max_sim = max(q_max_sim, max_sim)
            docs = sorted({c.get("doc_name", "?") for c in hits if c.get("hits", 0) >= threshold})
            if max_sim < threshold:
                # 分级: <0.40 真知识缺口 (无料) | 0.40-阈值 边缘召回 (有料但相似度差)
                level = "gap" if max_sim < 0.40 else "edge"
                concept_gaps.append({
                    "question": question, "expect_word": word,
                    "max_sim": round(max_sim, 3), "hits_docs": docs,
                    "ms": round((time.time() - t0) * 1000), "level": level,
                })
                q_gaps.append(word)

        # 题型判定: 有概念缺口 → 知识缺口; 全覆盖 → 覆盖缺口 (非补料)
        if q_gaps:
            question_gaps.append({
                "question": question, "hit_rate": q.get("hit_rate", None),
                "max_sim": round(q_max_sim, 3), "gap_type": "knowledge",
                "missing": q_gaps,
            })
        else:
            covered += 1

    return {
        "scanned": len(golden),
        "threshold": threshold,
        "concept_gaps": concept_gaps,
        "question_gaps": question_gaps,
        "covered": covered,
        "skipped_short": skipped_short,
    }


def render_report(result: dict) -> str:
    """渲染补料报告 (markdown, 人工确认清单)"""
    gaps = result["concept_gaps"]
    qgaps = result["question_gaps"]
    lines = [
        "# 知识库补料缺口报告 (kb_gap)",
        "",
        f"> 生成: {time.strftime('%Y-%m-%d %H:%M:%S')} | 扫描 {result['scanned']} 题 | "
        f"阈值 sim ≥ {result['threshold']} | 跳过短词 {result.get('skipped_short', 0)}",
        f"> 流程: 本报告确认 → 补文档进 china-ai-governance references/ → "
        f"`uv run python -m scripts.kb_refresh --no-scrape` 入库 → golden_eval 复评",
        "",
        f"## 结论: {len(gaps)} 个概念缺口 / {len(qgaps)} 题受影响 / {result['covered']} 题知识覆盖完整",
        "",
        "## 概念缺口清单 (补料候选)",
        "",
        "> 分级: **gap** = 真知识缺口 (sim<0.40, 无料, 优先补) | **edge** = 边缘召回 (0.40~阈值, 有料但相似度差, 可补锚点词)",
        "",
        "| # | 期望词 (缺失主题) | 相关题目 | 最高相似度 | 级别 | 建议文档方向 | 状态 |",
        "|---|------------------|----------|-----------|------|-------------|------|",
    ]
    seen: set[str] = set()
    n = 0
    for g in sorted(gaps, key=lambda x: x["max_sim"]):
        if g["expect_word"] in seen:
            continue
        seen.add(g["expect_word"])
        n += 1
        # 建议: 从题目反推主题方向 (人工细化)
        hint = _suggest_direction(g["expect_word"], g["question"])
        level = "🔴 gap" if g["level"] == "gap" else "🟡 edge"
        lines.append(f"| {n} | {g['expect_word']} | {g['question'][:30]} | "
                     f"{g['max_sim']:.2f} | {level} | {hint} | pending |")
    lines += ["", "## 受影响题目", "", "| 题目 | 缺失概念 |", "|------|---------|"]
    for q in qgaps:
        lines.append(f"| {q['question'][:50]} | {', '.join(q['missing'])} |")
    lines += ["", "## 使用说明", "",
              "1. 核对清单, 对每个 pending 概念找权威来源 (法规原文/官方解读/行业标准)",
              "2. 写成 markdown 放 china-ai-governance 对应 references/ (参考 ai-safety-testing-baseline.md 格式: 标题+要点+快速问答摘要)",
              "3. 入库: `uv run python -m scripts.kb_refresh --no-scrape`",
              "4. 复评: `uv run python scripts/golden_eval.py` (前台, 必须) — 命中率应上升",
              ""]
    return "\n".join(lines)


def _suggest_direction(word: str, question: str) -> str:
    """从期望词+题目反推文档方向 (启发式, 人工细化)"""
    if "AI" in question or "AI" in word:
        return f"{word} 主题规范/指引文档"
    if "出海" in question or "跨境" in question:
        return f"{word} 跨境合规/数据出境文档"
    if "备案" in question:
        return f"{word} 备案细则文档"
    return f"{word} 专题文档 (法规原文/官方解读)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb_gap", description="知识库补料缺口扫描 (零 LLM)")
    parser.add_argument("--set", type=Path, default=GOLDEN_SET, help="题目集 JSON")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true", help="stdout 输出 JSON")
    parser.add_argument("--watchdog", action="store_true",
                        help="watchdog 模式: 仅存在真缺口 (level=gap) 时输出告警, 否则静默")
    args = parser.parse_args(argv)

    golden = load_golden(args.set)
    print(f"扫描 {len(golden)} 题 (期望词逐一检索, top_k={args.top_k}, "
          f"阈值 {args.threshold})...", file=sys.stderr)
    result = scan_gap(golden, top_k=args.top_k, threshold=args.threshold)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # watchdog: 真缺口 (level=gap) 存在才告警, 无则静默 (cron no_agent 语义)
    real_gaps = [g for g in result["concept_gaps"] if g["level"] == "gap"]
    if args.watchdog and not real_gaps:
        return 0

    report = render_report(result)
    REPORT.write_text(report)
    print(report)
    print(f"\n→ 报告已写入 {REPORT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
