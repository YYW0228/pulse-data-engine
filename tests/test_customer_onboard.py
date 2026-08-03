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
