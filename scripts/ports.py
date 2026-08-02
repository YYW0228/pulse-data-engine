"""
scripts/ports.py — Pulse 服务端口管理器

列出所有服务 + 端口 + PID + 状态, 检测冲突, 一键清理。

用法:
  uv run python -m scripts.ports                 # 列出所有服务状态
  uv run python -m scripts.ports --check         # 只检查冲突
  uv run python -m scripts.ports --clean         # 清理冲突进程
  uv run python -m scripts.ports --kill 8502     # 杀掉指定端口占用者

服务端口分配表:
  8501  Pulse Dashboard (serve.py)
  8502  合规问答助手 (serve_compliance.py)
  8000  WASM SQL 查询 (wasm_server)
  9464  Prometheus Metrics (metrics_server)
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass

# ── 端口分配表 ────────────────────────────────────────────────────────
SERVICES = [
    {"name": "dashboard", "port": 8501, "cmd": "serve.py", "desc": "AI 人才市场情报"},
    {"name": "compliance", "port": 8502, "cmd": "serve_compliance.py", "desc": "合规问答助手"},
    {"name": "wasm", "port": 8000, "cmd": "wasm_server", "desc": "WASM SQL 查询"},
    {"name": "metrics", "port": 9464, "cmd": "metrics_server", "desc": "Prometheus Metrics"},
    {"name": "telegram", "port": None, "cmd": "telegram_poller", "desc": "Telegram 消息轮询"},
]


@dataclass
class PortInfo:
    port: int
    pid: int
    cmd: str


def find_port_user(port: int) -> PortInfo | None:
    """查找端口占用者 (只查 LISTEN 状态)"""
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        )
        pids = out.stdout.strip().splitlines()
        if not pids:
            return None
        pid = int(pids[0])
        cmd_out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "cmd="],
            capture_output=True, text=True, timeout=5,
        )
        return PortInfo(port=port, pid=pid, cmd=cmd_out.stdout.strip())
    except Exception:
        return None


def check_expected(port: int, cmd_hint: str) -> tuple[bool, PortInfo | None]:
    """检查端口占用者是否符合预期"""
    info = find_port_user(port)
    if info is None:
        return False, None
    expected = cmd_hint in info.cmd
    return expected, info


def list_services(json_out: bool = False) -> list[dict]:
    """列出所有服务状态"""
    results = []
    for svc in SERVICES:
        if svc["port"] is None:
            # 无端口服务: 检查进程
            proc = subprocess.run(
                ["pgrep", "-f", svc["cmd"]],
                capture_output=True, text=True, timeout=5,
            )
            pids = proc.stdout.strip().splitlines()
            status = "running" if pids else "stopped"
            results.append({
                "name": svc["name"], "port": None, "desc": svc["desc"],
                "status": status, "pid": pids[0] if pids else None, "conflict": False,
            })
            continue

        expected, info = check_expected(svc["port"], svc["cmd"])
        if info is None:
            results.append({
                "name": svc["name"], "port": svc["port"], "desc": svc["desc"],
                "status": "stopped", "pid": None, "conflict": False,
            })
        elif expected:
            results.append({
                "name": svc["name"], "port": svc["port"], "desc": svc["desc"],
                "status": "running", "pid": info.pid, "conflict": False,
            })
        else:
            results.append({
                "name": svc["name"], "port": svc["port"], "desc": svc["desc"],
                "status": "CONFLICT", "pid": info.pid,
                "conflict": True, "occupied_by": info.cmd,
            })

    if json_out:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"{'服务':<12} {'端口':<7} {'状态':<12} {'PID':<8} 说明")
        print("-" * 70)
        for r in results:
            port = str(r["port"]) if r["port"] else "-"
            status = r["status"]
            if r["conflict"]:
                status = f"⚠️ 冲突 (被 {r.get('occupied_by','?')[:40]})"
            pid = str(r["pid"]) if r["pid"] else "-"
            print(f"{r['name']:<12} {port:<7} {status:<30} {pid:<8} {r['desc']}")

    return results


def clean_conflicts(dry_run: bool = False) -> int:
    """清理冲突进程 (端口被非预期进程占用)"""
    killed = 0
    for svc in SERVICES:
        if svc["port"] is None:
            continue
        expected, info = check_expected(svc["port"], svc["cmd"])
        if info is not None and not expected:
            print(f"🔴 冲突: 端口 {svc['port']} 被 {info.cmd[:50]} (PID {info.pid}) 占用")
            if not dry_run:
                try:
                    os.kill(info.pid, 15)  # SIGTERM
                    print(f"   ✅ 已终止 PID {info.pid}")
                    killed += 1
                except Exception as e:
                    print(f"   ❌ 终止失败: {e}")
    return killed


def main():
    parser = argparse.ArgumentParser(description="Pulse 服务端口管理器")
    parser.add_argument("--check", action="store_true", help="只检查冲突")
    parser.add_argument("--clean", action="store_true", help="清理冲突进程")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--kill", type=int, help="杀掉指定端口占用者")
    args = parser.parse_args()

    if args.kill:
        info = find_port_user(args.kill)
        if info:
            os.kill(info.pid, 15)
            print(f"✅ 已终止 PID {info.pid} (端口 {args.kill})")
        else:
            print(f"端口 {args.kill} 无占用")
        return

    if args.clean:
        n = clean_conflicts()
        print(f"\n清理完成: {n} 个冲突进程")
        return

    results = list_services(json_out=args.json)

    if args.check:
        conflicts = [r for r in results if r.get("conflict")]
        if conflicts:
            print(f"\n⚠️ 发现 {len(conflicts)} 个端口冲突! 用 --clean 清理")
            sys.exit(1)
        print("\n✅ 无端口冲突")


if __name__ == "__main__":
    main()
