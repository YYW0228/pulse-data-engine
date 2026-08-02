"""
scripts/adapter_scaffold.py — 模式 → 适配器脚手架生成器

从模式库 index.json 生成可落地的三件套:
  1. 接口骨架 (Python ABC + 方法签名)
  2. 测试模板 (pytest)
  3. 迁移清单 (Checklist)

用法:
  uv run python -m scripts.adapter_scaffold --pattern loop_detection
  uv run python -m scripts.adapter_scaffold --pattern loop_detection --out experiments/
  uv run python -m scripts.adapter_scaffold --list          # 列出可生成的模式

生成物:
  <out>/<name>/adapter.py       — 接口骨架
  <out>/<name>/test_adapter.py  — 测试模板
  <out>/<name>/MIGRATION.md     — 迁移清单
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pattern_lib import list_patterns

# ── 各 category 的接口模板 ──
INTERFACE_TEMPLATES: dict[str, dict[str, str | list[tuple[str, str]]]] = {
    "cost": {
        "doc": "成本控制接口 — 预算检查/成本核算",
        "methods": [
            ("def check(self, session_key: str | None = None) -> dict",
             "检查预算: 返回 {allowed, reason, usage}"),
            ("def session_usage(self, session_key: str | None = None) -> dict",
             "读取会话累计用量"),
        ],
    },
    "orchestration": {
        "doc": "编排控制接口 — 循环检测/任务调度",
        "methods": [
            ("def record(self, fingerprint: str) -> str",
             "记录一次调用, 返回 ok/warn/capped"),
            ("def reset(self) -> None",
             "重置检测器状态"),
        ],
    },
    "evidence": {
        "doc": "证据交付接口 — 可验收交付物",
        "methods": [
            ("def to_dict(self) -> dict",
             "序列化为 JSON 兼容结构"),
            ("def save(self) -> str",
             "持久化, 返回路径"),
            ("def to_markdown(self) -> str",
             "生成人可读报告"),
        ],
    },
    "memory": {
        "doc": "记忆接口 — 持久化/检索/遗忘",
        "methods": [
            ("def upsert(self, key: str, value: dict) -> None",
             "写入/更新记忆"),
            ("def retrieve(self, key: str) -> dict | None",
             "读取记忆"),
        ],
    },
    "context": {
        "doc": "上下文接口 — 编译/压缩/预算",
        "methods": [
            ("def compile(self, query: str, top_k: int = 3) -> list[dict]",
             "编译上下文"),
        ],
    },
    "guardrails": {
        "doc": "护栏接口 — 输入/输出校验",
        "methods": [
            ("def validate_input(self, text: str) -> dict",
             "输入校验, 返回 {allowed, reason}"),
        ],
    },
}

TEST_TEMPLATE = '''"""<NAME> 适配器测试"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_adapter_import():
    """适配器可导入"""
    from adapter import <CLASS>

    assert <CLASS> is not None


def test_adapter_basic(tmp_path):
    """基础功能: 构造 + 核心方法"""
    from adapter import <CLASS>

    impl = <CLASS>()
    # TODO: 补真实断言 (对齐模式库 verification)
    assert impl is not None


# TODO: 补边界测试 (空输入/超限/重复调用)
'''

MIGRATION_TEMPLATE = """# 迁移清单: <NAME>

> 来源: <SOURCE_REPO> (<LICENSE>)
> 状态: <STATUS> | 价值: <VALUE>

## 核心思路
<CORE_IDEA>

## 未来证明测试
<FUTURE_PROOF>

## 步骤
- [ ] 1. 把 adapter.py 放入目标模块 (如 pulse/ 或 scripts/)
- [ ] 2. 通过 test_adapter.py 全部测试
- [ ] 3. 接入调用方 (compliance_qa / service 层)
- [ ] 4. 跑对抗/回归评测 (注入/护栏不回退)
- [ ] 5. 记录落地位置到模式库 (pattern_lib --add)

## 坑 (来自模式库)
<PITFALLS>

## 验证 (来自模式库)
<VERIFICATION>
"""


def generate(pattern: dict, out_root: Path) -> list[Path]:
    """生成三件套, 返回生成的文件列表"""
    name = pattern["name"]
    category = pattern.get("category", "other")
    tmpl = INTERFACE_TEMPLATES.get(category, {
        "doc": "通用接口",
        "methods": [("def run(self) -> dict", "执行核心逻辑")],
    })

    class_name = "".join(p.capitalize() for p in name.split("_")) + "Adapter"

    # 1. 接口骨架
    method_defs = tmpl["methods"]
    assert isinstance(method_defs, list)
    methods_src = "\n\n".join(
        f"    {sig}:\n"
        f"        \"\"\"{doc}\"\"\"\n"
        f"        raise NotImplementedError"
        for sig, doc in method_defs
    )
    adapter = f'''"""
{name} 适配器 — 源自 {pattern.get("source", {}).get("repo", "?")} ({pattern.get("source", {}).get("license", "?")})

{pattern.get("core_idea", "")}

状态: EXPERIMENT — 通过测试后合入主线
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class {class_name}(ABC):
    """{tmpl["doc"]} (源自模式库: {name})"""

{methods_src}


if __name__ == "__main__":
    print(f"{class_name} 骨架就绪 — 运行 test_adapter.py 验证")
'''

    # 2. 测试模板
    test_src = TEST_TEMPLATE.replace("<NAME>", name).replace("<CLASS>", class_name)

    # 3. 迁移清单
    pitfalls = "\n".join(f"- {p}" for p in pattern.get("pitfalls", [])) or "- (无记录)"
    migration = (MIGRATION_TEMPLATE
                 .replace("<NAME>", name)
                 .replace("<SOURCE_REPO>", str(pattern.get("source", {}).get("repo", "?")))
                 .replace("<LICENSE>", str(pattern.get("source", {}).get("license", "?")))
                 .replace("<STATUS>", pattern.get("status", "?"))
                 .replace("<VALUE>", pattern.get("value", "?"))
                 .replace("<CORE_IDEA>", pattern.get("core_idea", ""))
                 .replace("<FUTURE_PROOF>", pattern.get("future_proof", ""))
                 .replace("<PITFALLS>", pitfalls)
                 .replace("<VERIFICATION>", pattern.get("verification", "")))

    target = out_root / name
    target.mkdir(parents=True, exist_ok=True)
    files = [
        target / "adapter.py",
        target / "test_adapter.py",
        target / "MIGRATION.md",
    ]
    for f, content in zip(files, [adapter, test_src, migration]):
        f.write_text(content, encoding="utf-8")
    return files


def main():
    parser = argparse.ArgumentParser(description="模式 → 适配器脚手架")
    parser.add_argument("--pattern", help="模式名 (来自模式库)")
    parser.add_argument("--out", default="experiments", help="输出目录")
    parser.add_argument("--list", action="store_true", help="列出可生成模式")
    args = parser.parse_args()

    patterns = list_patterns()
    if args.list:
        print("可生成适配器的模式:")
        for p in patterns:
            if p.get("status") == "migrated":
                print(f"  ✅ {p['name']} [{p.get('category')}] <- {p.get('source',{}).get('repo','?')}")
        return

    if not args.pattern:
        parser.print_help()
        sys.exit(1)

    pattern = next((p for p in patterns if p["name"] == args.pattern), None)
    if not pattern:
        print(f"❌ 模式不存在: {args.pattern} (用 --list 查看)")
        sys.exit(1)

    out_root = Path(args.out)
    files = generate(pattern, out_root)
    print(f"✅ 生成 {len(files)} 个文件:")
    for f in files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
