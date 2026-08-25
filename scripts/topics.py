#!/usr/bin/env python3
"""
scripts/topics.py — 缺口驱动选题队列 (P0 闭环)

链路: kb_gap 缺口 + course_gaps.yaml 课程缺口 → queue/*.json 候选
      → 规则/人工批准 (配额内) → ingest_playlist --queue 消费 → 入库 → kb_gap 复评

约束 (选题失控防御):
  - 来源优先级: kb_gap 缺口 > 课程大纲缺口 > 销售高频问题 > 行业热点
  - 配额: 每周最多 QUOTA_WEEK 条 (默认 5), 超出需 --force
  - 去重: topic 归一化后查 queue/ingest/scene2 已有
  - 预期价值分: expected_value 0-10 (缺口强度/覆盖度加权)

用法:
  uv run python -m scripts.topics --generate          # 从 kb_gap + course_gaps 生成候选
  uv run python -m scripts.topics --list              # 查看队列
  uv run python -m scripts.topics --approve auto      # 规则自动批准 (high 优先)
  uv run python -m scripts.topics --approve <slug>    # 手动批准单个
  uv run python -m scripts.topics --approve <slug> --force   # 超配额强制
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
QUEUE_DIR = PROJECT / "data" / "ingest" / "queue"
GAPS_YAML = PROJECT / "data" / "course_gaps.yaml"
KB_GAP_REPORT = PROJECT / "data" / "kb_gap_report.md"
INGEST_DIR = PROJECT / "data" / "ingest"
SCENE2_DIR = PROJECT / "data" / "scene2_intel"

QUOTA_WEEK = 5  # 每周批准上限
AUTO_APPROVE_MAX_PRI = 2  # priority <= 2 自动批准
AUTO_APPROVE_MIN_VALUE = 7  # expected_value >= 7 自动批准
SOURCE_PRI = {"kb_gap": 1, "course_gap": 2, "sales": 3, "hotspot": 4}


def slugify(topic: str) -> str:
    s = unicodedata.normalize("NFKC", topic).lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s).strip("-")
    return (s or "topic")[:50]


def load_existing_topics() -> set[str]:
    """queue + 已入库素材的 topic 去重集"""
    seen: set[str] = set()
    for d in (QUEUE_DIR, INGEST_DIR, SCENE2_DIR):
        if not d.exists():
            continue
        for f in d.glob("*.json"):
            try:
                m = json.loads(f.read_text(encoding="utf-8"))
                if m.get("topic"):
                    seen.add(slugify(m["topic"]))
            except (json.JSONDecodeError, OSError):
                continue
    return seen


def load_course_gaps() -> list[dict]:
    """course_gaps.yaml: 手动维护的课程大纲缺口 (轻量解析: 每行 - topic: ...)"""
    gaps: list[dict] = []
    if not GAPS_YAML.exists():
        return gaps
    for line in GAPS_YAML.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = re.match(r"^-?\s*topic:\s*(.+)$", line)
        if m:
            topic = m.group(1).strip().strip("\"'")
            if topic:
                gaps.append(
                    {"topic": topic, "source": "course_gap", "expected_value": 6, "priority": 2}
                )
    return gaps


def kb_gap_candidates() -> list[dict]:
    """kb_gap --json 概念缺口 → 候选 (来源优先级 1)"""
    r = subprocess.run(
        [sys.executable, "-m", "scripts.kb_gap", "--json"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT),
        timeout=600,
    )
    if r.returncode != 0:
        print(f"[topics] kb_gap 失败: {r.stderr[-200:]}", file=sys.stderr)
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("[topics] kb_gap --json 解析失败", file=sys.stderr)
        return []
    cands = []
    for g in data.get("concept_gaps", []):
        word = g.get("expect_word", "")
        if not word:
            continue
        # 短词(<4 字符)是 golden_set 拆出来的碎片 (如"同意"/"清洗"), 无吞噬选题价值
        if len(word) < 4:
            continue
        # 价值分: 缺口越空(max_sim 越低) + 有明确问题上下文 → 越高
        max_sim = g.get("max_sim", 0.0)
        value = round(min(10, 5 + (0.52 - max_sim) * 25), 1)
        cands.append(
            {
                "topic": word,
                "source": "kb_gap",
                "expected_value": value,
                "priority": 1,
                "context_question": g.get("question", ""),
                "max_sim": max_sim,
            }
        )
    return cands


def write_candidate(c: dict, existing: set[str]) -> bool:
    slug = slugify(c["topic"])
    if slug in existing:
        return False
    cand = {
        "slug": slug,
        "topic": c["topic"],
        "source": c.get("source", "course_gap"),
        "priority": SOURCE_PRI.get(c.get("source", "course_gap"), 3),
        "expected_value": c.get("expected_value", 5),
        "context_question": c.get("context_question", ""),
        "status": "pending",  # pending → approved → done
        "approved_at": None,
        "done_at": None,
        "candidates_urls": [],  # 人工填充或 ytsearch 候选
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (QUEUE_DIR / f"{slug}.json").write_text(
        json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return True


def generate() -> int:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_existing_topics()
    cands = kb_gap_candidates() + load_course_gaps()
    # 来源优先级排序后按价值过滤 (expected_value < 5 不入队)
    cands = [c for c in cands if c.get("expected_value", 0) >= 5]
    added = 0
    for c in sorted(
        cands, key=lambda x: (SOURCE_PRI.get(x.get("source", 9), 9), -x.get("expected_value", 0))
    ):
        if write_candidate(c, existing):
            added += 1
            existing.add(slugify(c["topic"]))
    print(f"[topics] 生成完成: 新增 {added} 候选 (去重后)")
    return 0


def weekly_approved_count() -> int:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    n = 0
    for f in QUEUE_DIR.glob("*.json"):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("approved_at") and datetime.fromisoformat(m["approved_at"]) >= week_ago:
                n += 1
        except (json.JSONDecodeError, OSError, ValueError):
            continue
    return n


def approve(slugs: list[str], force: bool = False) -> int:
    if "auto" in slugs:
        targets = []
        for f in QUEUE_DIR.glob("*.json"):
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("status") != "pending":
                continue
            if (
                m.get("priority", 9) <= AUTO_APPROVE_MAX_PRI
                or m.get("expected_value", 0) >= AUTO_APPROVE_MIN_VALUE
            ):
                targets.append(f)
    else:
        targets = [QUEUE_DIR / f"{s}.json" for s in slugs]
    targets = [t for t in targets if t.exists()]
    if not targets:
        print("[topics] 无匹配的候选")
        return 0

    used = weekly_approved_count()
    remaining = QUOTA_WEEK - used
    approved = 0
    for t in targets:
        if remaining <= 0 and not force:
            print(f"  ⚠ 周配额已用尽 ({QUOTA_WEEK}/{QUOTA_WEEK}), 跳过 {t.stem} (--force 覆盖)")
            continue
        m = json.loads(t.read_text(encoding="utf-8"))
        if m.get("status") != "pending":
            print(f"  跳过 {t.stem}: 状态={m.get('status')}")
            continue
        m["status"] = "approved"
        m["approved_at"] = datetime.now(timezone.utc).isoformat()
        t.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ 批准 {t.stem} (priority={m['priority']}, value={m['expected_value']})")
        approved += 1
        remaining -= 1
    return approved


def list_queue() -> int:
    rows = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        rows.append(
            (
                m.get("status", "?"),
                m.get("priority", 9),
                m.get("expected_value", 0),
                m.get("source", "?"),
                m.get("topic", "?"),
            )
        )
    if not rows:
        print("[topics] 队列为空")
        return 0
    print(f"{'状态':<9} {'PRI':>3} {'价值':>4} 源         选题")
    for status, pri, val, src, topic in sorted(rows, key=lambda r: (r[0], r[1])):
        print(f"{status:<9} {pri:>3} {val:>4}  {src:<10} {topic[:50]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="缺口驱动选题队列 (P0 闭环)")
    ap.add_argument("--generate", action="store_true", help="生成候选 (kb_gap + course_gaps)")
    ap.add_argument("--list", action="store_true", help="查看队列")
    ap.add_argument("--approve", nargs="+", default=None, help="批准: slug 列表 或 auto")
    ap.add_argument("--force", action="store_true", help="超配额强制批准")
    args = ap.parse_args()

    if args.generate:
        return generate()
    if args.list:
        return list_queue()
    if args.approve:
        return approve(args.approve, force=args.force)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
