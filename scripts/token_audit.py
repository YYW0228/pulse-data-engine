"""7 天 token 趋势分析 (cron token-weekly-audit 用, no_agent)
2026-09-12 修复 (时钟跳变事故复盘):
  1) 所有查询加上界 started_at <= now — 排除未来时间戳脏数据 (2027 冻结事故产物)
  2) token 字段 None 安全 — 格式化不再因 NULL 崩溃
"""
import sqlite3
from datetime import datetime, timedelta, timezone

con = sqlite3.connect("/Users/mac/.hermes/state.db")
now_epoch = datetime.now(timezone.utc).timestamp()
week_epoch = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
rows = con.execute(
    """
    SELECT date(started_at, 'unixepoch', 'localtime') d, COUNT(*) n,
           ROUND(SUM(COALESCE(input_tokens,0))) inp,
           ROUND(SUM(COALESCE(output_tokens,0))) out,
           ROUND(SUM(COALESCE(cache_read_tokens,0))) cache_r,
           ROUND(SUM(COALESCE(reasoning_tokens,0))) reas,
           ROUND(SUM(COALESCE(estimated_cost_usd,0)), 3) cost,
           ROUND(SUM(COALESCE(input_tokens,0)) * 1.0 / COUNT(*)) avg_in
    FROM sessions WHERE started_at >= ? AND started_at <= ?
    GROUP BY d ORDER BY d
    """,
    (week_epoch, now_epoch),
).fetchall()
print("日期 | 会话数 | 输入t | 输出t | 缓存读t | 推理t | 成本$ | 均输入/会话")
for r in rows:
    print(f"{r[0]} | {r[1]} | {(r[2] or 0):,} | {(r[3] or 0):,} | {(r[4] or 0):,} | {(r[5] or 0):,} | {(r[6] or 0):.2f} | {(r[7] or 0):,.0f}")

tot = con.execute(
    "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
    "COALESCE(SUM(cache_read_tokens),0), COALESCE(SUM(estimated_cost_usd),0) "
    "FROM sessions WHERE started_at >= ? AND started_at <= ?",
    (week_epoch, now_epoch),
).fetchone()
print(f"7天合计: 输入 {tot[0]:,} / 输出 {tot[1]:,} / 缓存读 {tot[2]:,} / 成本 ${tot[3]:.2f}")

sp = con.execute(
    "SELECT system_prompt, length(system_prompt) FROM sessions "
    "WHERE started_at >= ? AND started_at <= ? AND system_prompt IS NOT NULL "
    "ORDER BY started_at DESC LIMIT 3",
    (week_epoch, now_epoch),
).fetchall()
print("system_prompt 长度:", [(l,) for _, l in sp])

# 长会话 top5 (输入 token 最多的)
top = con.execute(
    "SELECT title, message_count, tool_call_count, input_tokens, output_tokens, estimated_cost_usd "
    "FROM sessions WHERE started_at >= ? AND started_at <= ? ORDER BY input_tokens DESC LIMIT 5",
    (week_epoch, now_epoch),
).fetchall()
print("7天输入最大的会话:")
for t in top:
    print(f"  {str(t[0])[:40]} | msg={t[1] or 0} tools={t[2] or 0} | "
          f"in={(t[3] or 0):,} out={(t[4] or 0):,} | ${(t[5] or 0):.2f}")
