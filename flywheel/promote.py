#!/usr/bin/env python3
"""Flywheel 晋升执行器 — 提案 → 技能晋升 (人工审批 + 白名单 + 可回滚)

用法:
  python flywheel/promote.py --approve <proposal_file> --rationale "原因" [--target <技能名>]
  python flywheel/promote.py --rollback <promotion_id>
  python flywheel/promote.py --list

纪律 (吸收 wanman autoPromote + propose-never-auto-apply):
  - rationale 必填 (防橡皮图章)
  - 写入路径白名单: 仅 ~/.hermes/skills/ 下 (新技能) 或指定已有技能 (追加章节)
  - 晋升记录 promotions.jsonl, 7 天内可回滚
  - 指标: 晋升后技能使用/回滚情况由 trio-health + 人工周检跟踪
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FLYWHEEL = Path(__file__).resolve().parent
PROPOSALS = FLYWHEEL / "proposals"
REVIEW_QUEUE = FLYWHEEL / "REVIEW_QUEUE.md"
PROMOTIONS_LOG = FLYWHEEL / "promotions.jsonl"
SKILLS_ROOT = Path.home() / ".hermes" / "skills"
ALLOWED_ROOTS = (SKILLS_ROOT,)  # 路径白名单: 只允许技能库

FRONTMATTER = """---
name: {name}
description: "{desc}"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [{tags}]
    related_skills: [{related}]
---

"""


def load_promotions() -> list[dict]:
    if not PROMOTIONS_LOG.exists():
        return []
    return [json.loads(line) for line in PROMOTIONS_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_promotion(rec: dict) -> None:
    with PROMOTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_proposal(path: Path) -> tuple[str, str]:
    """返回 (技能名, body)。body = 提案正文 (去掉 header 注释)"""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)
    m = re.match(r"#\s+(.+)", text)
    name = m.group(1).strip() if m else path.stem
    name = re.sub(r"[^\w\u4e00-\u9fff-]", "-", name).strip("-")[:40] or path.stem
    return name, text


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "flywheel-skill"


def approve(proposal_path: str, rationale: str, target: str | None) -> None:
    if not rationale or len(rationale) < 4:
        print("✗ rationale 必填且 ≥4 字 (防橡皮图章)")
        sys.exit(1)

    prop = Path(proposal_path)
    if not prop.exists():
        print(f"✗ 提案不存在: {prop}")
        sys.exit(1)

    name, body = parse_proposal(prop)

    if target:
        # 追加到已有技能 (支持 category 嵌套: data-engineering/rag-material-factory/SKILL.md)
        matches = list(SKILLS_ROOT.rglob(f"{target}/SKILL.md"))
        if not matches:
            print(f"✗ 目标技能不存在: {target}")
            sys.exit(1)
        target_path = matches[0]
        section = (
            f"\n## Flywheel 晋升 ({prop.stem}, {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')})\n\n"
            f"{body}\n"
        )
        with target_path.open("a", encoding="utf-8") as f:
            f.write(section)
        dest = target_path
    else:
        # 新技能 (路径白名单内)
        dest_dir = SKILLS_ROOT / "software-development" / slugify(name)
        if not str(dest_dir).startswith(str(SKILLS_ROOT)):
            print("✗ 路径越界, 拒绝")
            sys.exit(1)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "SKILL.md"
        desc = body.split("\n")[1] if len(body.split("\n")) > 1 else name
        front = FRONTMATTER.format(name=slugify(name), desc=desc[:80].replace('"', "'"), tags="flywheel", related="")
        dest.write_text(front + body, encoding="utf-8")

    now = datetime.now(timezone.utc).astimezone()
    rec = {
        "id": f"prom-{now.strftime('%Y%m%d-%H%M%S')}",
        "proposal": prop.stem,
        "skill_name": name,
        "target": str(dest),
        "rationale": rationale,
        "promoted_at": now.isoformat(timespec="seconds"),
        "rollback_until": (now + timedelta(days=7)).isoformat(timespec="seconds"),
        "status": "active",
    }
    append_promotion(rec)
    print(f"✓ 晋升完成: {rec['id']} → {dest}")
    print(f"  回滚窗口: 7 天内 (--rollback {rec['id']})")


def rollback(prom_id: str) -> None:
    recs = load_promotions()
    for rec in recs:
        if rec["id"] == prom_id and rec["status"] == "active":
            target = Path(rec["target"])
            if target.exists():
                if target.name == "SKILL.md" and "software-development" in str(target) and "flywheel" in target.parent.name:
                    shutil.rmtree(target.parent, ignore_errors=True)
                else:
                    # 追加型: 无法精确还原, 标记需人工处理
                    print(f"  ! {target} 为追加型晋升, 需人工还原 (记录已标注)")
                rec["status"] = "rolled_back"
                rec["rolled_back_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                PROMOTIONS_LOG.write_text(
                    "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8"
                )
                print(f"✓ 回滚完成: {prom_id}")
                return
            print(f"✗ 目标不存在: {target}")
            return
    print(f"✗ 未找到活跃晋升记录: {prom_id}")


def list_promotions() -> None:
    for rec in load_promotions():
        print(f"  {rec['id']} [{rec['status']}] {rec['skill_name']} ← {rec['proposal']} ({rec['promoted_at'][:16]})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Flywheel 晋升执行器")
    ap.add_argument("--approve", metavar="PROPOSAL_FILE")
    ap.add_argument("--rationale", default="")
    ap.add_argument("--target", help="追加到已有技能 (缺省=新建技能)")
    ap.add_argument("--rollback", metavar="PROMOTION_ID")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.rollback:
        rollback(args.rollback)
    elif args.approve:
        approve(args.approve, args.rationale, args.target)
    elif args.list:
        list_promotions()
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
