"""
serve_boom.py — 爆款监控 Streamlit Dashboard

用法:
  uv run streamlit run serve_boom.py --server.port 8502 --server.headless true

4 个页面:
  / ?page=dashboard  (默认)  总览
  / ?page=feed               爆款列表
  / ?page=work&id=xxx        作品详情
  / ?page=creator            创作者档案
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs

import duckdb
import pandas as pd
import streamlit as st

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(
    page_title="爆款监控 Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .grade-T3 { color: #d32f2f; font-weight: 700; }
    .grade-T2 { color: #f57c00; font-weight: 600; }
    .grade-T1 { color: #ff8f00; font-weight: 500; }
    .grade-ordinary { color: #757575; }
    .metric-card {
        background: #1e1e2e; border-radius: 12px; padding: 1rem; text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; }
    .metric-label { font-size: 0.85rem; color: #888; }
    .boom-card {
        background: #1e1e2e; border-radius: 8px; padding: 0.8rem 1rem;
        margin-bottom: 0.5rem; border-left: 4px solid #555;
    }
    .boom-card.T3 { border-left-color: #d32f2f; }
    .boom-card.T2 { border-left-color: #f57c00; }
    .boom-card.T1 { border-left-color: #ff8f00; }
    .life-tag {
        display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px;
        font-size: 0.75rem; font-weight: 600;
    }
    .life-时效 { background: #ff5252; color: #fff; }
    .life-长青 { background: #69f0ae; color: #000; }
</style>
""", unsafe_allow_html=True)


# ── 数据库连接 ─────────────────────────────────────────────────────

BOOM_DB = Path("data/boom.duckdb")


@st.cache_resource
def get_conn() -> duckdb.DuckDBPyConnection | None:
    if not BOOM_DB.exists():
        return None
    return duckdb.connect(str(BOOM_DB))


def safe_query(sql: str, default: pd.DataFrame | None = None) -> pd.DataFrame:
    con = get_conn()
    if con is None:
        return default if default is not None else pd.DataFrame()
    try:
        return con.execute(sql).fetchdf()
    except Exception as e:
        st.error(f"查询失败: {e}")
        return default if default is not None else pd.DataFrame()


# ── 页面路由 ─────────────────────────────────────────────────────────

query = st.query_params if hasattr(st, 'query_params') else {}
page = query.get("page", "dashboard")
work_id = query.get("work_id", [None])[0] if isinstance(query.get("work_id"), list) else query.get("work_id", None)
creator_name = query.get("creator", [None])[0] if isinstance(query.get("creator"), list) else query.get("creator", None)

# ── 侧边栏导航 ───────────────────────────────────────────────────────

st.sidebar.markdown("## 🔥 爆款监控")
st.sidebar.markdown("---")

nav_page = st.sidebar.radio(
    "导航", ["📊 总览", "🔥 爆款列表", "👤 创作者档案", "⚙️ 设置"],
    index=0 if page == "dashboard" else 1 if page == "feed" else 2 if page == "creator" else 0,
)

if nav_page == "📊 总览":
    page = "dashboard"
elif nav_page == "🔥 爆款列表":
    page = "feed"
elif nav_page == "👤 创作者档案":
    page = "creator"
elif nav_page == "⚙️ 设置":
    page = "settings"

st.sidebar.markdown("---")

if work_id and page != "work":
    st.sidebar.info(f"当前作品: {work_id[:30]}...")

# ── 检查数据库 ───────────────────────────────────────────────────────

con = get_conn()
if con is None:
    st.warning("📦 boom.duckdb 不存在。请先运行: `uv run python scripts/run_boom_collect.py`")
    st.markdown("""
    爆款监控系统使用独立数据库，与 jobs.duckdb 隔离。
    
    初次使用:
    ```bash
    cd /root/projects/pulse-data-engine
    uv run python scripts/run_boom_collect.py
    uv run streamlit run serve_boom.py --server.port 8502 --server.headless true
    ```
    """)
    st.stop()

# ══════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════

if page == "dashboard" and con:

    st.markdown("## 🔥 爆款监控 · 总览")

    # Hero 指标
    total_works = int(con.execute("SELECT COUNT(*) FROM works").fetchone()[0] or 0)
    t3 = int(con.execute("SELECT COUNT(*) FROM works WHERE grade_code='T3'").fetchone()[0] or 0)
    t2 = int(con.execute("SELECT COUNT(*) FROM works WHERE grade_code='T2'").fetchone()[0] or 0)
    t1 = int(con.execute("SELECT COUNT(*) FROM works WHERE grade_code='T1'").fetchone()[0] or 0)
    analyzed = int(con.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] or 0)
    creators = int(con.execute("SELECT COUNT(*) FROM creators").fetchone()[0] or 0)
    scan_runs = int(con.execute("SELECT COUNT(*) FROM scan_log").fetchone()[0] or 0)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("📦 作品总数", total_works)
    c2.metric("🔴 T3 现象级", t3)
    c3.metric("🟠 T2 爆款", t2)
    c4.metric("🟡 T1 小爆", t1)
    c5.metric("🧠 AI分析", analyzed)
    c6.metric("👤 对标数", creators)

    st.markdown("---")

    # 平台分布
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📱 平台分布")
        plat_df = safe_query("SELECT platform, COUNT(*) as cnt FROM works GROUP BY platform ORDER BY cnt DESC")
        if not plat_df.empty:
            st.bar_chart(plat_df.set_index("platform")["cnt"], color="#42a5f5")

    with col2:
        st.markdown("### 🏆 爆款分级")
        grade_df = safe_query("""
            SELECT grade_code, COUNT(*) as cnt FROM works
            WHERE grade_code IN ('T3', 'T2', 'T1')
            GROUP BY grade_code ORDER BY cnt DESC
        """)
        if not grade_df.empty:
            colors = {"T3": "#d32f2f", "T2": "#f57c00", "T1": "#ff8f00"}
            chart = grade_df.set_index("grade_code")["cnt"]
            st.bar_chart(chart, color=[colors.get(g, "#888") for g in chart.index])

    st.markdown("---")
    st.markdown("### 🔥 最近爆款")

    recent = safe_query("""
        SELECT w.work_id, w.title, w.platform, w.grade_code, w.grade_label,
               w.r_value, w.m_value, w.likes, a.life, a.summary
        FROM works w
        LEFT JOIN analyses a ON w.work_id = a.work_id
        WHERE w.grade_code IN ('T3', 'T2')
        ORDER BY w.graded_at DESC LIMIT 10
    """)

    if not recent.empty:
        for _, row in recent.iterrows():
            grade = row["grade_code"]
            life = row.get("life", "长青")
            title = str(row.get("title", ""))[:60]
            platform = row.get("platform", "")
            r_val = row.get("r_value", 0)
            likes = int(row.get("likes", 0))
            summary = str(row.get("summary", ""))[:80]

            st.markdown(
                f"""<div class="boom-card {grade}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span><b>{title}</b></span>
                        <span>
                            <span class="life-tag life-{life}">{life}</span>
                            &nbsp;<span class="grade-{grade}">{grade} {row.get('grade_label','')}</span>
                        </span>
                    </div>
                    <div style="font-size:0.85rem;color:#888;margin-top:0.3rem">
                        {platform} · R={r_val:.1f} · ❤️{likes:,} · {summary}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("暂无爆款数据，请先运行采集")

# ══════════════════════════════════════════════════════════════════════
# PAGE: BOOM FEED
# ══════════════════════════════════════════════════════════════════════

elif page == "feed" and con:

    st.markdown("## 🔥 爆款列表")

    # 筛选栏
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        grade_filter = st.selectbox("分级", ["全部", "T3 现象级", "T2 爆款", "T1 小爆"])
    with fcol2:
        plat_filter = st.selectbox("平台", ["全部", "douyin", "xhs", "youtube"])
    with fcol3:
        life_filter = st.selectbox("时效性", ["全部", "时效", "长青"])

    where_clauses = ["w.grade_code IN ('T3', 'T2', 'T1')"]
    if grade_filter != "全部":
        code = grade_filter.split()[0]
        where_clauses.append(f"w.grade_code = '{code}'")
    if plat_filter != "全部":
        where_clauses.append(f"w.platform = '{plat_filter}'")
    if life_filter != "全部":
        where_clauses.append(f"a.life = '{life_filter}'")

    where_sql = " AND ".join(where_clauses)

    works = safe_query(f"""
        SELECT w.*, a.summary, a.factors, a.life, a.life_reason, a.confidence
        FROM works w
        LEFT JOIN analyses a ON w.work_id = a.work_id
        WHERE {where_sql}
        ORDER BY w.graded_at DESC
        LIMIT 50
    """)

    if not works.empty:
        for _, row in works.iterrows():
            grade = row["grade_code"]
            life = row.get("life", "长青") if row.get("life") else "长青"
            title = str(row.get("title", ""))[:60]
            platform = row.get("platform", "")
            r_val = row.get("r_value", 0)
            m_val = row.get("m_value", 0)
            likes = int(row.get("likes", 0))
            summary = str(row.get("summary", ""))[:100] if row.get("summary") else ""
            factors_raw = row.get("factors", "[]")
            factors = json.loads(factors_raw) if isinstance(factors_raw, str) else []
            factors_str = " · ".join(factors[:3]) if factors else ""

            st.markdown(
                f"""<div class="boom-card {grade}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span><b>{title}</b></span>
                        <span style="display:flex;gap:0.5rem;align-items:center">
                            <span class="life-tag life-{life}">{life}</span>
                            <span class="grade-{grade}">● {grade}</span>
                        </span>
                    </div>
                    <div style="font-size:0.85rem;color:#aaa;margin-top:0.3rem">
                        {platform} · ❤️{likes:,} · R={r_val:.1f} · M={m_val:.3f}
                    </div>
                    <div style="font-size:0.85rem;color:#888;margin-top:0.2rem">
                        {summary}
                        {' · ' + factors_str if factors_str else ''}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("没有匹配的爆款")

# ══════════════════════════════════════════════════════════════════════
# PAGE: WORK DETAIL
# ══════════════════════════════════════════════════════════════════════

elif page == "work" and work_id and con:

    work = safe_query(
        "SELECT w.*, a.* FROM works w LEFT JOIN analyses a ON w.work_id = a.work_id WHERE w.work_id = ?",
        [work_id],
    )
    if work.empty:
        st.error(f"作品不存在: {work_id}")
    else:
        row = work.iloc[0]
        st.markdown(f"## 📄 {row.get('title', '无标题')}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔥 分级", f"{row['grade_code']} {row.get('grade_label','')}")
        c2.metric("📈 R 值", f"{row['r_value']:.2f}")
        c3.metric("📊 M 值", f"{row['m_value']:.4f}")
        c4.metric("❤️ 点赞", f"{int(row['likes']):,}")

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**平台信息**")
            st.write(f"平台: {row.get('platform', '')}")
            st.write(f"创作者: {row.get('creator_name', '')}")
            st.write(f"发布时间: {row.get('create_time', 0)}")
            st.write(f"评论: {int(row.get('comments', 0)):,}")
            st.write(f"收藏: {int(row.get('collects', 0)):,}")
            st.write(f"分享: {int(row.get('shares', 0)):,}")

        with col2:
            st.markdown("**评分证据 (冻结)**")
            st.write(f"评分时粉丝: {int(row.get('creator_followers_at_grade', 0)):,}")
            st.write(f"基线中位数: {row.get('baseline_at_grade', 0):.1f}")
            st.write(f"M 基准: {row.get('m_base', 0):.3f}")
            st.write(f"粉丝体量层: {row.get('tier', '')}")
            st.write(f"评分时间戳: {row.get('graded_at', 0)}")

        st.markdown("---")
        st.markdown("### 🧠 L1 分析")

        analysis_cols = ["summary", "life", "life_reason", "confidence", "factors", "caveats"]
        has_analysis = any(row.get(c) for c in analysis_cols if c != "factors")

        if has_analysis:
            factors_raw = row.get("factors", "[]")
            factors = json.loads(factors_raw) if isinstance(factors_raw, str) else []
            caveats_raw = row.get("caveats", "[]")
            caveats = json.loads(caveats_raw) if isinstance(caveats_raw, str) else []

            f1, f2, f3 = st.columns(3)
            f1.metric("置信度", f"{float(row.get('confidence', 0)):.0%}")
            f2.metric("时效/长青", row.get("life", "—"))
            f3.metric("分类理由", str(row.get("life_reason", ""))[:30])

            st.markdown("**摘要**")
            st.write(row.get("summary", ""))

            if factors:
                st.markdown("**爆款因素**")
                for f in factors:
                    st.markdown(f"- {f}")

            if caveats:
                st.markdown("**⚠️ 注意事项**")
                for c in caveats:
                    st.markdown(f"- {c}")
        else:
            st.info("暂无 L1 分析 (仅在 T2+ 作品生成)")

else:
    # ── FALLBACK / CREATOR PAGE ──────────────────────────────────
    st.markdown("## 👤 创作者档案")

    creators = safe_query("SELECT * FROM creators WHERE enabled = TRUE")
    if not creators.empty:
        creator_names = creators["name"].tolist()
        selected = st.selectbox("选择创作者", creator_names)

        creator = creators[creators["name"] == selected]
        if not creator.empty:
            c = creator.iloc[0]
            st.markdown(f"### {c['name']}")
            st.write(f"平台: {c['platform']}")
            st.write(f"赛道: {c['niche']}")
            st.write(f"粉丝: {c['followers']:,}")
            st.write(f"备注: {c.get('note', '')}")

            # 该创作者的作品
            works = safe_query(f"""
                SELECT w.*, a.life, a.summary FROM works w
                LEFT JOIN analyses a ON w.work_id = a.work_id
                WHERE w.creator_name = '{selected.replace("'", "''")}'
                ORDER BY w.create_time DESC LIMIT 20
            """)
            if not works.empty:
                st.markdown("#### 🎬 作品")
                for _, w in works.iterrows():
                    grade = w["grade_code"]
                    st.markdown(
                        f"""<div class="boom-card {grade if grade in ('T3','T2','T1') else ''}">
                            <b>{str(w.get('title',''))[:50]}</b>
                            <span style="float:right">
                                <span class="grade-{grade if grade in ('T3','T2','T1') else 'ordinary'}">
                                    {grade} · ❤️{int(w['likes']):,}
                                </span>
                            </span>
                        </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("暂无作品数据")
    else:
        st.info("暂无创作者数据，请先运行采集")

    # ── SETTINGS (簡易版) ─────────────────────────────────────────
    if page == "settings":
        st.markdown("## ⚙️ 设置")
        st.markdown("**环境变量**")
        st.code("TIKHUB_API_KEY=your_key_here  # 切到真实数据")
        st.code("DEEPSEEK_API_KEY=your_key_here  # 启用 L1 分析")
        st.markdown("**对标创作者**")
        st.info(f"当前 {creators.shape[0] if not creators.empty else 0} 个对标 (编辑 creators.py 添加)")
        st.markdown("**定时扫描**")
        st.code("0 0 * * *  # 每天凌晨 Cron 已配置")
        st.markdown("**成本跟踪**")
        st.json({
            "TikHub API": "$15/月",
            "DeepSeek L1": "$15/月 (100条/天)",
            "Claude L2": "$3/月 (5条/天, Mac Mini)",
            "VPS": "$5/月",
            "ASR API": "$2/月",
            "合计": "~$40/月",
        })

# ── 底部 ─────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#888;font-size:0.85rem'>"
    "爆款监控 · pulse-data-engine · R/M/Tier 评分引擎 · L1 DeepSeek · L2 Claude Code"
    f" · DB: {BOOM_DB.name if BOOM_DB.exists() else '不存在'}</p>",
    unsafe_allow_html=True,
)
