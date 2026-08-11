"""
finops.py — Agent 成本核算模块 (Python 移植自 wanman/finops)

从 wanman 的 finops 包移植核心逻辑:
  - cost-model.ts     → estimate_costs_from_usage()
  - ledger.ts         → summarize_finops()
  - money.ts          → round_money() / from_minor_units()
  - pricing-registry.ts → DEFAULT_PRICING_REGISTRY + refresh pricing

适配: 中国国产模型优先 (DeepSeek/GLM/Qwen/MiniMax) + OpenRouter 兜底
用途: 统计 Hermes/agent 管道每月 token 成本 (Pattern 16 落地)
纯标准库, 零外部依赖。
"""

from __future__ import annotations

import copy
import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# money.py — 金额处理
# ═══════════════════════════════════════════════════════════════════

ZERO_DECIMAL_CURRENCIES = {
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
    "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
}


def normalize_currency(currency: str) -> str:
    return currency.strip().lower()


def minor_unit_factor(currency: str) -> int:
    return 1 if normalize_currency(currency) in ZERO_DECIMAL_CURRENCIES else 100


def from_minor_units(amount: float, currency: str) -> float:
    return amount / minor_unit_factor(currency)


def round_money(amount: float) -> float:
    """四舍五入到 4 位小数 (匹配 TS 版 Number.EPSILON 行为)"""
    return round(amount + 1e-12, 4)


# ═══════════════════════════════════════════════════════════════════
# types.py — 数据结构 (dataclass + dict 兼容)
# ═══════════════════════════════════════════════════════════════════

PROVIDERS = [
    "anthropic", "aws", "azure-openai", "cloudflare", "database", "discord",
    "github", "google", "line", "openai", "openai-compatible", "openrouter",
    "redis", "resend", "sendgrid", "sentry", "slack", "stripe", "supabase",
    "twilio", "vercel", "deepseek", "glm", "qwen", "minimax", "unknown",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ═══════════════════════════════════════════════════════════════════
# cost-model.py — 用量 → 成本估算
# ═══════════════════════════════════════════════════════════════════

def cost_model_key(provider: str, metric: str, unit: str, sku: str = "") -> str:
    """(provider, sku, metric, unit) 唯一键 — 加 sku 避免同 provider 多模型冲突"""
    return f"{provider}:{sku}:{metric}:{unit}".lower()


def estimate_costs_from_usage(
    usage: list[dict],
    models: list[dict],
    company_id: str,
    source: str | None = None,
) -> list[dict]:
    """usage 条目按 (provider, sku/model, metric, unit) 匹配价目表, 估算成本

    usage 条目带 model 字段时优先精确匹配 sku; 无 model 时退回 (provider, metric, unit) 匹配 (取第一条)。
    """
    models_by_key = {
        cost_model_key(m["provider"], m["metric"], m["unit"], m.get("sku", "")): m for m in models
    }
    # 无 sku 的宽松索引 (取第一条, 与 TS 原版行为一致)
    loose_by_key: dict[str, list[dict]] = {}
    for m in models:
        loose_by_key.setdefault(
            cost_model_key(m["provider"], m["metric"], m["unit"]), []
        ).append(m)

    costs: list[dict] = []
    for item in usage:
        model = None
        if item.get("model"):
            model = models_by_key.get(
                cost_model_key(
                    item.get("provider", ""), item.get("metric", ""),
                    item.get("unit", ""), item.get("model", ""),
                )
            )
        if model is None:
            loose = loose_by_key.get(
                cost_model_key(item.get("provider", ""), item.get("metric", ""), item.get("unit", ""))
            )
            if loose:
                model = loose[0]
        if not model:
            continue
        costs.append({
            "id": f"estimated:{item['id']}:{model['id']}",
            "provider": item.get("provider", ""),
            "companyId": item.get("companyId") or company_id,
            "productId": item.get("productId"),
            "amount": round_money(float(item.get("quantity", 0)) * float(model["unitPrice"])),
            "currency": model["currency"],
            "startTime": item.get("startTime"),
            "endTime": item.get("endTime"),
            "source": source or f"cost-model:{model['id']}",
            "category": model.get("service"),
            "usageMetric": item.get("metric"),
            "providerProjectId": item.get("providerProjectId"),
            "lineItem": model.get("service"),
            "raw": {"usageEntryId": item["id"], "costModelId": model["id"]},
        })
    return costs


# ═══════════════════════════════════════════════════════════════════
# ledger.py — 成本/收入汇总 → ROI / 盈亏
# ═══════════════════════════════════════════════════════════════════

def summarize_finops(costs: list[dict], revenue: list[dict], company_id: str) -> dict:
    """按 company 和 product 两个维度汇总, 计算 ROI 和盈亏"""
    return {
        "generatedAt": now_iso(),
        "companyId": company_id,
        "byCompany": _summarize_groups(costs, revenue, lambda e: f"{e['companyId']}:{e['currency']}"),
        "byProduct": _summarize_groups(
            costs, revenue,
            lambda e: f"{e['companyId']}:{e.get('productId')}:{e['currency']}",
        ),
    }


def _summarize_groups(costs: list[dict], revenue: list[dict], key_for) -> list[dict]:
    groups: dict[str, dict] = {}
    for entry in costs:
        key = key_for(entry)
        group = _ensure_group(groups, key, entry["companyId"], entry.get("productId"), entry["currency"])
        group["cost"] += float(entry["amount"])
    for entry in revenue:
        key = key_for(entry)
        group = _ensure_group(groups, key, entry["companyId"], entry.get("productId"), entry["currency"])
        group["revenue"] += float(entry["amount"])
    result = [_finalize_group(g) for g in groups.values()]
    result.sort(key=lambda g: (g["companyId"], g.get("productId") or "", g["currency"]))
    return result


def _ensure_group(groups: dict, key: str, company_id: str, product_id: str | None, currency: str) -> dict:
    if key not in groups:
        groups[key] = {
            "companyId": company_id, "productId": product_id, "currency": currency,
            "revenue": 0.0, "cost": 0.0, "grossProfit": 0.0, "roi": None, "breakEven": False,
        }
    return groups[key]


def _finalize_group(group: dict) -> dict:
    revenue = round_money(group["revenue"])
    cost = round_money(group["cost"])
    gross_profit = round_money(revenue - cost)
    return {
        **group,
        "revenue": revenue,
        "cost": cost,
        "grossProfit": gross_profit,
        "roi": None if cost == 0 else round_money(gross_profit / cost),
        "breakEven": gross_profit >= 0,
    }


# ═══════════════════════════════════════════════════════════════════
# pricing-registry.py — 价目表 (国产优先)
# ═══════════════════════════════════════════════════════════════════

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def _deepseek_rate(id_: str, sku: str, metric: str, unit_price: float, currency: str) -> dict:
    return {
        "id": id_, "provider": "deepseek", "service": "chat-completions", "sku": sku,
        "metric": metric, "unit": "1M tokens", "unitPrice": unit_price, "currency": currency,
        "pricingMethod": "public-rate-card",
        "sourceUrl": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing",
        "effectiveDate": "2026-07-31", "updateCadence": "weekly",
        "sourceCheckedAt": "2026-07-31T00:00:00.000Z",
    }


def _openrouter_rate(id_: str, sku: str, metric: str, unit_price: float, effective_date: str = "2026-07-31") -> dict:
    return {
        "id": id_, "provider": "openrouter", "service": "chat-completions", "sku": sku,
        "metric": metric, "unit": "token", "unitPrice": unit_price, "currency": "USD",
        "pricingMethod": "public-metadata-api", "sourceUrl": OPENROUTER_MODELS_URL,
        "effectiveDate": effective_date, "updateCadence": "daily",
        "sourceCheckedAt": "2026-07-31T00:00:00.000Z",
    }


# 价目表: 单位统一为 "每 1M token" 价格 (USD), 除 openrouter 是 "每 token"
DEFAULT_PRICING_REGISTRY: dict[str, Any] = {
    "generatedAt": "2026-07-31T00:00:00.000Z",
    "sources": [
        {"provider": "deepseek", "sourceUrl": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing", "checkedAt": "2026-07-31T00:00:00.000Z", "ok": True, "message": "Seeded from public DeepSeek pricing."},
        {"provider": "openrouter", "sourceUrl": OPENROUTER_MODELS_URL, "checkedAt": "2026-07-31T00:00:00.000Z", "ok": True, "message": "Seeded from public OpenRouter models metadata API."},
    ],
    "entries": [
        # DeepSeek (人民币计价, 官方 API 价格: 输入￥2/1M, 缓存命中￥0.5/1M, 输出￥8/1M — 2026-07)
        _deepseek_rate("deepseek:deepseek-chat:input", "deepseek-chat", "input_tokens", 0.28, "CNY"),      # ￥2/1M
        _deepseek_rate("deepseek:deepseek-chat:cached-input", "deepseek-chat", "cached_input_tokens", 0.07, "CNY"),  # ￥0.5/1M
        _deepseek_rate("deepseek:deepseek-chat:output", "deepseek-chat", "output_tokens", 1.12, "CNY"),    # ￥8/1M
        _deepseek_rate("deepseek:deepseek-reasoner:input", "deepseek-reasoner", "input_tokens", 0.56, "CNY"),   # ￥4/1M
        _deepseek_rate("deepseek:deepseek-reasoner:output", "deepseek-reasoner", "output_tokens", 2.24, "CNY"), # ￥16/1M
        # OpenRouter (USD 每 token)
        _openrouter_rate("openrouter:deepseek/deepseek-chat:prompt", "deepseek/deepseek-chat", "input_tokens", 0.00000028),
        _openrouter_rate("openrouter:deepseek/deepseek-chat:completion", "deepseek/deepseek-chat", "output_tokens", 0.00000112),
        _openrouter_rate("openrouter:anthropic/claude-sonnet-4:prompt", "anthropic/claude-sonnet-4", "input_tokens", 0.000003),
        _openrouter_rate("openrouter:anthropic/claude-sonnet-4:completion", "anthropic/claude-sonnet-4", "output_tokens", 0.000015),
    ],
}


def refresh_provider_pricing(
    include_openrouter: bool = True,
    openrouter_model_limit: int = 200,
    timeout: int = 15,
) -> dict:
    """刷新 OpenRouter 模型价目表 (在线), 失败时退回默认注册表"""
    registry = copy.deepcopy(DEFAULT_PRICING_REGISTRY)
    checked_at = now_iso()

    if include_openrouter:
        try:
            req = urllib.request.Request(OPENROUTER_MODELS_URL, headers={"User-Agent": "finops/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            entries: list[dict] = []
            for model in data.get("data", [])[:openrouter_model_limit]:
                pricing = model.get("pricing") or {}
                model_id = model.get("id", "")
                # OpenRouter pricing 是字符串 "0.00000175" 形式 (USD/token)
                prompt_price = _parse_price_str(pricing.get("prompt"))
                completion_price = _parse_price_str(pricing.get("completion"))
                if prompt_price is not None:
                    entries.append(_openrouter_rate(
                        f"openrouter:{model_id}:prompt", model_id, "input_tokens", prompt_price, checked_at[:10]))
                if completion_price is not None:
                    entries.append(_openrouter_rate(
                        f"openrouter:{model_id}:completion", model_id, "output_tokens", completion_price, checked_at[:10]))
            if entries:
                registry["entries"] = [e for e in registry["entries"] if e["provider"] != "openrouter"] + entries
                for s in registry["sources"]:
                    if s["provider"] == "openrouter":
                        s.update({"checkedAt": checked_at, "ok": True})
        except Exception as e:
            for s in registry["sources"]:
                if s["provider"] == "openrouter":
                    s.update({"checkedAt": checked_at, "ok": False, "message": str(e)})

    registry["generatedAt"] = checked_at
    return registry


def _parse_price_str(value) -> float | None:
    """'0.00000175' → 0.00000175; '' / None → None"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════
# 便捷封装: Hermes 成本报告
# ═══════════════════════════════════════════════════════════════════

def render_cost_report(costs: list[dict], summary: dict) -> str:
    """生成人类可读的成本报告 (对应 wanman finops CLI 输出)"""
    lines = ["## Agent 成本报告", ""]

    # 总成本
    total = round_money(sum(c.get("amount", 0) for c in costs))
    lines.append(f"**总成本: {total}**")
    lines.append("")

    # 按 provider 分组
    by_provider: dict[str, float] = {}
    for c in costs:
        by_provider[c["provider"]] = by_provider.get(c["provider"], 0) + float(c["amount"])
    lines.append("### 按 Provider")
    for provider, amount in sorted(by_provider.items(), key=lambda x: -x[1]):
        lines.append(f"- {provider}: {round_money(amount)}")
    lines.append("")

    # 按产品汇总 (ROI)
    lines.append("### 按产品 (ROI)")
    for g in summary.get("byProduct", []):
        roi = f"{g['roi']:.2f}" if g["roi"] is not None else "N/A"
        lines.append(
            f"- {g.get('productId', '(未归组)')}: 成本 {g['cost']} / 收入 {g['revenue']} "
            f"/ ROI {roi} / {'✅ 盈亏平衡' if g['breakEven'] else '❌ 亏损'}"
        )
    lines.append("")
    lines.append(f"*生成时间: {now_iso()}*")
    return "\n".join(lines)
