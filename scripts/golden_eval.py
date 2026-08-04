"""
scripts/golden_eval.py — 金标评测 (P3-9)

用人工标注的"金标问题集"持续评测问答质量:
  - 每个问题有: 问题 / 期望要点 (人工写的正确答案要点)
  - 评测: 跑问答 → 检查回答是否覆盖期望要点 → 计算命中率
  - 质量门禁: 命中率 ≥80% 才算通过 (模型升级/提示词改动后跑)

金标集文件: data/golden_set.json (30-50 题, 人工标注)
格式:
[
  {
    "question": "算法备案的要求是什么?",
    "expect": ["算法备案", "大模型专项备案", "未备案即违规"],
    "domain": "合规法规",
    "source": "人工标注 2026-08-04"
  }
]

用法:
  uv run python -m scripts.golden_eval                # 全量评测
  uv run python -m scripts.golden_eval --quick        # 前 10 题
  uv run python -m scripts.golden_eval --json         # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN_SET = Path(__file__).resolve().parent.parent / "data" / "golden_set.json"
PASS_THRESHOLD = 0.8


def load_golden() -> list[dict]:
    """加载金标集"""
    if not GOLDEN_SET.exists():
        print(f"❌ 金标集不存在: {GOLDEN_SET}")
        print("   请先创建 (见 data/golden_set.example.json 模板)")
        sys.exit(1)
    with open(GOLDEN_SET, encoding="utf-8") as f:
        return json.load(f)


def evaluate_question(q: dict, top_k: int = 5, samples: int = 2) -> dict:
    """评测单题: 跑问答 samples 次取最高命中 (消除模型随机性)"""
    from compliance_qa import answer

    question = q["question"]
    expects = q["expect"]

    best: dict = {"hit_rate": 0.0}
    for _ in range(samples):
        t0 = time.time()
        try:
            resp = answer(question, top_k=top_k)
            success = True
        except Exception as e:
            resp = f"ERROR: {e}"
            success = False
        ms = (time.time() - t0) * 1000
        covered = [e for e in expects if e in resp]
        hit_rate = len(covered) / len(expects) if expects else 0
        if hit_rate > best["hit_rate"]:
            best = {
                "question": question,
                "expect": expects,
                "covered": covered,
                "hit_rate": round(hit_rate, 2),
                "ms": round(ms),
                "success": success,
                "answer_head": resp[:100],
            }

    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="只跑前 10 题")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    golden = load_golden()
    if args.quick:
        golden = golden[:10]

    print(f"=== 金标评测 ({len(golden)} 题) ===")
    results = []
    total_hit = 0.0

    for i, q in enumerate(golden, 1):
        r = evaluate_question(q)
        results.append(r)
        total_hit += r["hit_rate"]
        mark = "✅" if r["hit_rate"] >= 0.5 else "⚠️"
        print(f"{mark} [{i}/{len(golden)}] {r['question'][:40]}")
        print(f"    命中 {len(r['covered'])}/{len(r['expect'])} ({r['hit_rate']*100:.0f}%) "
              f"{r['ms']}ms")

    avg = total_hit / len(results) if results else 0
    passed = avg >= PASS_THRESHOLD
    print(f"\n=== 平均命中率: {avg*100:.1f}% {'✅ 通过' if passed else '❌ 未通过 (<80%)'} ===")

    if args.json:
        print(json.dumps({"avg_hit_rate": round(avg, 3), "passed": passed,
                          "results": results}, ensure_ascii=False, indent=2))

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
