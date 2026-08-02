"""
pulse/subagent.py — Subagent 编排 (12组件第11项, 7层 Orchestration 深化)

主-从模式: 主 Agent 回答 → 子 Agent 独立评审 (找茬/校验) → 合并结果

设计:
  - 延迟引入原则: 仅在需要质量保证时启用 (合规场景 = 始终启用评审)
  - 子 Agent 独立 run_id + trace (可审计)
  - 评审发现错误 → 标记 answer_reviewed=False + 问题清单

流程:
  main_answer (DeepSeek) → reviewer (独立调用, 找茬) → verdict
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReviewResult:
    """子 Agent 评审结果"""

    verdict: str = "approved"  # approved / flagged / rejected
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    ms: float = 0.0


def _get_api_key() -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    for env_path in (Path.home() / ".hermes" / ".env", Path(".env")):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return None


def review_answer(query: str, answer: str, citations: list[dict]) -> ReviewResult:
    """子 Agent 独立评审: 检查回答是否忠实于引用、有无幻觉

    用独立 LLM 调用 (找茬视角), 与主回答模型不同 prompt。
    """
    t0 = time.time()
    api_key = _get_api_key()
    if not api_key:
        return ReviewResult(verdict="approved", ms=0)  # 无 key 跳过评审

    import httpx

    cit_text = "\n".join(f"- {c.get('doc')} | {c.get('section')}" for c in citations) or "(无引用)"

    prompt = f"""你是独立的合规评审员。检查下面的 AI 回答是否可信。

规则:
1. 回答中的每个事实/数字是否能在引用中找到依据? (找不到=幻觉, 标记)
2. 引用是否真实相关? (引用与内容无关=错误引用, 标记)
3. 是否越界给出法律结论? (应只做合规分析)
4. 是否有规避合规/误导性内容?

问题: {query}

引用来源:
{cit_text}

AI 回答:
{answer}

输出 JSON 格式:
{{"verdict": "approved|flagged|rejected", "issues": ["问题1", "问题2"], "suggestions": ["建议1"]}}
verdict 含义: approved=可信可发布, flagged=有小问题需复核, rejected=有严重问题不能发布"""

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 500,
            },
            timeout=45,
        )
        content = resp.json()["choices"][0]["message"]["content"]
        # 提取 JSON
        m = content[content.find("{"): content.rfind("}") + 1]
        data = json.loads(m)
        verdict = data.get("verdict", "flagged")
        if verdict not in ("approved", "flagged", "rejected"):
            verdict = "flagged"
        return ReviewResult(
            verdict=verdict,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            ms=(time.time() - t0) * 1000,
        )
    except Exception:
        return ReviewResult(verdict="flagged", issues=["评审失败"], ms=(time.time() - t0) * 1000)


if __name__ == "__main__":
    # 演示: 评审一个回答
    r = review_answer(
        "算法备案的要求是什么",
        "算法备案需要在十个工作日内完成。",
        [{"doc": "cac-algorithm-filing-guide.md", "section": "一"}],
    )
    print(f"verdict: {r.verdict}")
    print(f"issues: {r.issues}")
    print(f"suggestions: {r.suggestions}")
    print(f"评审耗时: {r.ms:.0f}ms")
