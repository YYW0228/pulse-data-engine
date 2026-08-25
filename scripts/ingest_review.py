#!/usr/bin/env python3
"""
scripts/ingest_review.py — 主线 harness 筛查评分: data/ingest/ → scene2_intel

Mac mini 素材工厂推送到 data/ingest/ 后, 由本脚本执行 harness 门禁:
  1. 扫描 data/ingest/ 下的 ingest-*.md + 同名 .json
  2. 模板校验: 6 段结构齐全 + metadata 字段完整 + 自评分存在
  3. 评分 (0-100): 结构完整性 40 + 元数据 30 + 内容质量启发式 30
  4. 分档: >=80 自动通过 | 60-79 需 --force | <60 拒绝
  5. --approve: 通过文件 move → scene2_intel → 触发 compliance_index 索引

用法:
  uv run python -m scripts.ingest_review                # 筛查报告 (只读)
  uv run python -m scripts.ingest_review --approve all  # 终审通过并入库
  uv run python -m scripts.ingest_review --approve <file> --force
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
INGEST = PROJECT / "data" / "ingest"
SCENE2 = PROJECT / "data" / "scene2_intel"

STRUCTURE_MARKERS = [
    "一、核心论点",
    "二、章节摘要",
    "三、关键概念",
    "四、金句",
    "五、与主线",
    "六、参考练习",
]
META_REQUIRED = ["title", "url", "ingested_at", "transcript_source", "self_score", "language"]


def check_structure(content: str) -> tuple[int, list[str]]:
    missing = [m for m in STRUCTURE_MARKERS if m not in content]
    return len(STRUCTURE_MARKERS) - len(missing), missing


def score_md(path: Path, meta: dict) -> dict:
    content = path.read_text(encoding="utf-8")
    detail: list[str] = []
    score = 0

    # 1. 结构完整性 40
    found, missing = check_structure(content)
    score += int(found / len(STRUCTURE_MARKERS) * 40)
    if missing:
        detail.append(f"缺结构: {missing}")

    # 2. 元数据 30
    meta_ok = [k for k in META_REQUIRED if meta.get(k)]
    score += int(len(meta_ok) / len(META_REQUIRED) * 30)
    if len(meta_ok) < len(META_REQUIRED):
        detail.append(f"缺元数据: {[k for k in META_REQUIRED if not meta.get(k)]}")

    # 3. 内容启发式 30
    if len(content) >= 2000:
        score += 10
    elif len(content) >= 1000:
        score += 6
    else:
        detail.append("内容过短")
    if "转录" in content or "RAG" in content or "LLM" in content or "AI" in content:
        score += 10  # 主题密度
    else:
        detail.append("主题密度低")
    if "信源" in content or "来源" in content or "URL" in content:
        score += 10  # 来源标注
    else:
        detail.append("缺来源标注")

    return {"score": score, "detail": detail, "found": found, "total": len(STRUCTURE_MARKERS)}


def scan() -> list[dict]:
    results = []
    for md in sorted(INGEST.glob("ingest-*.md")):
        meta_path = md.with_suffix(".json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        r = score_md(md, meta)
        results.append(
            {
                "file": md.name,
                "score": r["score"],
                "detail": r["detail"],
                "title": meta.get("title", "?"),
                "self_score": meta.get("self_score", "?"),
                "source": meta.get("transcript_source", "?"),
                "engine": meta.get("ingest_engine", "?"),
            }
        )
    return results


def approve(files: list[str], force: bool) -> int:
    SCENE2.mkdir(parents=True, exist_ok=True)
    moved = 0
    for name in files:
        md = INGEST / name
        if not md.exists():
            print(f"  跳过(不存在): {name}")
            continue
        meta_path = md.with_suffix(".json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        r = score_md(md, meta)
        if r["score"] < 60 or (r["score"] < 80 and not force):
            print(f"  拒绝 {name}: 评分 {r['score']} (需>=80, 60-79需--force) {r['detail']}")
            continue
        dest = SCENE2 / md.name
        shutil.move(str(md), str(dest))
        if meta_path.exists():
            shutil.move(str(meta_path), str(SCENE2 / meta_path.name))
        print(f"  入库 {name}: 评分 {r['score']} -> scene2_intel")
        moved += 1
    if moved:
        print(f"\n触发 compliance_index 索引...")
        r = subprocess.run(
            [sys.executable, "-m", "scripts.compliance_index", "--source", str(SCENE2)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = r.stdout + r.stderr
        print(
            "  "
            + "\n  ".join(
                l for l in out.splitlines() if "分块" in l or "文档" in l or "✅" in l or "❌" in l
            )
        )
    return moved


def main() -> int:
    ap = argparse.ArgumentParser(description="主线 harness 素材筛查评分")
    ap.add_argument("--approve", nargs="+", default=None, help="终审入库: 文件列表或 'all'")
    ap.add_argument("--force", action="store_true", help="允许 60-79 分入库")
    args = ap.parse_args()

    results = scan()
    if not results:
        print("data/ingest/ 无待审素材")
        return 0

    print(f"{'文件':<55} {'评分':>4}  自评 源      备注")
    print("-" * 100)
    for r in results:
        note = "; ".join(r["detail"]) if r["detail"] else "OK"
        print(f"{r['file']:<55} {r['score']:>4}  {r['self_score']!s:>4}  {r['source']:<10} {note}")
    print("-" * 100)
    passed = [r for r in results if r["score"] >= 80]
    manual = [r for r in results if 60 <= r["score"] < 80]
    rejected = [r for r in results if r["score"] < 60]
    print(f"通过: {len(passed)} | 待人工: {len(manual)} | 拒绝: {len(rejected)}")

    if args.approve:
        targets = [r["file"] for r in results] if "all" in args.approve else args.approve
        print(f"\n终审入库 {len(targets)} 个...")
        approve(targets, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
