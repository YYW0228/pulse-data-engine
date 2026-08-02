"""
scripts/pattern_lib.py — 模式库管理 (结构化吞噬模式)

把 devoured-patterns.md 升级为可检索的结构化模式库:
  patterns/<mode-name>/index.json — 每个模式一个 JSON

Schema (与 harness-devour 对齐):
  {
    "name": "loop_detection",
    "source": {"repo": "DeerFlow", "license": "MIT", "file": "middlewares/loop_detection_middleware.py"},
    "category": "orchestration|memory|context|guardrails|evidence|cost|recovery|tools",
    "core_idea": "一句话核心思路",
    "status": "migrated|experiment|watch|rejected",
    "future_proof": "模型变强后: 变简单/不变/变复杂",
    "adaptation": "可迁移接口建议",
    "pitfalls": ["坑1", "坑2"],
    "verification": "如何验证",
    "value": "试点客户价值: high|medium|low",
    "landed_at": "代码位置或实验位置"
  }

用法:
  uv run python -m scripts.pattern_lib --list              # 列出全部
  uv run python -m scripts.pattern_lib --add <json文件>     # 添加模式
  uv run python -m scripts.pattern_lib --search 缓存        # 搜索
  uv run python -m scripts.pattern_lib --export            # 导出全库 JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PATTERNS_DIR = Path(__file__).resolve().parent.parent / "patterns"

CATEGORIES = {"orchestration", "memory", "context", "guardrails", "evidence",
              "cost", "recovery", "tools", "sandbox", "model"}
STATUSES = {"migrated", "experiment", "watch", "rejected"}
VALUES = {"high", "medium", "low"}


def validate(pattern: dict) -> list[str]:
    """校验模式 schema, 返回错误列表"""
    errors = []
    for field in ("name", "source", "category", "core_idea", "status",
                  "future_proof", "value"):
        if field not in pattern:
            errors.append(f"缺少字段: {field}")
    if pattern.get("category") not in CATEGORIES:
        errors.append(f"category 非法: {pattern.get('category')} (可选: {sorted(CATEGORIES)})")
    if pattern.get("status") not in STATUSES:
        errors.append(f"status 非法: {pattern.get('status')} (可选: {sorted(STATUSES)})")
    if pattern.get("value") not in VALUES:
        errors.append(f"value 非法: {pattern.get('value')}")
    return errors


def add_pattern(pattern: dict, force: bool = False) -> Path:
    """添加/更新模式 → patterns/<name>/index.json"""
    errors = validate(pattern)
    if errors:
        raise ValueError("; ".join(errors))

    name = pattern["name"]
    safe = name.replace("/", "_").replace(" ", "_")
    target = PATTERNS_DIR / safe / "index.json"
    if target.exists() and not force:
        raise FileExistsError(f"模式已存在: {name} (用 --force 覆盖)")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pattern, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def list_patterns() -> list[dict]:
    """列出全部模式"""
    patterns = []
    for idx in sorted(PATTERNS_DIR.glob("*/index.json")):
        try:
            patterns.append(json.loads(idx.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return patterns


def search(query: str) -> list[dict]:
    """搜索模式 (name/core_idea/category 模糊匹配)"""
    q = query.lower()
    return [p for p in list_patterns()
            if q in p.get("name", "").lower()
            or q in p.get("core_idea", "").lower()
            or q in p.get("category", "").lower()]


def export() -> dict:
    """导出全库 (按 category 分组)"""
    grouped: dict[str, list[dict]] = {}
    for p in list_patterns():
        grouped.setdefault(p.get("category", "other"), []).append(p)
    return grouped


def main():
    parser = argparse.ArgumentParser(description="模式库管理")
    parser.add_argument("--list", action="store_true", help="列出全部")
    parser.add_argument("--add", help="添加模式 JSON 文件")
    parser.add_argument("--force", action="store_true", help="覆盖已存在")
    parser.add_argument("--search", help="搜索")
    parser.add_argument("--export", action="store_true", help="导出全库")
    args = parser.parse_args()

    if args.list:
        patterns = list_patterns()
        print(f"模式库: {len(patterns)} 个模式\n")
        for p in patterns:
            source_repo = str(p.get("source", {}).get("repo", "?")) if isinstance(p.get("source"), dict) else "?"
            mark = {"migrated": "✅", "experiment": "🧪", "watch": "👀", "rejected": "❌"}.get(p.get("status", ""), "?")
            print(f"  {mark} [{p.get('category','?'):<13}] {p.get('name','?'):<25} "
                  f"<- {source_repo} ({p.get('value','?')})")
            print(f"      {p.get('core_idea','')[:80]}")
        return

    if args.add:
        path = Path(args.add)
        if not path.exists():
            print(f"❌ 文件不存在: {path}")
            sys.exit(1)
        pattern = json.loads(path.read_text(encoding="utf-8"))
        try:
            target = add_pattern(pattern, force=args.force)
            print(f"✅ 模式已入库: {target}")
        except (ValueError, FileExistsError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        return

    if args.search:
        results = search(args.search)
        print(f"搜索 '{args.search}': {len(results)} 个结果\n")
        for p in results:
            print(f"  {p.get('name')} [{p.get('category')}] <- {p.get('source',{}).get('repo','?')}")
            print(f"      {p.get('core_idea','')[:90]}")
        return

    if args.export:
        grouped = export()
        for cat, patterns in grouped.items():
            print(f"## {cat} ({len(patterns)})")
            for p in patterns:
                print(f"  - {p.get('name')}: {p.get('status')} ({p.get('value')})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
