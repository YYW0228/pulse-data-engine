"""tests/conftest.py — 测试隔离: LLM 审计落盘指向 tmp, 不污染生产审计流。"""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _isolate_llm_audit():
    """所有测试的 audited_post 写入临时文件 (LLM_AUDIT_PATH 环境变量)。

    否则全量测试中 patch(httpx.post) 的 mock 路径 (FakeResp 等) 会
    经 audited_post 写入生产 data/llm_audit.jsonl, 污染真实审计流。
    """
    tmp = tempfile.mkdtemp(prefix="llm_audit_test_")
    old = os.environ.get("LLM_AUDIT_PATH")
    os.environ["LLM_AUDIT_PATH"] = os.path.join(tmp, "llm_audit.jsonl")
    yield
    if old is None:
        os.environ.pop("LLM_AUDIT_PATH", None)
    else:
        os.environ["LLM_AUDIT_PATH"] = old
