"""
scripts/log_rotate.py — 日志轮转 (P1-2)

策略:
  1. 大小阈值: 文件 > MAX_SIZE (默认 5MB) → 压缩归档 (旧日志滚动)
  2. 天数阈值: 归档文件 > MAX_DAYS (默认 30 天) → 删除
  3. 保留最近 N 个归档

用法:
  uv run python -m scripts.log_rotate              # 默认扫描 pulse 项目
  uv run python -m scripts.log_rotate --dry-run    # 只报告不动作
  uv run python -m scripts.log_rotate --json       # JSON 输出
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_SIZE = 5 * 1024 * 1024   # 5MB 触发轮转
MAX_DAYS = 30                # 归档保留 30 天
KEEP_ARCHIVES = 5            # 每文件保留最近 5 个归档

# 监控的日志文件 (glob 相对 ROOT)
LOG_GLOBS = [
    "data/*.jsonl",          # metrics/traces/inbox/artifacts
    "data/logs/*.log",
    "data/logs/*.jsonl",
    "data/*.log",
    "*.jsonl",
]


def find_logs() -> list[Path]:
    """找到所有日志文件"""
    found: list[Path] = []
    for g in LOG_GLOBS:
        found.extend(ROOT.glob(g))
    # 去重
    seen: set[Path] = set()
    result = []
    for f in found:
        if f not in seen and f.is_file():
            seen.add(f)
            result.append(f)
    return result


def rotate_file(path: Path, dry_run: bool = False) -> str | None:
    """轮转单个日志: 超大小 → 压缩归档; 返回动作描述"""
    size = path.stat().st_size
    if size < MAX_SIZE:
        return None

    # 归档: 改名 + gzip
    ts = time.strftime("%Y%m%d_%H%M%S")
    archive = path.with_suffix(path.suffix + f".{ts}.gz")
    if dry_run:
        return f"WOULD rotate {path.name} ({size/1024:.0f}KB → {archive.name})"

    with path.open("rb") as f_in, gzip.open(archive, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    path.write_text("")  # 清空原文件
    return f"rotated {path.name} ({size/1024:.0f}KB → {archive.name})"


def cleanup_old(keep_days: int = MAX_DAYS, keep_count: int = KEEP_ARCHIVES,
                dry_run: bool = False) -> list[str]:
    """删除过期归档"""
    removed: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)

    for f in ROOT.glob("data/*.gz"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            if dry_run:
                removed.append(f"WOULD delete {f.name}")
            else:
                f.unlink()
                removed.append(f"deleted {f.name}")

    # 每文件保留最近 N 个归档 (按前缀分组)
    archives: dict[str, list[Path]] = {}
    for f in ROOT.glob("data/*.gz"):
        base = f.name.split(".")[0]
        archives.setdefault(base, []).append(f)
    for base, files in archives.items():
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep_count:]:
            if dry_run:
                removed.append(f"WOULD prune {old.name}")
            else:
                old.unlink()
                removed.append(f"pruned {old.name}")

    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只报告")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-size-mb", type=float, default=5, help="大小阈值 MB")
    args = parser.parse_args()

    global MAX_SIZE
    MAX_SIZE = int(args.max_size_mb * 1024 * 1024)

    logs = find_logs()
    actions: list[str] = []
    rotated = 0

    for f in logs:
        action = rotate_file(f, dry_run=args.dry_run)
        if action:
            actions.append(action)
            rotated += 1

    cleaned = cleanup_old(dry_run=args.dry_run)
    actions.extend(cleaned)

    result = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "logs_found": len(logs),
        "rotated": rotated,
        "cleaned": len(cleaned),
        "dry_run": args.dry_run,
        "actions": actions,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 日志轮转 {result['ts']} ===")
        print(f"扫描: {len(logs)} 个日志 | 轮转: {rotated} | 清理: {len(cleaned)}")
        for a in actions:
            print(f"  - {a}")
        if not actions:
            print("  (无操作 — 全部正常)")

    sys.exit(0)


if __name__ == "__main__":
    main()
