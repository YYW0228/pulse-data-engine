"""
scripts/livestream_script.py — 直播口播脚本生成 (零 LLM, 纯拼接)

从 market_signals 库 (X 大 V 信号) + 市场洞察报告 md → 直播口播脚本 markdown。
本模块不调用任何 LLM/网络, 所有函数可被 tests/ 直接 import 独立测试。

用法:
  from scripts.livestream_script import build_script, load_signals, load_insight
"""

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
    """占位: s2 阶段填充为完整 CLI (加载信号 + 洞察 → 输出脚本)"""
    raise NotImplementedError("main() 由 s2 阶段实现")


if __name__ == "__main__":
    main()
