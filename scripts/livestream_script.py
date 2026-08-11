"""
scripts/livestream_script.py — 直播口播脚本生成 (零 LLM, 纯拼接)

从 market_signals 库 (X 大 V 信号) + 市场洞察报告 md → 直播口播脚本 markdown。
本模块不调用任何 LLM/网络, 所有函数可被 tests/ 直接 import 独立测试。

用法:
  from scripts.livestream_script import build_script, load_signals, load_insight
"""

import argparse
import datetime
import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("livestream_script")

# 默认数据路径常量 (与 market_insight.py 一致)
MARKET_DB = Path("data/market_signals.duckdb")
INSIGHT_DIR = Path("data/insights")

# 结尾固定行动号召段
CTA = "💡 行动号召: 评论区扣1领取 AI 岗位薪资表, 关注我每天看 AI 人才市场最新信号。"


def load_signals(db_path: Path) -> list[dict]:
    """从 market_signals 库读取最近 10 条大 V 信号; db 缺失或任何异常 → 空列表 (降级不抛错)"""
    if not db_path.exists():
        return []
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT handle, domain, signal_text FROM market_signals "
                "ORDER BY fetched_at DESC LIMIT 10").fetchall()
        finally:
            con.close()
        return [
            {"handle": r[0], "domain": r[1], "signal_text": r[2]}
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"读取 market_signals 失败, 降级为空: {e}")
        return []


def load_insight(insight_dir: Path) -> str:
    """取 insight_dir 中修改时间最新的 *.md 全文 (最多 500 字符); 目录缺失/无 md → 空字符串"""
    if not insight_dir.exists():
        return ""
    md_files = sorted(
        insight_dir.glob("*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not md_files:
        return ""
    try:
        return md_files[0].read_text(encoding="utf-8")[:500]
    except Exception as e:
        logger.warning(f"读取洞察报告失败, 降级为空: {e}")
        return ""


def build_script(signals: list[dict], insight_text: str, date_str: str) -> str:
    """纯字符串拼接生成直播口播脚本 markdown (无 LLM/网络调用)"""
    lines = [f"# 🎙 直播口播脚本 {date_str}", ""]

    # 开场引语段: 取 signals 前 3 条, 保持传入顺序
    lines.append("## 开场引语")
    if signals:
        for s in signals[:3]:
            lines.append(f"「{s['signal_text']}」 —— @{s['handle']} ({s['domain']})")
    else:
        lines.append("> 今日暂无大 V 信号, 直接进入数据解读。")
    lines.append("")

    # 数据洞察段
    lines.append("## 数据洞察")
    if insight_text:
        lines.append(insight_text)
    else:
        lines.append("> 暂无市场洞察报告。")
    lines.append("")

    # 结尾行动号召段
    lines.append("## 行动号召")
    lines.append(CTA)

    return "\n".join(lines)


def main():
    """s2 CLI: 加载信号 + 洞察 → 生成直播脚本。

    全降级路径: db 缺失/表缺失/洞察目录缺失均不抛异常, 照常生成文件。
    """
    project_root = Path(__file__).resolve().parent.parent
    default_db = project_root / "data" / "market_signals.duckdb"
    default_insight_dir = project_root / "data" / "market_insight"

    parser = argparse.ArgumentParser(description="生成直播口播脚本 (零 LLM, 纯拼接)")
    parser.add_argument(
        "--db", type=Path, default=default_db,
        help=f"market_signals DuckDB 路径 (默认: {default_db})",
    )
    parser.add_argument(
        "--insight-dir", type=Path, default=default_insight_dir,
        help=f"市场洞察 md 目录 (默认: {default_insight_dir})",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="输出 md 路径 (默认: data/livestream/<date>.md)",
    )
    parser.add_argument(
        "--date", default=None,
        help="日期 YYYY-MM-DD (默认: 今天)",
    )
    args = parser.parse_args()

    date_str = args.date or datetime.date.today().isoformat()
    out = args.out or (project_root / "data" / "livestream" / f"{date_str}.md")

    signals = load_signals(args.db)
    insight_text = load_insight(args.insight_dir)
    script = build_script(signals, insight_text, date_str)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(script, encoding="utf-8")
    print(f"已生成: {out}")


if __name__ == "__main__":
    main()
