"""
tests/test_harness_evolve_swap.py — 自演化闭环: apply 动作型提案 (热替换 embedding)

验证: 通过评估的提案 (action=swap_embedder) 落地时调用运行时原语,
替换记录进审计流 (component/swap, source=harness_evolve.apply)。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    """隔离: 提案文件 + 审计写 tmp。"""
    import scripts.harness_evolve as he

    monkeypatch.setenv("LLM_AUDIT_PATH", str(tmp_path / "llm_audit.jsonl"))
    monkeypatch.setattr(he, "PROPOSALS", tmp_path / "proposals.jsonl")
    monkeypatch.setattr(he, "QA_SRC", tmp_path / "compliance_qa.py")
    return he


def _write_proposal(he, prop: dict):
    he.PROPOSALS.write_text(json.dumps(prop, ensure_ascii=False) + "\n", encoding="utf-8")


def test_apply_swap_embedder_action(tmp_path, monkeypatch):
    """通过评估的 swap 提案 → 调用 swap_embedder (source=harness_evolve.apply) + 审计。"""
    import scripts.compliance_qa as cqa
    import scripts.harness_evolve as he

    prop = {"id": "p-swap-1", "action": "swap_embedder",
            "model_name": "BAAI/bge-m3", "status": "passed"}
    _write_proposal(he, prop)

    fake_old, fake_new = MagicMock(), MagicMock()
    fake_old._model_name = "bge-small-zh-v1.5"
    with patch.object(cqa, "swap_embedder", return_value=(fake_old, fake_new)) as mock_swap:
        rc = he.cmd_apply(he.argparse.Namespace(proposal="p-swap-1"))

    assert rc == 0
    mock_swap.assert_called_once_with("BAAI/bge-m3", source="harness_evolve.apply")
    # 提案状态已更新
    updated = json.loads(he.PROPOSALS.read_text(encoding="utf-8").strip())
    assert updated["status"] == "applied" and updated["applied_at"]


def test_apply_swap_failure_keeps_status(tmp_path, monkeypatch):
    """swap 失败 (模型加载崩) → 返回 1, 提案保持 passed (可重试), 无审计 (swap 未发生)。"""
    import scripts.compliance_qa as cqa
    import scripts.harness_evolve as he

    prop = {"id": "p-swap-2", "action": "swap_embedder",
            "model_name": "BAAI/nonexistent", "status": "passed"}
    _write_proposal(he, prop)

    with patch.object(cqa, "swap_embedder", side_effect=RuntimeError("load fail")):
        rc = he.cmd_apply(he.argparse.Namespace(proposal="p-swap-2"))

    assert rc == 1
    updated = json.loads(he.PROPOSALS.read_text(encoding="utf-8").strip())
    assert updated["status"] == "passed"            # 未标记 applied, 可重试


def test_apply_rejects_unpassed(tmp_path):
    """未通过评估的提案不落地。"""
    import scripts.harness_evolve as he

    prop = {"id": "p-swap-3", "action": "swap_embedder", "model_name": "BAAI/x", "status": "proposed"}
    _write_proposal(he, prop)
    rc = he.cmd_apply(he.argparse.Namespace(proposal="p-swap-3"))
    assert rc == 1
    updated = json.loads(he.PROPOSALS.read_text(encoding="utf-8").strip())
    assert updated["status"] == "proposed"


def test_structural_variant_defined():
    """结构级提案目录含 embedder_hot_swap (propose 可引用)。"""
    import scripts.harness_evolve as he

    v = he.STRUCTURAL_VARIANTS["embedder_hot_swap"]
    assert v["action"] == "swap_embedder"
    assert "swap_embedder" in v["pseudocode"]
    assert "component/swap" in v["mechanism"]
