"""
tests/test_llm_audit_coverage.py — 防回退门禁: 所有 LLM 调用必须经 audited_post。

扫描 pulse/ + scripts/ 源码, 任一含 chat/completions 的文件:
  - 必须 import/使用 audited_post
  - 不得再出现直接 httpx.post 调用
违反即测试失败 (CI 拦截未来新增未审计调用点)。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("pulse", "scripts")
EXCLUDE_DIRS = {"__pycache__", "vendor", "node_modules", ".venv"}
EXCLUDE_FILES = {
    "test_llm_audit.py",
    "test_llm_audit_coverage.py",
    "finops_tests.py",
    # 素材工厂 (ingest_*): 调用本地 llama-server (127.0.0.1), 非云端 LLM 链路,
    # 无外部可见性/成本, 不在 Model-visible=Logged 审计范围
    "ingest_produce.py",
    "ingest_review.py",
    # flywheel 候选技能生成: 同款本地 llama 链路 (127.0.0.1:8080), 无外部可见性
    "generate_candidate.py",
}


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


def test_all_compaction_functions_are_audited():
    """收口门禁: 任何压缩/摘要函数必须自带审计副作用。

    函数名匹配 compact|handoff 的 def, 其函数体必须含 audit_compaction 调用
    或 compact_and_audit (统一入口), 否则压缩发生但审计缺失 = 局部真理。
    """
    import ast

    violations = []
    for p in _py_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not re.search(r"compact|handoff", node.name, re.IGNORECASE):
                continue
            # 豁免: 审计工具函数自身 (检测/记录实现, 不是压缩逻辑)
            if re.search(r"find_compaction|audit_compaction", node.name):
                continue
            body_src = ast.get_source_segment(
                p.read_text(encoding="utf-8", errors="ignore"), node) or ""
            has_audit = ("audit_compaction" in body_src or "compact_and_audit" in body_src)
            if not has_audit:
                violations.append(f"{p.relative_to(ROOT)}::{node.name} 压缩/摘要无审计副作用")
    assert not violations, "\n".join(violations)
