"""
pulse/extractors/dap_enrich.py — dap LLM 提取增强适配器 (Pulse 接入点)

用途: 给采集到的岗位/作品做语义增强 (AI 岗位识别 / 技能提取 / 合规风险评估),
     字段级溯源 (每个增强字段带原文依据 + 置信度).

设计:
  - 纯增量: 只在 raw 数据上增加 _ai_* 字段, 不改变原有 Data Contract
  - 可开关: DAP_ENRICH=0 关闭 (默认开), 无 key 时自动跳过
  - 成本控制: 信息觅食式 — 只对高价值记录 (岗位含 AI/治理关键词) 增强

用法:
  from pulse.extractors.dap_enrich import enrich_records
  raw = enrich_records(raw)   # 返回带 _ai_* 字段的列表
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("pulse.dap_enrich")

DAP_ROOT = Path(os.environ.get("DAP_ROOT", "/root/harness-lab/data-acquisition-pipeline"))
if str(DAP_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(DAP_ROOT / "src"))

# AI 治理/岗位相关关键词 — 只增强高价值记录 (成本控制)
AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "llm",
    "machine learning",
    "ml",
    "大模型",
    "人工智能",
    "算法",
    "gpt",
    "deepseek",
    "agent",
    "governance",
    "compliance",
    "治理",
    "合规",
)

_ENRICH_SCHEMA = {
    "is_ai_role": "bool",
    "ai_skills": "list[str]",
    "compliance_relevance": "str",
    "rationale": "str",
}


def _should_enrich(record: dict) -> bool:
    """信息觅食式筛选: 只增强含 AI 关键词的记录."""
    text = " ".join(str(v) for v in record.values())[:2000].lower()
    return any(kw in text for kw in AI_KEYWORDS)


def enrich_records(records: list[dict], max_records: int = 20) -> list[dict]:
    """批量增强. 返回原列表 (原地加 _ai_* 字段). 失败不影响原数据."""
    if os.environ.get("DAP_ENRICH", "1") != "1":
        return records
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.info("[dap_enrich] 无 DEEPSEEK_API_KEY — 跳过增强")
        return records

    try:
        from dap.extractors.llm_extractor import LLMExtractor
    except ImportError as e:
        logger.warning(f"[dap_enrich] dap 不可用 ({e}) — 跳过")
        return records

    ex = LLMExtractor(api_key=api_key, max_tokens=1024)
    enriched = 0
    for rec in records:
        if enriched >= max_records:
            break
        if not _should_enrich(rec):
            continue
        content = f"岗位: {rec.get('job_title', rec.get('title', ''))}\n公司: {rec.get('company', '')}\n描述: {rec.get('description', rec.get('job_description', ''))[:800]}"
        try:
            result = ex.extract(_ENRICH_SCHEMA, content, rec.get("url", ""))
            if result.data:
                rec["_ai_enhanced"] = True
                rec["_ai_confidence"] = result.confidence
                rec["_ai_token_usage"] = result.token_usage
                rec["_ai_cost_usd"] = result.cost_usd
                for k, v in result.data.items():
                    rec[f"_ai_{k}"] = v
                enriched += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[dap_enrich] 单条增强失败: {e}")
    if enriched:
        logger.info(
            f"[dap_enrich] 增强 {enriched} 条 (总成本 ${sum(r.get('_ai_cost_usd', 0) for r in records):.4f})"
        )
    return records
