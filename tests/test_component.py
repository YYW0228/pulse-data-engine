"""
tests/test_component.py — 最小热替换原语 (Cordis 原则轻量版)

覆盖: 懒构建 / get 身份解析 / swap 原子性 / 失败回滚 / reset 卸载 /
      compliance_qa swap_embedder 集成 + component/swap 审计事件。
模型构建全局替换为假模型 (不触发真实 HF 下载/加载)。
"""

from __future__ import annotations

import pytest

from pulse.component import ManagedComponent


class FakeEmbedder:
    def __init__(self, name: str = "bge-small-zh-v1.5"):
        self._model_name = name

    def encode(self, *args, **kwargs):
        return [0.1, 0.2]


@pytest.fixture(autouse=True)
def _fake_model_env(tmp_path, monkeypatch):
    """全局假环境: 审计写 tmp + 模型构建替换为 FakeEmbedder (零网络/零加载/零 torch)。"""
    import sys
    import types

    import scripts.compliance_qa as cqa

    monkeypatch.setenv("LLM_AUDIT_PATH", str(tmp_path / "llm_audit.jsonl"))
    cqa._embedder = None

    def fake_build(name: str = "BAAI/bge-small-zh-v1.5") -> FakeEmbedder:
        return FakeEmbedder(name)

    from pulse.component import ManagedComponent
    monkeypatch.setattr(
        cqa, "_embedder_component",
        lambda: ManagedComponent("embedding.bge-small-zh", lambda: fake_build()),
    )
    # 注入假 sentence_transformers 模块: swap_embedder 内 from-import 拿 fake,
    # 不触发真实 torch 导入 (venv torch ABI 与 py3.10 不兼容, 硬导入会崩)
    fake_st = types.ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = fake_build
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    yield
    # 清理: 不把 fake 组件残留到全局 (否则后续测试拿到 list 向量而非 ndarray)
    cqa._embedder = None


def test_lazy_build_and_get_identity():
    """懒构建 + 身份解析: 消费方每次 get 拿当前实例。"""
    built = []

    def factory():
        built.append(1)
        return FakeEmbedder()

    c = ManagedComponent("embedding.test", factory)
    assert c.active is False and not built
    e1 = c.get()
    assert c.active and len(built) == 1
    assert c.get() is e1              # 缓存命中
    assert c.name == "embedding.test"


def test_swap_atomic_and_drainable():
    """swap = build → 原子换引用 → 返回 (old, new) 供 drain。"""
    c = ManagedComponent("embedding.test", lambda: FakeEmbedder("old"))
    old = c.get()
    new_old, new = c.swap(lambda: FakeEmbedder("new"))
    assert new_old is old
    assert new._model_name == "new"
    assert c.get() is new             # 之后的调用拿新实例
    assert c.get() is not old         # 旧实例已不可见 (drain 后 gc)


def test_swap_failure_rolls_back():
    """build 失败 → 抛异常, 旧实例保持 (失败隔离, 不污染业务)。"""
    c = ManagedComponent("embedding.test", lambda: FakeEmbedder("stable"))
    old = c.get()

    def bad_factory():
        raise RuntimeError("model load failed")

    with pytest.raises(RuntimeError):
        c.swap(bad_factory)
    assert c.get() is old             # 回滚: 旧实例仍然可用


def test_reset_unloads():
    """reset = 卸载; 下次 get 重新 build (可重复装载)。"""
    built = []
    c = ManagedComponent("embedding.test", lambda: (built.append(1), FakeEmbedder())[1])
    c.get()
    assert c.reset() is not None
    assert c.active is False
    c.get()
    assert len(built) == 2            # 重新构建


def test_swap_embedder_integration_audited(tmp_path):
    """compliance_qa.swap_embedder: 热替换 + component/swap 审计事件。"""
    import json

    import scripts.compliance_qa as cqa
    from pulse.llm_audit import _audit_path

    e1 = cqa.get_model()              # 懒构建默认模型 (FakeEmbedder)
    assert e1 is not None
    old, new = cqa.swap_embedder("BAAI/bge-small-zh-v1.5", source="agent.proposal")
    assert old is e1
    assert cqa.get_model() is new     # 身份解析: 调用方拿到新实例

    # 审计事件断言: "这次替换改了什么" 可追溯
    events = [json.loads(l) for l in _audit_path().read_text(encoding="utf-8").splitlines()
              if json.loads(l).get("kind") == "component/swap"]
    assert len(events) == 1
    ev = events[0]
    assert ev["component"] == "embedding.bge-small-zh"
    assert ev["new"] == "BAAI/bge-small-zh-v1.5"
    assert ev["source"] == "agent.proposal"


def test_swap_embedder_failure_keeps_old(tmp_path, monkeypatch):
    """swap_embedder 加载失败 → 异常抛出 + 旧模型保持 + 无审计记录 (swap 未发生)。"""
    import json
    import sys

    import scripts.compliance_qa as cqa
    from pulse.llm_audit import _audit_path

    old = cqa.get_model()
    # 让 fake 模块的 SentenceTransformer 抛错 (模拟加载失败)
    monkeypatch.setattr(
        sys.modules["sentence_transformers"], "SentenceTransformer",
        lambda name: (_ for _ in ()).throw(RuntimeError("load fail")),
    )
    with pytest.raises(RuntimeError):
        cqa.swap_embedder("BAAI/nonexistent-model-xyz", source="test.failure")
    assert cqa.get_model() is old
    p = _audit_path()
    events = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
              if json.loads(l).get("kind") == "component/swap"] if p.exists() else []
    assert events == []               # 失败替换不产生审计 (swap 未完成)
