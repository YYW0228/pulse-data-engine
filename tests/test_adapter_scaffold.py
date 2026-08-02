"""adapter_scaffold 测试"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_generate_cost_adapter(tmp_path):
    """cost 模式 → 适配器骨架 (语法正确 + 三件套)"""
    from scripts.adapter_scaffold import generate

    pattern = {
        "name": "token_budget",
        "source": {"repo": "DeerFlow", "license": "MIT", "file": "x.py"},
        "category": "cost",
        "core_idea": "会话 token 硬上限",
        "status": "migrated",
        "future_proof": "不变",
        "adaptation": "闸门",
        "pitfalls": ["坑1"],
        "verification": "超限 capped",
        "value": "high",
    }
    files = generate(pattern, tmp_path)
    assert len(files) == 3

    # 语法正确
    ast.parse(files[0].read_text(encoding="utf-8"))
    # 含 ABC 接口 + 方法
    src = files[0].read_text(encoding="utf-8")
    assert "TokenBudgetAdapter" in src
    assert "def check" in src
    assert "NotImplementedError" in src
    # 测试模板 + 迁移清单
    assert "pytest" in files[1].read_text(encoding="utf-8")
    assert "迁移清单" in files[2].read_text(encoding="utf-8")
    assert "DeerFlow" in files[2].read_text(encoding="utf-8")


def test_generate_orchestration(tmp_path):
    """orchestration 模式 → 不同接口形状"""
    from scripts.adapter_scaffold import generate

    pattern = {
        "name": "loop_detection",
        "source": {"repo": "DeerFlow", "license": "MIT", "file": "y.py"},
        "category": "orchestration",
        "core_idea": "hash 滑动窗口",
        "status": "migrated",
        "future_proof": "变简单",
        "value": "high",
    }
    files = generate(pattern, tmp_path)
    src = files[0].read_text(encoding="utf-8")
    ast.parse(src)
    assert "def record" in src
    assert "def reset" in src


def test_generate_unknown_category(tmp_path):
    """未知 category → 通用接口兜底"""
    from scripts.adapter_scaffold import generate

    pattern = {
        "name": "unknown_thing",
        "source": {"repo": "X", "license": "MIT", "file": "z.py"},
        "category": "other",
        "core_idea": "x",
        "status": "watch",
        "value": "medium",
    }
    files = generate(pattern, tmp_path)
    src = files[0].read_text(encoding="utf-8")
    ast.parse(src)
    assert "def run" in src  # 通用兜底方法
