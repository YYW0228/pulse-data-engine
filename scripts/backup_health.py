"""
scripts/backup_health.py — 备份健康检查

验证多仓库备份是否健康:
  1. 各仓库 git 未提交数 = 0 (代码已备份)
  2. hermes-brain 上次 push 时间 < 48h (配置已备份)
  3. 关键服务 running (可提供服务)
  4. 退出码: 0=健康 / 1=有告警 (供 cron 判断)

用法:
  uv run python -m scripts.backup_health          # 全量检查
  uv run python -m scripts.backup_health --json   # JSON 输出
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECTS_ROOT = Path("/root/projects")
TIER1 = ["pulse-data-engine", "hermes-brain", "china-ai-governance"]
TIER2 = ["job-scraper", "startalent-enterprise"]
TIER3 = ["kv-cache-governance", "my-intelligence-base", "obsidian_2025",
         "SOVEREIGN-SINGULARITY", "startalent-project-template"]

SERVICES = ["pulse-dashboard", "pulse-compliance", "pulse-wasm", "pulse-metrics", "pulse-telegram"]
MAX_UNPUSHED_AGE_HOURS = 48      # Tier 1/2 活跃仓库
TIER2_MAX_AGE_HOURS = 168        # Tier 2 (startalent) 每周 push 即可


def git_uncommitted(repo: str) -> int:
    """未提交文件数"""
    r = subprocess.run(["git", "-C", str(PROJECTS_ROOT / repo), "status", "--porcelain"],
                       capture_output=True, text=True, timeout=10)
    return len(r.stdout.splitlines())


def git_last_push(repo: str) -> float:
    """上次 push 时间 (unix)"""
    r = subprocess.run(
        ["git", "-C", str(PROJECTS_ROOT / repo), "log", "-1", "--format=%ct", "origin/main"],
        capture_output=True, text=True, timeout=10)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0


def service_active(name: str) -> bool:
    r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=10)
    return r.stdout.strip() == "active"


def disk_usage() -> dict:
    """磁盘空间检查 (P1-3 监控)"""
    r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=10)
    line = r.stdout.splitlines()[-1].split()
    pct = int(line[4].rstrip("%"))
    return {"used_pct": pct, "avail": line[3], "warn": pct >= 80}


def check() -> dict:
    results: dict = {
        "repos": {},
        "services": {},
        "ok": True,
        "alerts": [],
    }

    # 1. 仓库备份健康
    for repo in TIER1 + TIER2 + TIER3:
        try:
            uncommitted = git_uncommitted(repo)
            last_push = git_last_push(repo)
            age_h = (time.time() - last_push) / 3600 if last_push else 999
            # 分级阈值: Tier1/2 活跃 48h, Tier2 特定仓库 168h, Tier3 存档仅需无未提交
            is_archive = repo in TIER3
            is_tier2 = repo in TIER2
            age_limit = TIER2_MAX_AGE_HOURS if is_tier2 else MAX_UNPUSHED_AGE_HOURS
            push_fresh = age_h < age_limit or is_archive
            healthy = uncommitted == 0 and push_fresh
            results["repos"][repo] = {
                "uncommitted": uncommitted,
                "last_push_hours": round(age_h, 1),
                "healthy": healthy,
                "tier": "archive" if is_archive else "active",
            }
            if not healthy:
                results["ok"] = False
                if not is_archive:
                    results["alerts"].append(f"{repo}: 未提交 {uncommitted} / push {age_h:.0f}h 前")
                else:
                    results["alerts"].append(f"{repo}: 未提交 {uncommitted}")
        except Exception as e:
            results["repos"][repo] = {"error": str(e), "healthy": False}
            results["ok"] = False
            results["alerts"].append(f"{repo}: 检查失败 {e}")

    # 2. 服务健康
    for svc in SERVICES:
        active = service_active(svc)
        results["services"][svc] = active
        if not active:
            results["ok"] = False
            results["alerts"].append(f"{svc}: 不在运行")

    # 3. 磁盘空间 (P1-3)
    disk = disk_usage()
    results["disk"] = disk
    if disk["warn"]:
        results["ok"] = False
        results["alerts"].append(f"磁盘 {disk['used_pct']}% (剩 {disk['avail']}) — 需清理")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = check()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("=== 仓库备份健康 ===")
        for repo, r in results["repos"].items():
            mark = "✅" if r.get("healthy") else "🔴"
            print(f"  {mark} {repo}: 未提交={r.get('uncommitted','?')} push={r.get('last_push_hours','?')}h")
        print("=== 服务健康 ===")
        for svc, ok in results["services"].items():
            print(f"  {'✅' if ok else '🔴'} {svc}")
        d = results.get("disk", {})
        print(f"=== 磁盘 ===\n  {'✅' if not d.get('warn') else '🔴'} 已用 {d.get('used_pct','?')}% (剩 {d.get('avail','?')})")
        if results["alerts"]:
            print("\n⚠️ 告警:")
            for a in results["alerts"]:
                print(f"  - {a}")
        print(f"\n总体: {'✅ 健康' if results['ok'] else '🔴 有告警'}")

    sys.exit(0 if results["ok"] else 1)


if __name__ == "__main__":
    main()
