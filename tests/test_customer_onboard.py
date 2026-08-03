"""customer_onboard + 客户库测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_get_db_path(tmp_path, monkeypatch):
    """客户库路径生成"""
    from scripts import compliance_index as ci

    monkeypatch.setattr(ci, "DB_PATH", tmp_path / "global.duckdb")
    assert ci.get_db_path(None) == tmp_path / "global.duckdb"
    p = ci.get_db_path("acme")
    assert str(p).endswith("data/customers/acme/acme.duckdb")


def test_customer_db_switch(monkeypatch):
    """客户库切换"""
    import scripts.compliance_qa as cqa

    monkeypatch.setattr(cqa, "_CUSTOMER_DB", None)
    cqa.set_customer_db("acme")
    assert cqa._active_db().name == "acme.duckdb"
    cqa.set_customer_db(None)
    assert cqa._active_db().name == "compliance.duckdb"


def test_customer_fallback_logic():
    """客户库回退判定: 全局强命中 - 客户弱命中 > 0.05 → 应回退 (答非所问防御)"""
    import scripts.compliance_qa as cqa

    # 模拟检索结果
    cust_results = [{"doc": "cust.md", "hits": 0.50}]  # 客户库弱命中
    global_results = [{"doc": "law.md", "hits": 0.72}]  # 全局库强命中

    # 复刻 retrieve 的回退判定逻辑
    cust_best = max(r["hits"] for r in cust_results)
    global_best = max((r["hits"] for r in global_results), default=0.0)
    should_fallback = (global_best - cust_best > 0.05) and (global_best >= cqa.SIM_THRESHOLD)
    assert should_fallback, "全局 0.72 vs 客户 0.50 应回退"

    # 反例: 客户库强命中 (密码策略场景) → 不回退
    cust_strong = [{"doc": "cust.md", "hits": 0.674}]
    global_weak = [{"doc": "law.md", "hits": 0.50}]
    cb = max(r["hits"] for r in cust_strong)
    gb = max((r["hits"] for r in global_weak), default=0.0)
    assert not (gb - cb > 0.05), "客户库 0.674 应保留"


def test_list_customers(tmp_path, monkeypatch):
    """列出已接入客户 (仅含独立库存在的)"""
    from scripts import customer_onboard as co

    monkeypatch.setattr(co, "CUSTOMERS", tmp_path)
    # 有库的客户
    (tmp_path / "acme").mkdir(parents=True)
    (tmp_path / "acme" / "acme.duckdb").touch()
    # 无库的目录
    (tmp_path / "ghost").mkdir()
    customers = co.list_customers()
    assert customers == ["acme"]
