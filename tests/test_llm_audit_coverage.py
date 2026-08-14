"""
tests/test_llm_audit_coverage.py — 防回退门禁: 所有 LLM 调用必须经 audited_post。

扫描 pulse/ + scripts/ 源码, 任一含 chat/completions 的文件:
  - 必须 import/使用 audited_post
  - 不得再出现直接 httpx.post 调用
违反即测试失败 (CI 拦截未来新增未审计调用点)。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("pulse", "scripts")
EXCLUDE_DIRS = {"__pycache__", "vendor", "node_modules", ".venv"}
EXCLUDE_FILES = {"test_llm_audit.py", "test_llm_audit_coverage.py", "finops_tests.py"}


def _py_files() -> list[Path]:
    out = []
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.name in EXCLUDE_FILES:
                continue
            out.append(p)
    return out


def test_all_llm_calls_use_audited_post():
    violations = []
    for p in _py_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "chat/completions" not in text:
            continue
        if "audited_post" not in text:
            violations.append(f"{p.relative_to(ROOT)}: 含 LLM 调用但未使用 audited_post")
        if "httpx.post(" in text:
            violations.append(f"{p.relative_to(ROOT)}: 存在未审计的直接 httpx.post")
    assert not violations, "\n".join(violations)


def test_no_raw_llm_url_escapes():
    """审计包装器自身的 URL 是调用方传入, 其余源码不得出现裸 API 直连模式。"""
    raw = []
    for p in _py_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "api.deepseek.com" in text and "audited_post" not in text:
            raw.append(str(p.relative_to(ROOT)))
    assert not raw, f"裸 API 直连: {raw}"
