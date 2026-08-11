"""
scripts/kb_refresh.py — 知识库持续迭代管道 (护城河)

闭环: 情报采集 → 同步 → 增量索引 → 验证
  1. 运行 intel_scraper_v2 (抓取最新法规情报)
  2. 新报告同步到 data/scene2_intel/
  3. 增量索引 (compliance_index 幂等, 同 doc 替换)
  4. 验证 (块数对账 + 缓存命中率/成本指标)

用法:
  uv run python -m scripts.kb_refresh            # 完整刷新
  uv run python -m scripts.kb_refresh --no-scrape # 只同步+索引 (跳过采集)
  uv run python -m scripts.kb_refresh --json      # JSON 输出

设计原则:
  - 幂等: 重复跑不产生重复块 (compliance_index 增量替换语义)
  - 隔离: 只动 scene2_intel 目录, 不碰客户库
  - 可观测: 每次刷新记录指标 (耗时/块数/新增)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import os
from pathlib import Path

INTEL_SRC = Path.home() / "projects" / "china-ai-governance" / "reports"
INTEL_DST = Path(__file__).resolve().parent.parent / "data" / "scene2_intel"
MARKET_SRC = Path.home() / "projects" / "pulse-data-engine" / "data" / "market_knowledge"  # job-scraper CI 回流 (Mac runner)
MARKET_DST = Path(__file__).resolve().parent.parent / "data" / "market_knowledge"
SCRAPER = Path.home() / "projects" / "china-ai-governance" / "_intel_scraper_v2.py"
INDEX_CMD = [
    sys.executable,
    "-m",
    "scripts.compliance_index",
    "--source",
    str(INTEL_DST),
    "--include-jsonl",
]
# references 稳定参考文档源 (china-ai-governance 法律参考 — 随仓库更新自动入库)
REFERENCES_SRC = Path.home() / "projects" / "china-ai-governance" / "ai-governance-legal" / "references"
REFERENCES_DST = Path(__file__).resolve().parent.parent / "data" / "references"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "compliance.duckdb"


def sync_reports() -> tuple[int, list[str]]:
    """同步新报告到 scene2_intel, 返回 (新增数, 新增文件名)"""
    INTEL_DST.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in INTEL_DST.glob("*.md")}
    added: list[str] = []
    for src in sorted(INTEL_SRC.glob("intel-*.md")):
        if src.name not in existing:
            shutil.copy2(src, INTEL_DST / src.name)
            added.append(src.name)
    return len(added), added


def sync_market_insight() -> tuple[int, list[str]]:
    """同步市场洞察 (job-scraper CI 产物) → market_knowledge"""
    MARKET_DST.mkdir(parents=True, exist_ok=True)
    if not MARKET_SRC.exists():
        return 0, []
    existing = {p.name for p in MARKET_DST.glob("*.md")}
    added: list[str] = []
    for src in sorted(MARKET_SRC.glob("market-insight-*.md")):
        if src.name not in existing:
            shutil.copy2(src, MARKET_DST / src.name)
            added.append(src.name)
    return len(added), added


def _scraper_interpreter() -> str:
    """探测能运行 scraper 的 Python 解释器.

    kb_refresh 运行在项目 venv (uv run) 下, sys.executable 是 venv python;
    但 scraper (china-ai-governance/_intel_scraper_v2.py, shebang
    `#!/usr/bin/env python3`) 依赖 bs4/requests, 只装在系统 python。
    且 uv run 会把 venv 提前到 PATH, shutil.which("python3") 也会命中 venv。
    因此按候选顺序探测, 返回第一个能 import bs4+requests 的解释器。
    """
    import shutil

    dap_root = os.environ.get('DAP_ROOT', '')
    dap_python = Path(dap_root) / '.venv' / 'bin' / 'python' if dap_root else None

    candidates = [
        "/usr/bin/python3",
        "/usr/local/lib/hermes-agent/venv/bin/python3",
        *( [str(dap_python)] if dap_python and dap_python.exists() else [] ),
        shutil.which("python3") or "",
    ]
    failures: list[str] = []
    for cand in candidates:
        if not cand or not Path(cand).exists():
            continue
        try:
            r = subprocess.run(
                [cand, "-c", "import bs4, requests"],
                capture_output=True,
                timeout=30,
            )
            if r.returncode == 0:
                return cand
            err_text = r.stderr or ""
            if isinstance(err_text, bytes):
                err_text = err_text.decode("utf-8", "replace")
            failures.append(f"{cand}: {err_text.strip()[-200:]}")
        except Exception as e:
            failures.append(f"{cand}: {e!r}")
    print(f"[kb_refresh] 未找到可用 scraper 解释器: {failures}", file=sys.stderr)
    # 兜底: 原行为 (venv python), 失败会在 run_scraper 中体现
    return sys.executable


def run_scraper(timeout: int = 240) -> bool:
    """运行情报采集器 (使用带 bs4/requests 的系统 python)"""
    if not SCRAPER.exists():
        return False
    py = _scraper_interpreter()
    try:
        r = subprocess.run([py, str(SCRAPER)], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def sync_references() -> tuple[int, list[str]]:
    """同步 china-ai-governance 法律参考文档 (references/) → data/references"""
    REFERENCES_DST.mkdir(parents=True, exist_ok=True)
    if not REFERENCES_SRC.exists():
        return 0, []
    existing = {p.name for p in REFERENCES_DST.glob("*.md")}
    added: list[str] = []
    for src in sorted(REFERENCES_SRC.rglob("*.md")):
        if src.name not in existing:
            shutil.copy2(src, REFERENCES_DST / src.name)
            added.append(src.name)
        elif src.stat().st_mtime > (REFERENCES_DST / src.name).stat().st_mtime:
            # 已存在但更新 → 覆盖 (同步最新版本)
            shutil.copy2(src, REFERENCES_DST / src.name)
            added.append(src.name + " (更新)")
    return len(added), added


def index() -> dict:
    """增量索引 (幂等)"""
    r = subprocess.run(INDEX_CMD, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    chunks = 0
    docs = 0
    for line in out.splitlines():
        if "分块:" in line:
            try:
                chunks = int(line.split(":")[1].strip().replace("个", ""))
            except ValueError:
                pass
        if "文档:" in line:
            try:
                docs = int(line.split(":")[1].strip().replace("个", ""))
            except ValueError:
                pass
    return {"exit": r.returncode, "docs": docs, "chunks": chunks}


def verify() -> dict:
    """块数对账"""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    total = con.execute("SELECT COUNT(*) FROM compliance_chunks").fetchone()[0]
    intel = con.execute(
        "SELECT COUNT(*) FROM compliance_chunks WHERE doc_name LIKE 'intel-%'"
    ).fetchone()[0]
    con.close()
    return {"total": total, "intel": intel}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-scrape", action="store_true", help="跳过采集")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    result: dict = {"step": "kb_refresh", "ts": time.strftime("%Y-%m-%d %H:%M:%S")}

    # 1. 采集 (可选)
    if not args.no_scrape:
        scraper_ok = run_scraper()
        result["scraper"] = "ok" if scraper_ok else "skipped/failed"
    else:
        result["scraper"] = "skipped (--no-scrape)"

    # 2. 同步新报告 (情报 + 市场 + references)
    added_n, added = sync_reports()
    result["synced"] = added_n
    result["new_reports"] = added
    m_added, m_added_names = sync_market_insight()
    result["market_synced"] = m_added
    result["market_new"] = m_added_names
    r_added, r_added_names = sync_references()
    result["refs_synced"] = r_added
    result["refs_new"] = r_added_names

    # 3. 增量索引 (情报库 + 市场知识 + references)
    idx = index()
    # 市场知识独立索引 (幂等)
    m_idx = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compliance_index",
            "--source",
            str(MARKET_DST),
            "--include-jsonl",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=300,
    )
    r_idx = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.compliance_index",
            "--source",
            str(REFERENCES_DST),
            "--include-jsonl",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=300,
    )
    result["index"] = idx
    result["market_index_exit"] = m_idx.returncode
    result["refs_index_exit"] = r_idx.returncode

    # 4. 验证
    v = verify()
    result["verify"] = v

    result["elapsed_s"] = round(time.time() - t0, 1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 知识库刷新 {result['ts']} ===")
        print(f"采集: {result['scraper']}")
        print(f"情报同步: +{added_n} 份报告 {added}")
        print(f"市场同步: +{m_added} 份报告 {m_added_names}")
        print(f"索引: {idx}")
        print(f"对账: 总{result['verify']['total']}块 (情报{result['verify']['intel']}块)")
        print(f"耗时: {result['elapsed_s']}s")
        ok = idx.get("exit") == 0 and result["verify"]["total"] > 0
        print(f"结果: {'✅ 成功' if ok else '❌ 失败'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
