"""tests/test_kb_refresh.py — _scraper_interpreter() DAP_ROOT 探测逻辑测试"""

import os
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.kb_refresh import _scraper_interpreter


@pytest.fixture
def venv_tree():
    """在临时目录中创建 DAP_ROOT/.venv/bin/python 可执行脚本"""
    with tempfile.TemporaryDirectory() as tmpdir:
        dap_root = Path(tmpdir)
        venv_python = dap_root / ".venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("#!/bin/sh\necho fake\n")
        venv_python.chmod(venv_python.stat().st_mode | stat.S_IEXEC)
        yield dap_root, venv_python


def _make_run(dap_python_path: str):
    """构造 mock subprocess.run: 仅对 DAP python 返回 returncode=0, 其余候选返回 1"""

    def fake_run(args, **_kw):
        result = MagicMock()
        result.returncode = 0 if args[0] == dap_python_path else 1
        result.stderr = b""
        return result

    return fake_run


def test_scraper_interpreter_dap_venv(venv_tree):
    """DAP_ROOT 设置时, .venv/bin/python 应在 candidates 中且被返回"""
    dap_root, venv_python = venv_tree

    with patch.dict(os.environ, {"DAP_ROOT": str(dap_root)}, clear=True), patch(
        "scripts.kb_refresh.subprocess.run",
        side_effect=_make_run(str(venv_python)),
    ):
        result = _scraper_interpreter()
        assert result == str(venv_python), (
            f"Expected DAP python {venv_python}, got {result}"
        )


def test_scraper_interpreter_no_dap_root():
    """DAP_ROOT 未设置时不影响原有行为 — 函数不崩溃, 返回字符串"""
    with patch.dict(os.environ, {}, clear=True), \
            patch("scripts.kb_refresh.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = b""
            mock_run.return_value = mock_result

            result = _scraper_interpreter()
            assert isinstance(result, str)
            assert len(result) > 0
            # 不应包含 DAP .venv 路径特征
            assert ".venv" not in result or "DAP_ROOT" in os.environ


def test_scraper_interpreter_fallback_to_sys_executable():
    """所有候选都失败时, 兜底返回 sys.executable"""
    with patch.dict(os.environ, {}, clear=True), \
            patch("scripts.kb_refresh.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1  # 全部失败
            mock_result.stderr = b"import error"
            mock_run.return_value = mock_result

            result = _scraper_interpreter()
            assert result == sys.executable
