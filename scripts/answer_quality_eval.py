"""
scripts/answer_quality_eval.py — 回答质量评测

对 10 个测试问题跑完整 LLM 回答, 输出报告供人工核验:
  - 是否基于资料 (引用完整)
  - 是否编造 (幻觉)
  - 回答完整度

用法:
  uv run python -m scripts.answer_quality_eval           # 全部, 存报告
  uv run python -m scripts.answer_quality_eval --q "..." # 单个
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compliance_qa import answer
from eval_compliance import TEST_QUESTIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", help="单个问题")
    parser.add_argument("--out", default="data/answer_quality_report.md")
    args = parser.parse_args()

    questions = [args.q] if args.q else TEST_QUESTIONS
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = ["# 合规问答回答质量评测报告", f"\n生成时间: {time.strftime('%Y-%m-%d %H:%M')}", ""]

    for q in questions:
        t0 = time.time()
        try:
            ans = answer(q)
            ms = (time.time() - t0) * 1000
            report.append(f"## Q: {q}\n")
            report.append(f"**耗时: {ms:.0f}ms**\n")
            report.append(ans)
            report.append("\n---\n")
            print(f"✅ Q: {q[:30]}... ({ms:.0f}ms)")
        except Exception as e:
            report.append(f"## Q: {q}\n\n**❌ 回答失败: {e}**\n\n---\n")
            print(f"❌ Q: {q[:30]}... ERROR: {e}")

    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\n报告已保存: {out_path}")


if __name__ == "__main__":
    main()
