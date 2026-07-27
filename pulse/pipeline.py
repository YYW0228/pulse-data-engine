"""
pulse/pipeline.py — 三层数仓管道 v4 (Data Contracts + DLQ + Parquet)

架构:
  Input → validate_and_route() → [pass] → merge_into_ods (SCD Type 2)
                                  [fail] → write_dlq(SCHEMA_VIOLATION)
"""

import hashlib
import logging
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import duckdb

logger = logging.getLogger("pulse.pipeline")


def build_safe_pattern(kw: str) -> str:
    safe = re.escape(kw)
    if re.match(r"^[a-zA-Z0-9_+#.@-]+$", kw):
        return rf"(?<![a-zA-Z0-9_]){safe}(?![a-zA-Z0-9_])"
    return safe


from typing import ClassVar


class Pipeline:
    CATEGORIES: ClassVar[list[tuple[str, list[str]]]] = [
        (
            "AI/ML算法",
            [
                "ai",
                "ml",
                "llm",
                "大模型",
                "深度学习",
                "自然语言",
                "计算机视觉",
                "推荐算法",
                "搜索算法",
                "算法研究",
                "算法工程",
                "机器学习",
                "nlp",
                "cv",
                "模型训练",
                "人工智能",
                "算法",
                "模型",
                "推荐系统",
            ],
        ),
        (
            "AI应用/Agent",
            [
                "agent",
                "rag",
                "提示词",
                "prompt",
                "ai应用",
                "ai产品",
                "智能体",
                "自动化",
                "ai训练师",
                "ai算法",
                "智能",
            ],
        ),
        (
            "治理/合规",
            [
                "治理",
                "合规",
                "安全",
                "隐私",
                "审计",
                "伦理",
                "风控",
                "对齐",
                "法律",
                "法务",
            ],
        ),
        (
            "数据工程",
            [
                "数据工程",
                "数据开发",
                "数据仓库",
                "etl",
                "bi",
                "数仓",
                "大数据",
                "spark",
                "flink",
                "数据标注",
            ],
        ),
        (
            "后端/架构",
            [
                "golang",
                "python",
                "java",
                "rust",
                "c++",
                "c#",
                "后端",
                "微服务",
                "中间件",
                "架构师",
                "cto",
                "技术总监",
                "后端开发",
                "node.js",
                "node",
            ],
        ),
        (
            "产品/管理",
            [
                "产品经理",
                "pm",
                "产品总监",
                "产品负责",
                "产品专家",
                "团队管理",
                "项目总监",
                "产品设计",
                "vp",
            ],
        ),
        (
            "运维/基础设施",
            [
                "devops",
                "sre",
                "k8s",
                "docker",
                "云原生",
                "运维",
                "基础设施",
                "cicd",
                "kubernetes",
                "部署",
            ],
        ),
        (
            "AI基础设施",
            [
                "模型部署",
                "推理优化",
                "模型压缩",
                "分布式训练",
                "gpu",
                "算力",
                "训练框架",
                "推理加速",
            ],
        ),
    ]

    _COMPILED: ClassVar[list[tuple[str, list[re.Pattern]]]] = []
    for name, kws in CATEGORIES:
        patterns = []
        for kw in kws:
            try:
                patterns.append(re.compile(build_safe_pattern(kw), re.IGNORECASE))
            except re.error:
                warnings.warn(f"Regex failed for '{kw}' in {name}")
        _COMPILED.append((name, patterns))

    @classmethod
    def classify(cls, title: str) -> str:
        t = title or ""
        for name, patterns in cls._COMPILED:
            for pat in patterns:
                if pat.search(t):
                    return name
        return "其他"

    @staticmethod
    def content_hash(title: str, sal_min: int | None, sal_max: int | None, city: str) -> str:
        raw = f"{title}|{sal_min}|{sal_max}|{city}"
        return hashlib.md5(raw.encode()).hexdigest()

    def __init__(
        self,
        db_path: str | Path = "data/jobs.duckdb",
        parquet_path: str | Path = "data/ods_parquet",
        iceberg_path: str | Path = "data/ods_iceberg",
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_path = str(Path(parquet_path))
        Path(parquet_path).mkdir(parents=True, exist_ok=True)
        self.iceberg_path = str(Path(iceberg_path))
        Path(iceberg_path).mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.db_path))

    def init_schema(self) -> None:
        con = self.con
        con.execute("CREATE SEQUENCE IF NOT EXISTS seq_row_id START 1")

        con.execute("""
            CREATE TABLE IF NOT EXISTS ods_raw_jobs (
                row_id BIGINT PRIMARY KEY, entity_id VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL, is_latest BOOLEAN DEFAULT TRUE,
                valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP, valid_to TIMESTAMP,
                job_title VARCHAR, company_name VARCHAR, city VARCHAR,
                salary_min_k INTEGER, salary_max_k INTEGER,
                education VARCHAR, experience VARCHAR,
                url VARCHAR, keyword VARCHAR, source VARCHAR, domain VARCHAR,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_entity ON ods_raw_jobs(entity_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_latest ON ods_raw_jobs(is_latest)")

        con.execute("""
            CREATE TABLE IF NOT EXISTS dlq_jobs (
                row_id BIGINT PRIMARY KEY, url VARCHAR,
                error_type VARCHAR, error_message VARCHAR,
                http_status INTEGER, raw_payload VARCHAR,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retry_count INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS dwd_cleaned_jobs (
                entity_id VARCHAR PRIMARY KEY, title VARCHAR,
                company VARCHAR, city VARCHAR, salary_min INTEGER,
                salary_max INTEGER, salary_mid DOUBLE, category VARCHAR,
                crawled_at TIMESTAMP, valid_from TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS dws_skill_agg (
                category VARCHAR PRIMARY KEY, demand_count BIGINT,
                avg_salary DOUBLE, p50 DOUBLE, p25 DOUBLE, p75 DOUBLE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS dws_city_agg (
                city VARCHAR PRIMARY KEY, job_count BIGINT, avg_salary DOUBLE
            )
        """)

    def write_dlq(
        self,
        url: str,
        error_type: str,
        error_message: str,
        http_status: int | None = None,
        raw_payload: str = "",
    ) -> None:
        row_id = abs(hash(url + error_type + str(datetime.now(timezone.utc)))) % (2**63)
        self.con.execute(
            """
            INSERT OR IGNORE INTO dlq_jobs
                (row_id, url, error_type, error_message, http_status, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            [
                row_id,
                url,
                error_type,
                error_message[:1000],
                http_status,
                raw_payload[:5000],
            ],
        )

    def validate_and_route(self, raw_records: list[dict]) -> dict:
        from pulse.schema import RawJobContract

        passed = []
        violations = []
        for record in raw_records:
            try:
                contract = RawJobContract(**record)
                passed.append(contract.model_dump())
            except Exception as e:
                url = record.get("url", "unknown")
                violations.append({"url": url, "error": str(e), "raw_record": record})
                self.write_dlq(
                    url,
                    "SCHEMA_VIOLATION",
                    str(e)[:500],
                    raw_payload=str(record)[:3000],
                )
        return {
            "passed": passed,
            "violations": violations,
            "summary": {
                "total": len(raw_records),
                "passed": len(passed),
                "failed": len(violations),
            },
        }

    def merge_into_ods(self, jobs: list[dict]) -> dict:
        con = self.con
        stats = {"new": 0, "updated": 0, "unchanged": 0}
        for job in jobs:
            url = job.get("url", "")
            entity_id = hashlib.md5(url.encode()).hexdigest()
            new_hash = self.content_hash(
                str(job.get("job_title", "")),
                job.get("salary_min_k"),
                job.get("salary_max_k"),
                str(job.get("city", "")),
            )
            existing = con.execute(
                "SELECT content_hash FROM ods_raw_jobs WHERE entity_id=? AND is_latest=TRUE",
                [entity_id],
            ).fetchone()
            if existing is None:
                row_id = con.execute("SELECT nextval('seq_row_id')").fetchone()[0]
                con.execute(
                    "INSERT INTO ods_raw_jobs (row_id, entity_id, content_hash, is_latest, job_title, company_name, city, salary_min_k, salary_max_k, education, experience, url, keyword, source, domain, crawled_at) VALUES (?,?,?,TRUE,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                    [
                        row_id,
                        entity_id,
                        new_hash,
                        job.get("job_title"),
                        job.get("company_name"),
                        job.get("city"),
                        job.get("salary_min_k"),
                        job.get("salary_max_k"),
                        job.get("education"),
                        job.get("experience"),
                        url,
                        job.get("keyword"),
                        job.get("source"),
                        job.get("domain"),
                    ],
                )
                stats["new"] += 1
            elif existing[0] == new_hash:
                con.execute(
                    "UPDATE ods_raw_jobs SET crawled_at=CURRENT_TIMESTAMP WHERE entity_id=? AND is_latest=TRUE",
                    [entity_id],
                )
                stats["unchanged"] += 1
            else:
                con.execute(
                    "UPDATE ods_raw_jobs SET is_latest=FALSE, valid_to=CURRENT_TIMESTAMP WHERE entity_id=? AND is_latest=TRUE",
                    [entity_id],
                )
                row_id = con.execute("SELECT nextval('seq_row_id')").fetchone()[0]
                con.execute(
                    "INSERT INTO ods_raw_jobs (row_id, entity_id, content_hash, is_latest, valid_from, job_title, company_name, city, salary_min_k, salary_max_k, education, experience, url, keyword, source, domain, crawled_at) VALUES (?,?,?,TRUE,CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                    [
                        row_id,
                        entity_id,
                        new_hash,
                        job.get("job_title"),
                        job.get("company_name"),
                        job.get("city"),
                        job.get("salary_min_k"),
                        job.get("salary_max_k"),
                        job.get("education"),
                        job.get("experience"),
                        url,
                        job.get("keyword"),
                        job.get("source"),
                        job.get("domain"),
                    ],
                )
                stats["updated"] += 1
        return stats

    def refresh_dwd(self) -> int:
        con = self.con
        con.execute("DELETE FROM dwd_cleaned_jobs")
        rows = con.execute(
            "SELECT entity_id,job_title,company_name,city,salary_min_k,salary_max_k,crawled_at,valid_from FROM ods_raw_jobs WHERE is_latest=TRUE"
        ).fetchall()
        for r in rows:
            eid, title, co, city, smin, smax, crawled, vf = r
            sal_min = smin if smin and 0 < smin < 500 else None
            sal_max = smax if smax and 0 < smax < 500 else None
            sal_mid = (sal_min + sal_max) / 2.0 if sal_min and sal_max else None
            cat = self.classify(str(title or ""))
            con.execute(
                "INSERT INTO dwd_cleaned_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    eid,
                    str(title or "").strip(),
                    str(co or "").strip(),
                    str(city or "").strip(),
                    sal_min,
                    sal_max,
                    sal_mid,
                    cat,
                    crawled,
                    vf,
                ],
            )
        return len(rows)

    def refresh_dws(self) -> None:
        con = self.con
        con.execute("DELETE FROM dws_skill_agg")
        con.execute(
            """INSERT INTO dws_skill_agg SELECT category,COUNT(*),ROUND(AVG(salary_mid)),ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_mid)),ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary_mid)),ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary_mid)),CURRENT_TIMESTAMP FROM dwd_cleaned_jobs WHERE category!='其他' AND salary_mid IS NOT NULL GROUP BY category"""
        )
        con.execute("DELETE FROM dws_city_agg")
        con.execute(
            """INSERT INTO dws_city_agg SELECT city,COUNT(*),ROUND(AVG(salary_mid)) FROM dwd_cleaned_jobs WHERE city NOT IN ('','SEM','抛光工') AND salary_mid IS NOT NULL GROUP BY city"""
        )

    def export_to_parquet(self) -> dict:
        con = self.con
        con.execute(
            f"COPY (SELECT *, EXTRACT(YEAR FROM crawled_at) AS year, EXTRACT(MONTH FROM crawled_at) AS month, CAST(crawled_at AS DATE) AS date FROM ods_raw_jobs WHERE is_latest=TRUE) TO '{self.parquet_path}' (FORMAT PARQUET, PARTITION_BY (year, month, date), OVERWRITE_OR_IGNORE 1)"
        )
        files = list(Path(self.parquet_path).rglob("*.parquet"))
        return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}

    # ── Iceberg 冷存储 (time travel) ────────────────────────────────

    def export_to_iceberg(self) -> dict:
        """将 ODS 最新数据导出为 Iceberg 格式, 支持 time travel"""
        con = self.con
        con.execute("LOAD iceberg")

        # 写完整 ODS 表 (含历史版本, 非仅 is_latest)
        # Iceberg 自动创建快照, time travel 可回溯任意版本
        con.execute(
            f"COPY (SELECT * FROM ods_raw_jobs) TO '{self.iceberg_path}' "
            f"(FORMAT ICEBERG, OVERWRITE_OR_IGNORE 1)"
        )

        # 统计
        data_files = list((Path(self.iceberg_path) / "data").rglob("*.parquet"))
        size = sum(f.stat().st_size for f in data_files) if data_files else 0
        meta_files = list((Path(self.iceberg_path) / "metadata").rglob("*"))
        meta_size = sum(f.stat().st_size for f in meta_files) if meta_files else 0

        # 读取快照信息
        snapshots = con.execute(
            f"SELECT snapshot_id, timestamp_ms, manifest_list "
            f"FROM iceberg_snapshots('{self.iceberg_path}')"
        ).fetchall()

        return {
            "data_files": len(data_files),
            "data_bytes": size,
            "meta_bytes": meta_size,
            "total_bytes": size + meta_size,
            "snapshots": [
                {"id": str(s[0]), "ts": str(s[1])[:19], "rows": "*"}
                for s in snapshots
            ],
        }

    def list_iceberg_snapshots(self) -> list[dict]:
        """列出所有 Iceberg 快照 (time travel 时间点)"""
        path = Path(self.iceberg_path)
        if not path.exists() or not any(path.iterdir()):
            return []
        con = self.con
        con.execute("LOAD iceberg")
        try:
            snaps = con.execute(
                f"SELECT snapshot_id, timestamp_ms "
                f"FROM iceberg_snapshots('{self.iceberg_path}') "
                f"ORDER BY timestamp_ms DESC"
            ).fetchall()
            return [
                {"id": str(s[0]), "timestamp": str(s[1])[:19], "rows": "*"}
                for s in snaps
            ]
        except Exception:
            return []

    def iceberg_query_at(self, snapshot_id: str, sql: str = "SELECT * FROM ods_raw_jobs LIMIT 10") -> list:
        """对指定 Iceberg 快照执行 SQL 查询 (time travel)"""
        con = self.con
        con.execute("LOAD iceberg")
        # 创建视图指向特定快照
        con.execute(
            f"CREATE OR REPLACE VIEW ods_raw_at AS "
            f"SELECT * FROM iceberg_scan('{self.iceberg_path}', snapshot_from_id={snapshot_id})"
        )
        return con.execute(sql).fetchall()

    def verify(self) -> dict:
        from pulse.metrics import metrics

        con = self.con
        ods = con.execute("SELECT COUNT(*) FROM ods_raw_jobs").fetchone()[0] or 0
        # 更新指标
        latest = (
            con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()[0] or 0
        )
        dwd = con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0] or 0
        dlq = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0
        metrics.ods_rows.labels(version="total").set(ods)
        metrics.ods_rows.labels(version="latest").set(latest)
        metrics.dwd_rows.set(dwd)
        metrics.dlq_rows.set(dlq)
        latest = (
            con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()[0] or 0
        )
        dwd = con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0] or 0
        dws_n = (
            con.execute("SELECT COALESCE(SUM(demand_count),0) FROM dws_skill_agg").fetchone()[0]
            or 0
        )
        excluded = (
            con.execute(
                "SELECT COUNT(*) FROM dwd_cleaned_jobs WHERE category='其他' OR salary_mid IS NULL"
            ).fetchone()[0]
            or 0
        )
        dlq_n = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0
        return {
            "ods_total": ods,
            "ods_latest": latest,
            "dwd": dwd,
            "dws": dws_n,
            "excluded": excluded,
            "dws_plus_excluded": dws_n + excluded,
            "dlq": dlq_n,
            "consistent": (dws_n + excluded) == dwd == latest and dwd > 0,
        }

    def run_full(self) -> dict:
        self.init_schema()
        return self.verify()

    def close(self) -> None:
        self.con.close()

    # ── DLQ 重处理 ──────────────────────────────────────────────────

    def reprocess_dlq(self, dry_run: bool = False) -> dict:
        """尝试修复并重处理 DLQ 中的死信记录

        修复规则:
          1. city 过长 → 截断至 200 字符
          2. salary min>max → 自动交换 (已由 Data Contract 处理)
          3. salary > 1000 → 按 元/月 归一化 (÷1000)
          4. raw_payload 是 Python dict 语法 (非 JSON) → 用 ast.literal_eval

        返回:
            {"recovered": N, "still_failed": N, "total": N}
        """
        import ast

        from pulse.schema import RawJobContract

        con = self.con
        rows = con.execute(
            "SELECT row_id, url, error_type, error_message, raw_payload "
            "FROM dlq_jobs WHERE retry_count < 1"
        ).fetchall()

        recovered = 0
        still_failed = 0
        for row_id, url, error_type, error_msg, raw_payload in rows:
            # 从 raw_payload 恢复原始记录
            record = {}
            if raw_payload and raw_payload.startswith("{"):
                try:
                    record = ast.literal_eval(raw_payload)
                except (ValueError, SyntaxError):
                    still_failed += 1
                    continue

            if not record:
                still_failed += 1
                continue

            # 尝试修复: city 截断
            if isinstance(record.get("city"), str) and len(record["city"]) > 200:
                record["city"] = record["city"][:197] + "..."

            # 重新校验
            try:
                contract = RawJobContract(**record)
                validated = contract.model_dump()
                if dry_run:
                    recovered += 1
                else:
                    # 合并到 ODS
                    self.merge_into_ods([validated])
                    # 从 DLQ 标记已处理
                    con.execute(
                        "DELETE FROM dlq_jobs WHERE row_id=?",
                        [row_id],
                    )
                    recovered += 1
            except Exception as e:
                # 无法修复 — 标记永久
                con.execute(
                    "UPDATE dlq_jobs SET retry_count=1, error_message=? WHERE row_id=?",
                    [f"PERMANENT: {str(e)[:200]}", row_id],
                )
                still_failed += 1

        total = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0
        return {"recovered": recovered, "still_failed": still_failed, "total_remaining": total}
