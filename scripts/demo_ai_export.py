"""
scripts/demo_ai_export.py — AI 出海科技公司 10 题演示脚本

演示定位: "AI 出海科技公司的合规问答系统"
  全局库 (57 文档法规+情报) → 出海法规能力
  客户库 (acme 3 文档) → 客户文档能力

用法:
  uv run python -m scripts.demo_ai_export           # 全量 10 题
  uv run python -m scripts.demo_ai_export --quick   # 前 6 题 (快速版)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 全局库问题 (出海法规能力) — 来自现有 57 文档
GLOBAL_QUESTIONS = [
    ("AI 产品出口欧盟需要满足什么标识要求？",
     "欧盟 AI 法案 Art.50 标识要求"),
    ("中国 AI 公司出海, 算法备案有什么影响？",
     "2026 算法备案新规 + Gartner 预测"),
    ("深度合成 AI 产品在欧洲和中国标识要求有何不同？",
     "欧盟灵活标识 vs 中国双重标识"),
    ("AI 训练数据有哪些合规要求？",
     "训练数据来源/清洗/敏感数据"),
    ("数据跨境传输有哪些限制？",
     "数据出境评估/安全审查/分级"),
]

# 客户库问题 (acme 出海文档) — 模拟客户自己的制度
CUSTOMER_QUESTIONS = [
    ("我们公司出海产品什么时候要做合规评估？",
     "acme: AI产品出海合规管理制度 第二章"),
    ("面向欧盟市场的数据存储有什么要求？",
     "acme: 出海产品数据安全手册 第一章"),
    ("AI 生成内容在欧盟怎么标识？",
     "acme: 出海合规管理制度 第四章"),
    ("训练数据能用爬取的数据吗？",
     "acme: 数据安全手册 第三章"),
    ("出海产品发生数据泄露要多久通知？",
     "acme: 数据安全手册 第五章 GDPR 72小时"),
    # 场景 10 (企业第二大脑): 决策建议型 — 跨文档聚合
    ("根据我们公司的制度, 如果计划进入欧盟市场, 需要完成哪些合规动作？",
     "acme: 合规评估/数据本地化/标识/隐私政策"),
    # 场景 5 (合同审查): 风险条款识别 + 缺失条款提示
    ("这份销售合同里, 哪些条款对卖方不利？",
     "acme: 销售合同 付款/违约金/知识产权/争议管辖"),
    ("这份合同缺少哪些常见必备条款？",
     "acme: 销售合同 不可抗力/质量异议期限"),
]


def run_one(query: str, expect: str, customer: bool = False) -> dict:
    """跑一个问题, 返回结果摘要"""
    from compliance_qa import answer, set_customer_db

    if customer:
        set_customer_db("acme")
    else:
        set_customer_db(None)

    t0 = time.time()
    resp = answer(query, top_k=8 if customer else 5)  # 客户库小块分散, 加大召回
    ms = (time.time() - t0) * 1000

    # 判断是否命中期望 (引用数 + 期望关键词)
    citations = resp.count("文档:")
    hit = any(k in resp for k in expect.split("|")[0].split("/")[:1]) or citations > 0
    return {
        "query": query, "expect": expect, "ms": ms,
        "citations": citations, "hit": hit, "answer_head": resp[:120],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="只跑前 6 题")
    args = parser.parse_args()

    print("=" * 62)
    print(f"  AI 出海科技公司 — 合规问答演示 ({len(GLOBAL_QUESTIONS) + len(CUSTOMER_QUESTIONS)} 题)")
    print(f"  全局库: 57 文档 (法规+情报) | 客户库: acme 4 文档 (含销售合同)")
    print("=" * 62)

    qs = GLOBAL_QUESTIONS + CUSTOMER_QUESTIONS
    if args.quick:
        qs = qs[:6]

    passed = 0
    for i, (q, expect) in enumerate(qs, 1):
        customer = i > len(GLOBAL_QUESTIONS)
        r = run_one(q, expect, customer)
        mark = "✅" if r["hit"] else "⚠️"
        if r["hit"]:
            passed += 1
        print(f"\n{mark} [{i}/{len(qs)}] ({'客户库' if customer else '全局库'}) {q}")
        print(f"   期望: {expect}")
        print(f"   引用: {r['citations']} | 耗时: {r['ms']:.0f}ms")
        print(f"   回答: {r['answer_head']}...")

    print(f"\n{'='*62}")
    print(f"  结果: {passed}/{len(qs)} 命中")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
