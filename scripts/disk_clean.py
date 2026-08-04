"""
scripts/disk_clean.py — 磁盘清理 (P1-3)

安全清理项 (可重建/已吞噬):
  1. harness-lab 已吞噬的 clone 仓库 (deer-flow/Kun/boxsh 等, 原创分析保留)
  2. hermes state-snapshots 旧快照 (保留最近 2 个)
  3. 过期 .gz 归档 (log_rotate 产物, 保留最近)

保守清理 (需确认):
  4. pip/uv 缓存
  5. 旧 venv

用法:
  uv run python -m scripts.disk_clean --dry-run   # 只报告
  uv run python -m scripts.disk_clean             # 执行安全清理
  uv run python -m scripts.disk_clean --all       # 含保守清理
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

# 已吞噬的 clone (原创分析在 repo/ + *.md, clone 可删)
HARNESS_CLONES = [
    "deer-flow", "Kun", "DeepSeek-Reasonix", "san",
    "learn-claude-code-rs", "boxsh", "mini-claude-code",
]
HARNESS_LAB = Path("/root/harness-lab")
SNAPSHOTS = Path("/root/.hermes/state-snapshots")
KEEP_SNAPSHOTS = 2
KEEP_GZ = 5


def clean_clones(dry_run: bool) -> tuple[int, float]:
    """清理已吞噬 clone, 返回 (删除数, 释放 MB)"""
    freed = 0
    count = 0
    for name in HARNESS_CLONES:
        d = HARNESS_LAB / name
        if d.is_dir():
            size_mb = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e6
            if dry_run:
                print(f"  [dry] WOULD delete {name}/ ({size_mb:.0f}MB)")
            else:
                shutil.rmtree(d)
                print(f"  ✅ deleted {name}/ ({size_mb:.0f}MB)")
            freed += size_mb
            count += 1
    return count, freed


def clean_snapshots(dry_run: bool) -> tuple[int, float]:
    """清理旧快照 (保留最近 KEEP_SNAPSHOTS)"""
    if not SNAPSHOTS.exists():
        return 0, 0
    snaps = sorted(SNAPSHOTS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    freed = 0
    count = 0
    for old in snaps[KEEP_SNAPSHOTS:]:
        if old.is_dir():
            size_mb = sum(f.stat().st_size for f in old.rglob("*") if f.is_file()) / 1e6
            if dry_run:
                print(f"  [dry] WOULD delete snapshot {old.name} ({size_mb:.0f}MB)")
            else:
                shutil.rmtree(old)
                print(f"  ✅ deleted snapshot {old.name} ({size_mb:.0f}MB)")
            freed += size_mb
            count += 1
    return count, freed


def clean_gz(dry_run: bool) -> tuple[int, float]:
    """清理旧 .gz 归档 (log_rotate 产物, 每文件保留 KEEP_GZ)"""
    freed = 0
    count = 0
    gz_files = sorted(Path("/root/projects/pulse-data-engine/data").glob("*.gz"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    # 按前缀分组 (compliance_metrics / compliance_traces / pulse)
    groups: dict[str, list[Path]] = {}
    for f in gz_files:
        base = f.name.split(".")[0]
        groups.setdefault(base, []).append(f)
    for base, files in groups.items():
        for old in files[KEEP_GZ:]:
            size = old.stat().st_size
            if dry_run:
                print(f"  [dry] WOULD delete {old.name} ({size/1e6:.1f}MB)")
            else:
                old.unlink()
                print(f"  ✅ deleted {old.name} ({size/1e6:.1f}MB)")
            freed += size / 1e6
            count += 1
    return count, freed


def clean_uv_cache(dry_run: bool) -> tuple[int, float]:
    """uv 缓存 (保守)"""
    uv_cache = Path.home() / ".cache" / "uv"
    if not uv_cache.exists():
        return 0, 0
    size_mb = sum(f.stat().st_size for f in uv_cache.rglob("*") if f.is_file()) / 1e6
    if dry_run:
        print(f"  [dry] WOULD clear uv cache ({size_mb:.0f}MB)")
    else:
        shutil.rmtree(uv_cache)
        print(f"  ✅ cleared uv cache ({size_mb:.0f}MB)")
    return 1, size_mb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true", help="含保守清理")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    total_freed = 0.0
    results: dict[str, int] = {}

    print(f"=== 磁盘清理 {'(dry-run)' if args.dry_run else ''} ===")

    n, freed = clean_clones(args.dry_run)
    results["clones"] = n
    total_freed += freed

    n, freed = clean_snapshots(args.dry_run)
    results["snapshots"] = n
    total_freed += freed

    n, freed = clean_gz(args.dry_run)
    results["gz"] = n
    total_freed += freed

    if args.all:
        n, freed = clean_uv_cache(args.dry_run)
        results["uv_cache"] = n
        total_freed += freed

    print(f"\n可释放: {total_freed:.0f}MB")
    print(f"耗时: {time.time()-t0:.1f}s")

    if args.json:
        print(json.dumps({"freed_mb": round(total_freed), **results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
