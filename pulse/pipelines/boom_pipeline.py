"""
pulse/pipelines/boom_pipeline.py — 爆款监控管道 (独立 DuckDB)

与主数据的 jobs.duckdb 隔离, 避免锁冲突。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import duckdb

logger = logging.getLogger("pulse.pipelines.boom_pipeline")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BOOM_DB = DATA_DIR / "boom.duckdb"


class BoomPipeline:
    """爆款数据管道 — 独立 DB, 自包含 schema"""

    def __init__(self, db_path: str | Path = BOOM_DB):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(db_path))
        self._init_schema()

    def _init_schema(self):
        """初始化表结构"""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                name VARCHAR,
                platform VARCHAR,
                platform_id VARCHAR,
                handle VARCHAR,
                followers INTEGER DEFAULT 0,
                niche VARCHAR,
                note VARCHAR,
                enabled BOOLEAN DEFAULT true,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS works (
                work_id VARCHAR PRIMARY KEY,
                platform VARCHAR,
                creator_id VARCHAR,
                creator_name VARCHAR,
                title VARCHAR,
                create_time INTEGER,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                collects INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                content_type VARCHAR,
                cover_url VARCHAR,
                video_url VARCHAR DEFAULT '',
                grade_code VARCHAR DEFAULT 'ordinary',
                grade_label VARCHAR DEFAULT '普通',
                r_value REAL DEFAULT 0.0,
                m_value REAL DEFAULT 0.0,
                m_base REAL DEFAULT 0.0,
                tier VARCHAR DEFAULT '',
                creator_followers_at_grade INTEGER DEFAULT 0,
                baseline_at_grade REAL DEFAULT 0.0,
                graded_at INTEGER DEFAULT 0
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                work_id VARCHAR PRIMARY KEY,
                tier VARCHAR DEFAULT 'L1',
                summary VARCHAR DEFAULT '',
                factors VARCHAR DEFAULT '[]',
                factor_evidence VARCHAR DEFAULT '[]',
                confidence REAL DEFAULT 0.0,
                caveats VARCHAR DEFAULT '[]',
                life VARCHAR DEFAULT '长青',
                life_reason VARCHAR DEFAULT '',
                raw_result VARCHAR DEFAULT '{}',
                created_at INTEGER DEFAULT 0
            )
        """)
        self.con.execute("DROP TABLE IF EXISTS scan_log")
        self.con.execute("""
            CREATE TABLE scan_log (
                scan_time INTEGER,
                platform VARCHAR,
                creators_scanned INTEGER,
                works_collected INTEGER,
                booms_detected INTEGER,
                status VARCHAR DEFAULT 'done',
                error VARCHAR DEFAULT ''
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
        """)
        # 迁移: 旧库加 factor_evidence 列 (CREATE IF NOT EXISTS 不会加列)
        try:
            self.con.execute(
                "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS factor_evidence VARCHAR DEFAULT '[]'"
            )
        except Exception as e:
            logger.warning(f"[BoomPipeline] factor_evidence 列迁移失败(可忽略): {e}")
        # DuckDB 默认 WAL (不需要显式设置)
        logger.info("[BoomPipeline] Schema 就绪")

    def save_creator(self, creator: dict) -> None:
        self.con.execute(
            """
            INSERT INTO creators (name, platform, platform_id, handle, followers,
                                  niche, note, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """,
            [
                creator["name"],
                creator["platform"],
                creator.get("platform_id", ""),
                creator.get("handle", ""),
                creator.get("followers", 0),
                creator.get("niche", ""),
                creator.get("note", ""),
                creator.get("enabled", True),
                int(time.time()),
                int(time.time()),
            ],
        )

    def save_work(self, work: dict) -> None:
        self.con.execute(
            """
            INSERT INTO works (work_id, platform, creator_id, creator_name,
                               title, create_time, likes, comments, collects, shares,
                               content_type, cover_url, video_url,
                               grade_code, grade_label, r_value, m_value, m_base,
                               tier, creator_followers_at_grade, baseline_at_grade, graded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_id) DO UPDATE SET
                likes = EXCLUDED.likes,
                comments = EXCLUDED.comments,
                collects = EXCLUDED.collects,
                shares = EXCLUDED.shares,
                grade_code = EXCLUDED.grade_code,
                grade_label = EXCLUDED.grade_label
        """,
            [
                work["work_id"],
                work.get("platform", ""),
                work.get("creator_id", ""),
                work.get("creator_name", ""),
                work.get("title", ""),
                work.get("create_time", 0),
                work.get("likes", 0),
                work.get("comments", 0),
                work.get("collects", 0),
                work.get("shares", 0),
                work.get("content_type", ""),
                work.get("cover_url", ""),
                work.get("video_url", ""),
                work.get("grade_code", "ordinary"),
                work.get("grade_label", "普通"),
                work.get("r_value", 0.0),
                work.get("m_value", 0.0),
                work.get("m_base", 0.0),
                work.get("tier", ""),
                work.get("creator_followers_at_grade", 0),
                work.get("baseline_at_grade", 0.0),
                work.get("graded_at", 0),
            ],
        )

    def save_analysis(self, analysis: dict) -> None:
        self.con.execute(
            """
            INSERT INTO analyses (work_id, tier, summary, factors, factor_evidence, confidence,
                                  caveats, life, life_reason, raw_result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_id) DO UPDATE SET
                tier = EXCLUDED.tier,
                summary = EXCLUDED.summary,
                factors = EXCLUDED.factors,
                factor_evidence = EXCLUDED.factor_evidence,
                confidence = EXCLUDED.confidence,
                caveats = EXCLUDED.caveats,
                life = EXCLUDED.life,
                life_reason = EXCLUDED.life_reason,
                raw_result = EXCLUDED.raw_result
        """,
            [
                analysis["work_id"],
                analysis.get("tier", "L1"),
                analysis.get("summary", ""),
                json.dumps(analysis.get("factors", []), ensure_ascii=False),
                json.dumps(analysis.get("factor_evidence", []), ensure_ascii=False),
                analysis.get("confidence", 0.0),
                json.dumps(analysis.get("caveats", []), ensure_ascii=False),
                analysis.get("life", "长青"),
                analysis.get("life_reason", ""),
                json.dumps(analysis.get("raw_result", {}), ensure_ascii=False),
                int(time.time()),
            ],
        )

    def log_scan(
        self, platform: str, scanned: int, collected: int, booms: int, error: str = ""
    ) -> int:
        self.con.execute(
            """
            INSERT INTO scan_log (scan_time, platform, creators_scanned, works_collected,
                                  booms_detected, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [
                int(time.time()),
                platform,
                scanned,
                collected,
                booms,
                "error" if error else "done",
                error,
            ],
        )
        return int(self.con.execute("SELECT COUNT(*) FROM scan_log").fetchone()[0])

    def get_recent_booms(self, limit: int = 20) -> list[dict]:
        rows = self.con.execute(
            """
            SELECT w.*, a.summary, a.factors, a.life, a.life_reason, a.confidence
            FROM works w
            LEFT JOIN analyses a ON w.work_id = a.work_id
            WHERE w.grade_code IN ('T3', 'T2')
            ORDER BY w.graded_at DESC
            LIMIT ?
        """,
            [limit],
        ).fetchdf()
        return rows.to_dict("records") if not rows.empty else []

    def get_stats(self) -> dict:
        return (
            self.con.execute("""
            SELECT
                (SELECT COUNT(*) FROM works) AS total_works,
                (SELECT COUNT(*) FROM works WHERE grade_code = 'T3') AS t3_count,
                (SELECT COUNT(*) FROM works WHERE grade_code = 'T2') AS t2_count,
                (SELECT COUNT(*) FROM works WHERE grade_code = 'T1') AS t1_count,
                (SELECT COUNT(*) FROM analyses) AS analyzed,
                (SELECT COUNT(*) FROM scan_log) AS scan_runs,
                (SELECT COUNT(*) FROM creators) AS creators
        """)
            .fetchdf()
            .iloc[0]
            .to_dict()
            if False
            else self.con.execute("SELECT 'stats' AS _dummy").fetchdf().to_dict()
        )

    def close(self):
        self.con.close()
