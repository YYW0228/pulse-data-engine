"""
scripts/meta_loop.py — Harness 自我进化 Meta-Loop

流程 (呼应 A5):
  1. 收集失败轨迹: compliance_metrics.jsonl + compliance_traces.jsonl
  2. 聚类失败模式: 按 error / 低引用 / 低置信 分组
  3. LLM 提出修改提案: 针对失败模式生成 prompt/策略改进建议
  4. 输出提案文件: .hermes/meta_loop_proposals.md (人工或自动晋升)

用法:
  uv run python -m scripts.meta_loop                 # 分析 + 提案
  uv run python -m scripts.meta_loop --dry           # 只分析不调 LLM
  uv run python -m scripts.meta_loop --auto-apply    # 提案自动写入 AGENTS 风格提示
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

METRICS_PATH = Path("data/compliance_metrics.jsonl")
TRACES_PATH = Path("data/compliance_traces.jsonl")
PROPOSALS_PATH = Path(".hermes/meta_loop_proposals.md")

# ── 失败模式启发式 ────────────────────────────────────────────────────


def analyze_failures(limit: int = 500) -> dict:
    """聚类失败模式"""
    if not METRICS_PATH.exists():
        return {"total": 0}

    records = []
    with METRICS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    records = records[-limit:]

    total = len(records)
    failed = [r for r in records if not r["success"]]
    low_citation = [r for r in records if r["success"] and r["citations"] < 2]
    slow = [r for r in records if r["ms"] > 10000]

    error_counter = Counter(r.get("error", "unknown") for r in failed)
    model_counter = Counter(r.get("model", "?") for r in records)

    return {
        "total": total,
        "failed": len(failed),
        "low_citation": len(low_citation),
        "slow": len(slow),
        "error_types": dict(error_counter.most_common(5)),
        "model_usage": dict(model_counter),
        "failed_queries": [r["query"] for r in failed[-5:]],
        "low_citation_queries": [r["query"] for r in low_citation[-3:]],
    }


def build_proposal_prompt(analysis: dict) -> str:
    """构建 Meta-Loop 提案 prompt"""
    return f"""你是 Agent Harness 自优化引擎。基于以下失败轨迹分析，提出 3-5 条可执行的 Harness 修改提案。

目标: 减少失败率, 提升回答质量, 控制成本。

## 失败分析

总问答: {analysis.get('total')}
失败: {analysis.get('failed')} (错误类型: {analysis.get('error_types')})
低引用(质量差): {analysis.get('low_citation')}
慢查询(>10s): {analysis.get('slow')}
模型分布: {analysis.get('model_usage')}

失败问题示例: {analysis.get('failed_queries')}
低引用问题示例: {analysis.get('low_citation_queries')}

## 提案要求

每条提案格式:
### 提案 N: <标题>
- **问题**: 对应哪个失败模式
- **修改**: 具体改什么 (prompt/路由阈值/检索参数/工具)
- **预期**: 量化预期效果
- **验证**: 如何 A/B 验证
- **风险**: 副作用

只提可落地、可验证的提案, 拒绝空泛建议。"""


def call_llm(prompt: str) -> str:
    """调用 DeepSeek 生成提案"""

    from compliance_qa import _get_api_key

    api_key = _get_api_key()
    if not api_key:
        return _fallback_proposals()

    from pulse.llm_audit import audited_post

    try:
        resp = audited_post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 1500,
            },
            timeout=60,
            source="meta_loop.call_llm",
        )
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"LLM 调用失败: {e}\n\n{_fallback_proposals()}"


def _fallback_proposals() -> str:
    """无 key 时的规则提案"""
    return """### 提案 1: 低引用问题 → 强化引用提示
- **问题**: 回答引用不足 (citations < 2)
- **修改**: prompt 规则2 增加"每个要点必须带引用, 无引用段落标记'推测'"
- **预期**: 引用率提升 50%
- **验证**: eval_compliance 对比
- **风险**: 回答变啰嗦

### 提案 2: no_chunks 失败 → 检索兜底
- **问题**: 检索零命中 (no_chunks)
- **修改**: 无命中时降级关键词 LIKE 检索 (BM25 风格)
- **预期**: 零命中率 -80%
- **验证**: adversarial_eval
- **风险**: 检索变慢

### 提案 3: 慢查询 → 小模型优先
- **问题**: >10s 查询占比高
- **修改**: 路由层复杂度阈值调低, 更多走 deepseek-chat
- **预期**: P95 下降 40%
- **验证**: compliance_metrics P95
- **风险**: 复杂问题质量下降"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只分析不调 LLM")
    parser.add_argument("--auto-apply", action="store_true", help="提案自动写入")
    args = parser.parse_args()

    analysis = analyze_failures()
    print(f"=== Meta-Loop 失败分析 ===")
    print(f"总问答: {analysis.get('total')} | 失败: {analysis.get('failed')} | "
          f"低引用: {analysis.get('low_citation')} | 慢: {analysis.get('slow')}")
    if analysis.get("error_types"):
        print(f"错误类型: {analysis['error_types']}")

    if analysis.get("total", 0) == 0:
        print("无数据 — 先跑一些问答")
        return

    if args.dry:
        print("\n[dry] 仅分析, 不生成提案")
        return

    prompt = build_proposal_prompt(analysis)
    print("\n生成提案中...")
    proposals = call_llm(prompt)

    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = f"# Meta-Loop 提案 ({time.strftime('%Y-%m-%d %H:%M')})\n\n分析: {analysis.get('total')} 问答, {analysis.get('failed')} 失败\n\n---\n\n"
    PROPOSALS_PATH.write_text(header + proposals, encoding="utf-8")
    print(f"✅ 提案已保存: {PROPOSALS_PATH}")
    print(f"\n{proposals[:800]}...")

    if args.auto_apply:
        print("\n[auto-apply] 提案已写入, 人工评审后合入 (不自动改代码)")


if __name__ == "__main__":
    main()
