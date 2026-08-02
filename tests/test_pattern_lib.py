"""pattern_lib 测试"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _valid_pattern(name: str = "test_pattern") -> dict:
    return {
        "name": name,
        "source": {"repo": "TestRepo", "license": "MIT", "file": "x.py"},
        "category": "cost",
        "core_idea": "测试模式",
        "status": "experiment",
        "future_proof": "不变",
        "adaptation": "接口",
        "pitfalls": ["坑"],
        "verification": "验证",
        "value": "high",
    }


def test_add_and_list(tmp_path, monkeypatch):
    from scripts import pattern_lib as pl

    monkeypatch.setattr(pl, "PATTERNS_DIR", tmp_path / "patterns")
    pl.add_pattern(_valid_pattern())
    patterns = pl.list_patterns()
    assert len(patterns) == 1
    assert patterns[0]["name"] == "test_pattern"


def test_add_duplicate_rejected(tmp_path, monkeypatch):
    from scripts import pattern_lib as pl

    monkeypatch.setattr(pl, "PATTERNS_DIR", tmp_path / "patterns")
    pl.add_pattern(_valid_pattern())
    try:
        pl.add_pattern(_valid_pattern())
        assert False, "应拒绝重复"
    except FileExistsError:
        pass


def test_add_duplicate_force(tmp_path, monkeypatch):
    from scripts import pattern_lib as pl

    monkeypatch.setattr(pl, "PATTERNS_DIR", tmp_path / "patterns")
    pl.add_pattern(_valid_pattern())
    p = _valid_pattern()
    p["core_idea"] = "更新"
    pl.add_pattern(p, force=True)
    patterns = pl.list_patterns()
    assert patterns[0]["core_idea"] == "更新"


def test_validate_invalid():
    from scripts import pattern_lib as pl

    errors = pl.validate({"name": "x"})  # 缺字段
    assert len(errors) > 0

    bad = _valid_pattern()
    bad["category"] = "invalid_cat"
    assert "category 非法" in " ".join(pl.validate(bad))


def test_search(tmp_path, monkeypatch):
    from scripts import pattern_lib as pl

    monkeypatch.setattr(pl, "PATTERNS_DIR", tmp_path / "patterns")
    pl.add_pattern(_valid_pattern("cache_stability"))
    pl.add_pattern({**_valid_pattern("loop_detection"), "category": "orchestration"})

    results = pl.search("cache")
    assert len(results) == 1
    assert results[0]["name"] == "cache_stability"

    results2 = pl.search("orchestration")
    assert len(results2) == 1


def test_export_grouped(tmp_path, monkeypatch):
    from scripts import pattern_lib as pl

    monkeypatch.setattr(pl, "PATTERNS_DIR", tmp_path / "patterns")
    pl.add_pattern(_valid_pattern("a"))
    pl.add_pattern({**_valid_pattern("b"), "category": "memory"})

    grouped = pl.export()
    assert "cost" in grouped
    assert "memory" in grouped
