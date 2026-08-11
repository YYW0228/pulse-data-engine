"""pulse/finops.py 测试 — Agent 成本核算 (纯 stdlib)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pulse.finops as f


def test_money_functions():
    assert f.round_money(1.005) == 1.005
    assert f.round_money(0.1 + 0.2) == 0.3
    assert f.minor_unit_factor("jpy") == 1
    assert f.minor_unit_factor("JPY") == 1  # 大小写归一
    assert f.minor_unit_factor("usd") == 100
    assert f.from_minor_units(100, "usd") == 1.0
    assert f.normalize_currency(" USD ") == "usd"


def test_cost_model_key():
    assert f.cost_model_key("DeepSeek", "input_tokens", "1M tokens", "deepseek-chat") == (
        "deepseek:deepseek-chat:input_tokens:1m tokens"
    )
    assert f.cost_model_key("openai", "output", "token") == "openai::output:token"


def test_estimate_costs_exact_sku():
    usage = [
        {"id": "u1", "provider": "deepseek", "model": "deepseek-chat",
         "metric": "input_tokens", "unit": "1M tokens", "quantity": 0.5,
         "companyId": "co1", "productId": "hermes"},
        {"id": "u2", "provider": "deepseek", "model": "deepseek-chat",
         "metric": "output_tokens", "unit": "1M tokens", "quantity": 0.2,
         "companyId": "co1", "productId": "hermes"},
    ]
    models = [m for m in f.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = f.estimate_costs_from_usage(usage, models, "co1")
    assert len(costs) == 2
    assert costs[0]["amount"] == 0.14  # 0.5 * 0.28 (￥2/1M)
    assert costs[1]["amount"] == 0.224  # 0.2 * 1.12 (￥8/1M)
    assert costs[0]["currency"] == "CNY"
    assert costs[0]["companyId"] == "co1"
    assert costs[0]["category"] == "chat-completions"
    assert costs[0]["raw"]["usageEntryId"] == "u1"


def test_estimate_costs_loose_and_skip():
    # 无 model 字段 → 宽松匹配 (provider+metric+unit 取第一条)
    usage = [{"id": "u3", "provider": "deepseek", "metric": "input_tokens",
              "unit": "1M tokens", "quantity": 1.0, "companyId": "co2"}]
    models = [m for m in f.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = f.estimate_costs_from_usage(usage, models, "co2")
    assert len(costs) == 1
    assert costs[0]["companyId"] == "co2"  # usage 无 companyId → 用传入 company_id

    # 完全无匹配 → 跳过
    usage = [{"id": "u4", "provider": "nowhere", "metric": "input_tokens",
              "unit": "1M tokens", "quantity": 1.0}]
    assert f.estimate_costs_from_usage(usage, models, "co3") == []

    # 空 usage → 空结果
    assert f.estimate_costs_from_usage([], models, "co4") == []


def test_summarize_finops_roi():
    costs = [
        {"companyId": "co1", "productId": "course", "currency": "CNY", "amount": 1.0},
        {"companyId": "co1", "productId": "course", "currency": "CNY", "amount": 2.0},
        {"companyId": "co1", "productId": "consult", "currency": "CNY", "amount": 0.5},
    ]
    revenue = [
        {"companyId": "co1", "productId": "course", "currency": "CNY", "amount": 5.0},
    ]
    s = f.summarize_finops(costs, revenue, "co1")
    assert s["companyId"] == "co1"
    by_product = {g["productId"]: g for g in s["byProduct"]}
    assert by_product["course"]["cost"] == 3.0
    assert by_product["course"]["revenue"] == 5.0
    assert by_product["course"]["grossProfit"] == 2.0
    assert by_product["course"]["roi"] == round(2.0 / 3.0, 4)
    assert by_product["course"]["breakEven"] is True
    # 无收入产品 → 亏损
    assert by_product["consult"]["breakEven"] is False
    # byCompany 聚合
    assert s["byCompany"][0]["cost"] == 3.5
    assert s["byCompany"][0]["revenue"] == 5.0


def test_summarize_finops_zero_cost():
    s = f.summarize_finops([], [{"companyId": "c", "productId": None, "currency": "USD", "amount": 9.9}], "c")
    g = s["byCompany"][0]
    assert g["roi"] is None  # cost == 0 → roi None
    assert g["breakEven"] is True


def test_render_cost_report():
    costs = [
        {"provider": "deepseek", "amount": 1.0},
        {"provider": "openrouter", "amount": 2.0},
    ]
    summary = f.summarize_finops(
        [{"companyId": "c", "productId": "p1", "currency": "CNY", "amount": 1.0}],
        [{"companyId": "c", "productId": "p1", "currency": "CNY", "amount": 3.0}],
        "c",
    )
    report = f.render_cost_report(costs, summary)
    assert "总成本: 3.0" in report
    assert "- openrouter: 2.0" in report
    assert "p1" in report and "ROI 2.0" in report
    assert "盈亏平衡" in report


def test_parse_price_str():
    assert f._parse_price_str("0.00000175") == 0.00000175
    assert f._parse_price_str("") is None
    assert f._parse_price_str(None) is None
    assert f._parse_price_str("abc") is None


def test_refresh_provider_pricing_offline(monkeypatch):
    """include_openrouter=False → 不触发网络, 纯本地拷贝"""
    registry = f.refresh_provider_pricing(include_openrouter=False)
    assert registry["entries"] == f.DEFAULT_PRICING_REGISTRY["entries"]
    assert registry["generatedAt"].endswith("Z")


def test_refresh_provider_pricing_network_fail(monkeypatch):
    """网络失败 → 降级为默认注册表 + 标记 ok=False"""
    import urllib.request

    def boom(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    registry = f.refresh_provider_pricing(include_openrouter=True, timeout=1)
    openrouter_src = next(s for s in registry["sources"] if s["provider"] == "openrouter")
    assert openrouter_src["ok"] is False
    assert "network down" in openrouter_src["message"]
    # openrouter entries 保留默认值
    assert any(e["provider"] == "openrouter" for e in registry["entries"])
