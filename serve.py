"""
serve.py — Pulse Data Engine Streamlit Dashboard

三层数仓可视化 + 数据对账 + 质量 SLA

用法:
  uv run streamlit run serve.py
"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pulse Data Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "data/jobs.duckdb"
PARQUET_PATH = "data/ods_parquet"
LOG_PATH = "data/logs/pulse.jsonl"


@st.cache_resource
def get_conn():
    db = Path(DB_PATH)
    if not db.exists():
        return None
    return duckdb.connect(str(db))


def safe_query(con, sql, default=None):
    try:
        return con.execute(sql).fetchdf()
    except Exception:
        return default if default is not None else pd.DataFrame()


def verify_report(con):
    """手搓对账: 人工 reify verify() 逻辑"""
    try:
        ods_latest = con.execute(
            "SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE"
        ).fetchone()[0]
        dwd = con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0]
        dws_n = con.execute("SELECT COALESCE(SUM(demand_count),0) FROM dws_skill_agg").fetchone()[0]
        excluded = con.execute(
            "SELECT COUNT(*) FROM dwd_cleaned_jobs WHERE category='其他' OR salary_mid IS NULL"
        ).fetchone()[0]
        dlq = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0]
        consistent = (dws_n + excluded) == dwd == ods_latest and dwd > 0
        return {
            "ods_latest": ods_latest,
            "dwd": dwd,
            "dws_count": dws_n,
            "excluded": excluded,
            "dlq": dlq,
            "consistent": consistent,
        }
    except Exception:
        return {}


def last_log_time():
    """读取最近一条日志的时间"""
    log = Path(LOG_PATH)
    if not log.exists():
        return "从未运行"
    try:
        with log.open() as f:
            lines = f.readlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts:
                        return ts[:19]
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    return "未知"


con = get_conn()
report = {}  # 预初始化, stop 后不再使用

# ─── 主面板 ──────────────────────────────────────────────────────────
st.title("🚀 Pulse Data Engine")
st.caption("零成本数据湖 — ODS/DWD/DWS 三层数仓实时对账")

if con is None:
    st.sidebar.warning("数据库不存在，请先运行管道")
    st.error("❌ 数据库 `data/jobs.duckdb` 不存在。请先运行:")
    st.code("uv run python -m pulse.runner", language="bash")
    st.stop()

report = verify_report(con)

# ─── 侧边栏 ──────────────────────────────────────────────────────────
st.sidebar.markdown("## 🚀 Pulse Data Engine")
st.sidebar.markdown("**三层数仓** | **SCD Type 2** | **$0/月**")
st.sidebar.markdown("---")
st.sidebar.metric("ODS 最新版本", report.get("ods_latest", "?"))
st.sidebar.metric("DWD 清洗行", report.get("dwd", "?"))
st.sidebar.metric("DWS 技能聚合", report.get("dws_count", "?"))
st.sidebar.metric("DLQ 死信队列", report.get("dlq", "?"))
consistent = report.get("consistent", False)
st.sidebar.metric("对账一致", "✅" if consistent else "❌", delta_color="off")
st.sidebar.markdown("---")
st.sidebar.caption(f"最后运行: {last_log_time()}")
st.sidebar.markdown("---")
st.sidebar.caption("pulse-data-engine v0.1.0")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "[🔍 SQL 查询 (WASM)](http://localhost:8000/wasm) · "
    "[📖 GitHub](https://github.com/YYW0228/pulse-data-engine)"
)

# ── 行 1: 对账看板 ──────────────────────────────────────────────────
st.subheader("📊 数据对账")
cols = st.columns(6)
metrics = [
    ("ODS 最新", report.get("ods_latest", 0), "{:d} 行"),
    ("DWD 清洗", report.get("dwd", 0), "{:d} 行"),
    ("DWS 汇总", report.get("dws_count", 0), "{:d} 行"),
    ("排除项", report.get("excluded", 0), "{:d} 行"),
    ("DLQ 隔离", report.get("dlq", 0), "{:d} 行"),
    ("对账", "✅" if report.get("consistent") else "❌", "{}"),
]
for col, (label, val, fmt) in zip(cols, metrics):
    col.metric(label, fmt.format(val) if isinstance(val, int) else val, delta_color="off")

# ── 行 2: DWS 技能聚合 ──────────────────────────────────────────────
st.subheader("🏷️ 技能分类薪资")
dws = safe_query(
    con,
    """
    SELECT category, demand_count, avg_salary, p25, p50, p75
    FROM dws_skill_agg
    ORDER BY demand_count DESC
""",
)
if not dws.empty:
    col1, col2 = st.columns([3, 2])
    with col1:
        st.bar_chart(dws.set_index("category")["demand_count"], height=400)
    with col2:
        st.dataframe(
            dws.style.format(
                {
                    "avg_salary": "¥{:,.0f}k",
                    "p25": "¥{:,.0f}k",
                    "p50": "¥{:,.0f}k",
                    "p75": "¥{:,.0f}k",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("暂无 DWS 数据，请先运行 `refresh_dws()`")

# ── 行 3: 城市分布 ──────────────────────────────────────────────────
st.subheader("📍 城市分布")
dwc = safe_query(
    con,
    """
    SELECT city, job_count, avg_salary
    FROM dws_city_agg
    ORDER BY job_count DESC
""",
)
if not dwc.empty:
    col1, col2 = st.columns([3, 2])
    with col1:
        st.bar_chart(dwc.set_index("city")["job_count"], height=350)
    with col2:
        st.dataframe(
            dwc.style.format({"avg_salary": "¥{:,.0f}k"}),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("暂无城市聚合数据")

# ── 行 4: DLQ 分析 ──────────────────────────────────────────────────
st.subheader("⚠️ 死信队列 (DLQ)")

dlq_df = safe_query(
    con,
    """
    SELECT error_type, COUNT(*) as count
    FROM dlq_jobs
    GROUP BY error_type
    ORDER BY count DESC
""",
)
if not dlq_df.empty:
    col1, col2 = st.columns([2, 3])
    with col1:
        st.dataframe(dlq_df, use_container_width=True, hide_index=True)
    with col2:
        st.bar_chart(dlq_df.set_index("error_type"), height=250)
else:
    st.info("DLQ 为空")

# ── 行 5: 质量 SLA ──────────────────────────────────────────────────
st.subheader("✅ 质量 SLA")
try:
    from pulse.monitor import QualitySLA, QualityStatus

    sla = QualitySLA(DB_PATH)
    full = sla.full_report()
    sla_cols = st.columns(4)
    labels = {
        "completeness": "完整性",
        "validity": "有效性",
        "freshness": "新鲜度",
        "consistency": "一致性",
    }
    for col, key in zip(sla_cols, labels):
        info = full.get(key, {})
        status = info.get("status", "?")
        emoji = "✅" if status == QualityStatus.OK else ("⚠️" if status == "WARNING" else "❌")
        col.metric(labels[key], f"{emoji} {status}")
except Exception as e:
    st.warning(f"质量 SLA 检查失败: {e}")

# ── 行 6: Parquet 湖 ────────────────────────────────────────────────
st.subheader("🗄️ Parquet 冷存储")
pq = Path(PARQUET_PATH)
if pq.exists():
    files = list(pq.rglob("*.parquet"))
    total_bytes = sum(f.stat().st_size for f in files)
    st.metric("文件数", len(files))
    st.metric("总大小", f"{total_bytes / 1024:.1f} KB")
    for f in sorted(files):
        st.caption(f"  {f.relative_to(pq.parent)}  ({f.stat().st_size / 1024:.1f} KB)")
else:
    st.info("暂无 Parquet 导出")

# ── 行 7: 最近日志 ──────────────────────────────────────────────────
st.subheader("📋 最近运行日志")
log = Path(LOG_PATH)
if log.exists():
    entries = []
    with log.open() as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # 显示最近 20 条
    recent = entries[-20:]
    log_df = pd.DataFrame(recent)
    if "timestamp" in log_df.columns:
        log_df["timestamp"] = log_df["timestamp"].astype(str).str[:19]
    if "level" in log_df.columns and "message" in log_df.columns:
        display = log_df[["timestamp", "level", "message"]]
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.dataframe(log_df.tail(20), use_container_width=True)
else:
    st.info("无日志记录")

# ── 底部 ──────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "pulse-data-engine · ODS/DWD/DWS · SCD Type 2 · DLQ · $0/月\n\n"
    "数据来源: Remotive API (免费) · 数据量: ~1K 条 · 操作系统托管"
)
