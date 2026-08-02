"""
scripts/eval_compliance.py — 合规 RAG 评测

对一组测试问题跑 RAG, 记录:
  - 回答是否命中知识库 (有引用)
  - 引用块数量与相似度
  - 回答长度 / 耗时 / 成本估算

用法:
  uv run python -m scripts.eval_compliance           # 全部问题
  uv run python -m scripts.eval_compliance --json    # JSON 输出
  uv run python -m scripts.eval_compliance --q "算法备案"  # 单个问题
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


from compliance_qa import retrieve

# ── 测试问题集 (覆盖不同难度) ─────────────────────────────────────────
TEST_QUESTIONS = [
    # 简单: 文档标题直接命中
    "算法备案的要求是什么",
    "生成式AI服务的训练数据合规要求",
    "AI Agent 需要什么治理框架",
    # 中等: 需要跨文档检索
    "跨境数据传输有什么限制",
    "深度合成内容需要标识吗",
    "企业使用AI工具的内部政策要点",
    # 难: 需要语义理解 + 多块组装
    "NIST AI RMF 的风险管理流程是怎么运作的",
    "中小企业本地部署大模型的准备度评估怎么做",
    "AI 透明度与可解释性在中国法规下的要求",
    "AI 治理中的董事会责任和风险管理",
]

from compliance_qa import compile_context


def eval_one(query: str, top_k: int = 3) -> dict:
    """评测单问题 — 对比 原始检索 vs Context Compiler"""
    # 原始检索
    t0 = time.time()
    raw = retrieve(query, top_k)
    raw_ms = (time.time() - t0) * 1000

    # Context Compiler
    t1 = time.time()
    compiled = compile_context(query, top_k)
    compile_ms = (time.time() - t1) * 1000

    raw_sim = sum(c["hits"] for c in raw) / max(len(raw), 1) if raw else 0
    comp_sim = sum(c["hits"] for c in compiled) / max(len(compiled), 1) if compiled else 0

    return {
        "query": query,
        "raw": {
            "chunks": len(raw),
            "docs": len({c["doc"] for c in raw}),
            "avg_sim": round(raw_sim, 3),
            "ms": round(raw_ms, 1),
        },
        "compiled": {
            "chunks": len(compiled),
            "docs": len({c["doc"] for c in compiled}),
            "avg_sim": round(comp_sim, 3),
            "ms": round(compile_ms, 1),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", help="单个问题 (默认跑全部)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    questions = [args.q] if args.q else TEST_QUESTIONS

    results = []
    for q in questions:
        r = eval_one(q)
        results.append(r)
        if not args.json:
            raw, comp = r["raw"], r["compiled"]
            delta_ms = comp["ms"] - raw["ms"]
            delta_docs = comp["docs"] - raw["docs"]
            print(f"Q: {q}")
            print(f"   原始: {raw['chunks']}块/{raw['docs']}文档  sim={raw['avg_sim']}  {raw['ms']:.0f}ms")
            print(f"   编译: {comp['chunks']}块/{comp['docs']}文档  sim={comp['avg_sim']}  {comp['ms']:.0f}ms  "
                  f"(Δ{delta_ms:+.0f}ms Δ{delta_docs:+d}doc)")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # 汇总对比
        avg_raw_sim = sum(r["raw"]["avg_sim"] for r in results) / max(len(results), 1)
        avg_comp_sim = sum(r["compiled"]["avg_sim"] for r in results) / max(len(results), 1)
        avg_raw_docs = sum(r["raw"]["docs"] for r in results) / max(len(results), 1)
        avg_comp_docs = sum(r["compiled"]["docs"] for r in results) / max(len(results), 1)
        avg_raw_ms = sum(r["raw"]["ms"] for r in results) / max(len(results), 1)
        avg_comp_ms = sum(r["compiled"]["ms"] for r in results) / max(len(results), 1)
        print(f"\n=== 汇总对比 ({len(results)} 问题) ===")
        print(f"平均相似度:  原始 {avg_raw_sim:.3f} → 编译 {avg_comp_sim:.3f}  ({avg_comp_sim-avg_raw_sim:+.3f})")
        print(f"平均文档数:  原始 {avg_raw_docs:.1f} → 编译 {avg_comp_docs:.1f}  ({avg_comp_docs-avg_raw_docs:+.1f})")
        print(f"平均耗时:    原始 {avg_raw_ms:.0f}ms → 编译 {avg_comp_ms:.0f}ms")


if __name__ == "__main__":
    main()
