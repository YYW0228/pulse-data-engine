"""
serve.py — Pulse Data Engine Streamlit Dashboard (直播优化版)

故事线: 一条管道看透 2026 AI 人才市场
  Row 1: 市场总览 (4 Hero metrics)
  Row 2: 技能薪资排行 (最高薪 vs 最高需求)
  Row 3: 公司来源 + 城市分布
  Row 4: 最高薪岗位 TOP 8
  Row 5: Iceberg 时间旅行 + DLQ 教学
  Row 6: 技术栈展示 (Showcase)
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI 人才市场实时情报", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

DB_PATH = "data/jobs.duckdb"
PARQUET_PATH = "data/ods_parquet"


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


# ── 标题 ─────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;font-size:2.5rem'>📊 AI 人才市场实时情报</h1>"
    "<p style='text-align:center;color:#888'>一条零成本管道 · 5个数据源 · 实时采集 · 全面开源</p>",
    unsafe_allow_html=True,
)

con = get_conn()
if con is None:
    st.error("数据库不存在，请先运行: `uv run python -m pulse.runner`")
    st.stop()

# 防 shopify 污染
# ── 来源选择器 ──────────────────────────────────────────────────────
view_mode = st.radio(
    "数据范围",
    ["🌍 全球远程 (美元)", "🇨🇳 国内市场", "🌐 全部数据"],
    horizontal=True,
    index=0,
)
source_filter_map = {
    "🌍 全球远程 (美元)": "source IN ('tavily', 'remotive', 'firecrawl', 'jobicy')",
    "🇨🇳 国内市场": "source = 'chinese_market'",
    "🌐 全部数据": "1=1",
}
SF = source_filter_map[view_mode]

st.markdown("---")

# ── Row 1: Hero 指标 ─────────────────────────────────────────────────

ods_total = int(con.execute(f"SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE AND {SF}").fetchone()[0] or 0)
dwd_total = int(con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0] or 0)
dlq_total = int(con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0)
top_skill = con.execute("SELECT category FROM dws_skill_agg ORDER BY demand_count DESC LIMIT 1").fetchone()
top_skill_name = top_skill[0] if top_skill else "?"
top_salary = con.execute("SELECT category FROM dws_skill_agg ORDER BY p75 DESC LIMIT 1").fetchone()
top_salary_name = top_salary[0] if top_salary else "?"
sources = con.execute(f"SELECT COUNT(DISTINCT source) FROM ods_raw_jobs WHERE {SF}").fetchone()[0] or 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("🧑‍💻 采集岗位数", f"{ods_total:,}", help="ODS 最新版本行数")
c2.metric("🔥 最热门技能", top_skill_name, help="需求量最大的技能分类")
c3.metric("💰 最高薪技能", top_salary_name, help="P75 薪资最高的技能分类")
c4.metric("📡 数据源数", sources)

# ── Row 2: 技能薪资排行 ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🏆 技能分类 — 需求 vs 薪资")

dws = safe_query(con, "SELECT category, demand_count, avg_salary, p25, p50, p75 FROM dws_skill_agg ORDER BY demand_count DESC")
if not dws.empty:
    # 过滤掉 shopify 带来的脏分类
    dws = dws[dws["category"] != "?"]
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("📈 按需求排名")
        st.bar_chart(dws.set_index("category")["demand_count"], height=350, color="#00c853")
    with col2:
        st.dataframe(
            dws.style.format({
                "avg_salary": "¥{:,.0f}k",
                "p25": "¥{:,.0f}k",
                "p50": "¥{:,.0f}k",
                "p75": "¥{:,.0f}k",
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "category": "技能分类",
                "demand_count": "岗位数",
                "avg_salary": "平均薪资",
                "p25": "P25",
                "p50": "P50",
                "p75": "P75",
            },
        )

# ── Row 3: 薪资区间分布 ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## 💰 各技能薪资分布 (P25-P50-P75)")

dws_chart = dws.copy() if not dws.empty else pd.DataFrame()
if not dws_chart.empty:
    chart_data = dws_chart.set_index("category")[["p25", "p50", "p75"]]
    st.bar_chart(chart_data, height=400, color=["#90caf9", "#42a5f5", "#1565c0"])

# ── Row 4: 最高薪岗位 TOP 8 ────────────────────────────────────────
st.markdown("---")
st.markdown("## 🥇 最高薪岗位 TOP 8")

top_jobs = safe_query(
    con,
    f"""
    SELECT job_title, company_name, salary_min_k, salary_max_k, keyword, source
    FROM ods_raw_jobs
    WHERE is_latest=TRUE AND {SF} AND salary_max_k IS NOT NULL
    ORDER BY salary_max_k DESC LIMIT 8
""",
)
if not top_jobs.empty:
    top_jobs["薪资范围"] = top_jobs.apply(lambda r: f"¥{int(r['salary_min_k'] or 0)}k - ¥{int(r['salary_max_k'])}k", axis=1)
    st.dataframe(
        top_jobs[["job_title", "company_name", "薪资范围", "keyword"]].rename(
            columns={"job_title": "岗位", "company_name": "公司", "keyword": "技能标签"}
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("暂无数据")

# ── Row 5: 公司来源 + 城市 ──────────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.markdown("## 📡 数据源分布")
    src_df = safe_query(con, f"SELECT source, COUNT(*) as count FROM ods_raw_jobs WHERE {SF} GROUP BY source ORDER BY count DESC")
    if not src_df.empty:
        st.bar_chart(src_df.set_index("source")["count"], height=300, color="#ff7043")

with col2:
    st.markdown("## 🏙️ 招聘城市 TOP 10")
    city_df = safe_query(con, "SELECT city, job_count, avg_salary FROM dws_city_agg ORDER BY job_count DESC LIMIT 10")
    if not city_df.empty:
        city_df = city_df[~city_df["city"].isin(["?", "未知", ""])]
        st.bar_chart(city_df.set_index("city")["job_count"], height=300, color="#26c6da")

# ── Row 6: 极速技术展示 ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## ⚡ 技术栈一览")

t1, t2, t3, t4 = st.columns(4)
t1.markdown("**采集层**\n\nFetcher v2\nCircuit Breaker\nFull Jitter\n自适应超时")
t2.markdown("**存储层**\n\nDuckDB (热)\nParquet (冷)\nIceberg (时间旅行)\nSCD Type 2")
t3.markdown("**编排层**\n\nDagster 8 Assets\nCron 6h 调度\nPrometheus Metrics\nDLQ 治理")
t4.markdown("**交付层**\n\nStreamlit Dashboard\nDuckDB WASM SQL\n零成本 ($0/月)\n全开源")

# ── 底部 ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#888'>pulse-data-engine · "
    "数据来源: Remotive/Jobicy/Firecrawl · "
    f"最后更新: {Path(DB_PATH).stat().st_mtime_ns if Path(DB_PATH).exists() else '?'}</p>",
    unsafe_allow_html=True,
)
