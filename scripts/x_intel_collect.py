#!/usr/bin/env python3
"""x_intel_collect.py — X 大 V 推文 → 知识库情报 (dap L4 采集)

数据流: dap x @handle → 过滤开发信号 → 生成 x-intel-<date>.md
  → kb_refresh sync_reports 模式 (pulse/data/intel_knowledge/) → 8502 索引

大 V 清单: 开发/商业/开源思想领袖 (可扩展)

用法:
  python scripts/x_intel_collect.py              # 全部大 V
  python scripts/x_intel_collect.py --handles a,b
  python scripts/x_intel_collect.py --dry-run    # 只打印将采集的
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DAP_ROOT = Path.home() / "projects" / "data-acquisition-pipeline"
OUT_DIR = Path.home() / "projects" / "pulse-data-engine" / "data" / "intel_knowledge"
MARKET_DB = Path.home() / "projects" / "pulse-data-engine" / "data" / "market_signals.duckdb"

# 大 V 清单: handle → (领域, 关注理由)
BIG_VS = {
    "turingou": ("harness/agent", "wanman 作者, agent matrix 设计哲学"),
    "karpathy": ("AI/教育", "vibe coding 提出者, LLM 认知"),
    "sama": ("AI/商业", "OpenAI CEO, 行业方向"),
    "miramurati": ("AI/商业", "OpenAI CTO, 产品与安全"),
    "garrytan": ("YC/创业", "YC CEO, agent brain 作者 (gbrain)"),
    "swyx": ("AI/工程", "AI 工程化, agent 生态观察"),
    "lmsys": ("开源/模型", "LLM 评测, 模型排行"),
}

# 核心信号词 (深度 harness/工程信号 — 高价值直通)
CORE_SIGNAL_RE = re.compile(
    r"harness|scaffold|agent loop|agentic|context window|context engineer|"
    r"\bmcp\b|token|rl training|reinforcement learning|self-improving|"
    r"self-modifying|compaction|deep research|tool use|function calling|"
    r"fine-tun|reasoning|long.?horizon|autonomous|multi.?agent|"
    r"swarm|orchestrat|memory system|knowledge graph|eval|benchmark",
    re.IGNORECASE)
# 通用开发词 (弱信号 — 需正文较长且无生活噪音才保留)
GENERAL_SIGNAL_RE = re.compile(
    r"harness|agent|wanman|vibe|开发|工程|产品|代码|sandbank|chatben|tuwa|"
    r"codex|claude|github|git|编程|startup|yc|openai|llm|模型|训练|推理|"
    r"api|cloud|deploy|ship|发布|开源|open.?source|brain|记忆|memory",
    re.IGNORECASE)
# 生活噪音黑名单 (命中即排除, 即使含 codex/agent 等词)
NOISE_RE = re.compile(
    r"猫|喂食|寄养|宠物|狗|旅行|度假|家庭|孩子|娃|吃饭|餐厅|早餐|晚餐|"
    r"跑步|健身|健身房|购物|买了个|搬家|结婚|生日|感冒|医院|看病|"
    r"咖啡|奶茶|电影|追剧|游戏|steam", re.IGNORECASE)

# 跨天去重: 已报告推文指纹 (data/intel_knowledge/.reported_hashes.jsonl)
REPORTED_HASHES = Path(__file__).resolve().parent.parent / "data" / "intel_knowledge" / ".reported_hashes.jsonl"


def is_reported(text: str) -> bool:
    """按文本 hash 检查是否已报告过 (近 7 天)"""
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - 7 * 86400
    seen = set()
    lines = []
    if REPORTED_HASHES.exists():
        for line in REPORTED_HASHES.read_text().splitlines():
            try:
                ts, hh = line.split("\t")
                if float(ts) >= cutoff:
                    lines.append(line)
                    seen.add(hh)
            except ValueError:
                continue
    if h in seen:
        return True
    lines.append(f"{now:.0f}\t{h}")
    REPORTED_HASHES.write_text("\n".join(lines) + "\n")
    return False


def fetch_handle(handle: str, limit: int = 20) -> list[dict]:
    """调 dap x 采集推文 (JSONL stdout)"""
    cmd = [str(DAP_ROOT / ".venv/bin/python"), "-m", "dap", "x",
           f"@{handle}", "--limit", str(limit)]
    r = subprocess.run(cmd, cwd=DAP_ROOT, capture_output=True, text=True,
                       timeout=120)
    tweets = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
            if d.get("text"):
                tweets.append(d)
        except json.JSONDecodeError:
            continue
    return tweets


def clean_text(raw: str) -> str:
    """清洗: 去 @handle 前缀/尾部噪音/登录墙残留"""
    t = re.sub(r"^@\w+(?=\d|\w{3})", "", raw)  # 去 @handle+时间 前缀
    t = re.sub(r"\d{2}:\d{2}.*$", "", t)  # 去视频时长
    t = re.sub(r"(Log in or sign up|Continue with|Scan to get|Terms·Privacy|© 2026).*$",
               "", t, flags=re.DOTALL)
    t = re.sub(r"\s*\d{2,}K?\s*$", "", t)  # 去尾部浏览数
    return t.strip()


def build_report(handle: str, meta: tuple, tweets: list[dict]) -> str:
    domain, reason = meta
    lines = [
        f"# X 信号: @{handle} ({domain})",
        f"> 来源: x.com/{handle} | 采集: dap L4 登录态 | {datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        f"> 关注理由: {reason}",
        "",
    ]
    n = 0
    for t in tweets:
        text = clean_text(t["text"])
        # 过滤: 核心信号直通; 弱信号需正文较长; 噪音黑名单一律排除; 跨天去重
        if len(text) < 30 or NOISE_RE.search(text) or is_reported(text):
            continue
        if not (CORE_SIGNAL_RE.search(text) or (GENERAL_SIGNAL_RE.search(text) and len(text) > 80)):
            continue
        n += 1
        lines.append(f"## 信号 {n}")
        lines.append(text[:400])
        lines.append("")
    if n == 0:
        return ""
    lines.insert(0, f"> 本批 {n} 条开发信号 (过滤后)")
    return "\n".join(lines)


def save_to_market_db(signals: list[dict]) -> int:
    """大 V 信号写入 market_signals 表 (与 DWS 同仓, 供市场洞察/直播消费).

    表: market_signals (handle, domain, signal_text, fetched_at)
    """
    import duckdb
    if not MARKET_DB.exists():
        return 0
    con = duckdb.connect(str(MARKET_DB))
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_signals (
            handle VARCHAR, domain VARCHAR, signal_text VARCHAR,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
    n = 0
    for s in signals:
        con.execute(
            "INSERT INTO market_signals (handle, domain, signal_text) VALUES (?,?,?)",
            [s["handle"], s["domain"], s["text"]])
        n += 1
    con.close()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handles", default="", help="逗号分隔, 覆盖默认清单")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    handles = [h.strip() for h in args.handles.split(",") if h.strip()] or list(BIG_VS)
    if args.dry_run:
        print(f"将采集 {len(handles)} 个大 V: {', '.join(handles)}")
        print(f"输出: {OUT_DIR}/x-intel-<date>.md → kb_refresh 索引")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"x-intel-{date_str}.md"
    all_lines: list[str] = []
    total = 0
    all_signals: list[dict] = []
    for h in handles:
        if h not in BIG_VS:
            print(f"⚠️ 未知 handle {h}, 跳过 (加入 BIG_VS 清单)")
            continue
        try:
            tweets = fetch_handle(h, args.limit)
            report = build_report(h, BIG_VS[h], tweets)
            if report:
                all_lines.append(report)
                total += 1
            # 收集市场信号 (去重清洗后的开发信号)
            for t in tweets:
                text = clean_text(t["text"])
                if len(text) >= 30 and not NOISE_RE.search(text) and \
                        (CORE_SIGNAL_RE.search(text) or GENERAL_SIGNAL_RE.search(text)):
                    all_signals.append({"handle": h, "domain": BIG_VS[h][0],
                                        "text": text[:400]})
            print(f"✓ @{h}: {len(tweets)} 推文 → {len(report.splitlines()) if report else 0} 行报告")
        except Exception as e:
            print(f"✗ @{h}: {e}")

    # 市场信号入库 (market_signals 表, 与 DWS 同仓)
    market_n = 0
    if all_signals:
        market_n = save_to_market_db(all_signals)
        print(f"→ 市场信号入库: {market_n} 条 → market_signals (market_signals.duckdb)")

    if not all_lines:
        print("无信号产出 (所有大 V 无开发内容或采集失败)")
        return 1
    out_file.write_text("\n\n---\n\n".join(all_lines), encoding="utf-8")
    print(f"\n✅ {total}/{len(handles)} 大 V 产出 → {out_file}")
    print(f"   kb_refresh 将自动同步索引 (scene2_intel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
