"""生成 acme 演示证据包 — 给客户/销售的 10 题问答汇总 (markdown)

用法:
  uv run python -m scripts.demo_pack
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

QUESTIONS = [
    ("global", "AI 产品出口欧盟需要满足什么标识要求？", "欧盟 AI 法案 Art.50"),
    ("global", "中国 AI 公司出海, 算法备案有什么影响？", "双备案 + 出海合规"),
    ("global", "深度合成 AI 产品在欧洲和中国标识要求有何不同？", "欧盟灵活 vs 中国双重"),
    ("global", "AI 训练数据有哪些合规要求？", "第7-8条 训练数据"),
    ("global", "数据跨境传输有哪些限制？", "三条法定出境路径"),
    ("acme", "我们公司出海产品什么时候要做合规评估？", "立项阶段必评"),
    ("acme", "面向欧盟市场的数据存储有什么要求？", "本地化或 SCC"),
    ("acme", "AI 生成内容在欧盟怎么标识？", "AI 法案第50条"),
    ("acme", "训练数据能用爬取的数据吗？", "禁止未授权爬取"),
    ("acme", "出海产品发生数据泄露要多久通知？", "GDPR 72小时"),
]


def main() -> None:
    from scripts.compliance_qa import answer, set_customer_db

    out: list[str] = []
    out.append("# Acme 客户演示证据包 — AI 出海合规问答 (10/10)\n")
    out.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M')}")
    out.append("数据源: 全局法规库 (57 文档) + acme 客户库 (3 文档, 独立 DuckDB)\n")

    for scope, q, expect in QUESTIONS:
        if scope == "acme":
            set_customer_db("acme")
        else:
            set_customer_db(None)
        t0 = time.time()
        try:
            r = answer(q, top_k=3)
            ms = int((time.time() - t0) * 1000)
            # 有引用溯源即算命中 (回答长度不是质量判据 — 短而准确的回答也是对的)
            ok = ("[文档:" in r or "引用来源" in r) and "❌" not in r and "未找到" not in r
            out.append(f"## {q}\n")
            out.append(f"> 期望: {expect} | {'✅' if ok else '❌'} | {ms}ms\n")
            out.append(r.strip() + "\n")
        except Exception as e:
            out.append(f"## {q}\n\n❌ 错误: {e}\n")

    report = "\n".join(out)
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    path = Path("data/reports") / f"acme-demo-pack-{time.strftime('%Y%m%d')}.md"
    path.write_text(report, encoding="utf-8")
    print(f"✅ 证据包已生成: {path} ({len(report)} 字符, {len(QUESTIONS)} 题)")


if __name__ == "__main__":
    main()
