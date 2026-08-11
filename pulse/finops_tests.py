"""pulse/finops_tests.py — finops 模块单元测试 (纯 stdlib, 无 pytest 依赖)"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("pulse_finops", ROOT / "pulse" / "finops.py")
if spec is None or spec.loader is None:
    raise ImportError("cannot load finops.py")
loader = spec.loader
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)


def test_money():
    assert mod.round_money(1.005) == 1.005
    assert mod.round_money(0.1 + 0.2) == 0.3
    assert mod.minor_unit_factor("jpy") == 1
    assert mod.minor_unit_factor("usd") == 100
    assert mod.from_minor_units(100, "usd") == 1.0
    print("✅ money")


def test_cost_estimate_exact():
    usage = [
        {"id": "u1", "provider": "deepseek", "model": "deepseek-chat", "metric": "input_tokens",
         "unit": "1M tokens", "quantity": 0.5, "companyId": "co1", "productId": "hermes"},
        {"id": "u2", "provider": "deepseek", "model": "deepseek-chat", "metric": "output_tokens",
         "unit": "1M tokens", "quantity": 0.2, "companyId": "co1", "productId": "hermes"},
    ]
    models = [m for m in mod.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = mod.estimate_costs_from_usage(usage, models, "co1")
    assert len(costs) == 2
    assert costs[0]["amount"] == 0.14, costs[0]
    assert costs[1]["amount"] == 0.224, costs[1]
    print("✅ cost_estimate_exact")


def test_cost_estimate_loose():
    usage = [
        {"id": "u3", "provider": "deepseek", "metric": "input_tokens",
         "unit": "1M tokens", "quantity": 1.0, "companyId": "co1"},
    ]
    models = [m for m in mod.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = mod.estimate_costs_from_usage(usage, models, "co1")
    assert len(costs) == 1
    print("✅ cost_estimate_loose")


def test_ledger_roi():
    usage = [
        {"id": "u1", "provider": "deepseek", "model": "deepseek-chat", "metric": "input_tokens",
         "unit": "1M tokens", "quantity": 0.5, "companyId": "co1", "productId": "hermes"},
    ]
    models = [m for m in mod.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = mod.estimate_costs_from_usage(usage, models, "co1")
    revenue = [{"id": "r1", "provider": "stripe", "companyId": "co1",
                "productId": "hermes", "amount": 10.0, "currency": "CNY"}]
    summary = mod.summarize_finops(costs, revenue, "co1")
    bp = summary["byProduct"][0]
    assert bp["revenue"] == 10.0
    assert bp["cost"] == 0.14
    assert bp["breakEven"] is True
    assert bp["roi"] is not None and bp["roi"] > 0
    print("✅ ledger_roi")


def test_render():
    usage = [
        {"id": "u1", "provider": "deepseek", "model": "deepseek-chat", "metric": "input_tokens",
         "unit": "1M tokens", "quantity": 0.5, "companyId": "co1", "productId": "hermes"},
    ]
    models = [m for m in mod.DEFAULT_PRICING_REGISTRY["entries"] if m["provider"] == "deepseek"]
    costs = mod.estimate_costs_from_usage(usage, models, "co1")
    summary = mod.summarize_finops(costs, [], "co1")
    report = mod.render_cost_report(costs, summary)
    assert "Agent 成本报告" in report
    assert "deepseek" in report
    print("✅ render")


def test_pricing_refresh_offline():
    """不联网时 refresh 应优雅失败, 退回默认注册表"""
    registry = mod.refresh_provider_pricing(include_openrouter=True, timeout=1)
    assert registry["generatedAt"]
    # 即使网络失败, 注册表仍有数据
    assert len(registry["entries"]) > 0
    print("✅ pricing_refresh_offline (graceful)")


if __name__ == "__main__":
    test_money()
    test_cost_estimate_exact()
    test_cost_estimate_loose()
    test_ledger_roi()
    test_render()
    test_pricing_refresh_offline()
    print("\n🎉 全部通过")
