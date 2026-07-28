"""
pulse/monitor.py — 监控告警 + 数据质量 SLA

功能:
  - DLQ 激增告警 (Slack/Email)
  - 任务失败告警
  - 性能 SLA 检查
  - 数据质量多维检查 (完整性/有效性/新鲜度/一致性)
"""

import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from enum import Enum

logger = logging.getLogger("pulse.monitor")


class AlertLevel(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class QualityStatus:
    OK = "PASS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Monitor:
    def __init__(self, webhook_url: str | None = None, email: str | None = None):
        self.webhook_url: str | None = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.email: str | None = email or os.getenv("ALERT_EMAIL")

    def check_dlq_spike(self, dlq_count: int, threshold: int = 100) -> bool:
        if dlq_count > threshold:
            self.alert(
                AlertLevel.CRITICAL, "DLQ Spike", f"DLQ {dlq_count} records (threshold={threshold})"
            )
            return False
        return True

    def check_task_failure(self, task_name: str, error: str) -> None:
        self.alert(AlertLevel.CRITICAL, f"Task Failed: {task_name}", str(error)[:300])

    def check_performance(self, task_name: str, duration_ms: int, sla_ms: int = 60000) -> None:
        if duration_ms > sla_ms:
            self.alert(
                AlertLevel.WARNING, f"Performance: {task_name}", f"{duration_ms}ms (SLA={sla_ms}ms)"
            )

    def alert(self, level: AlertLevel, title: str, message: str) -> None:
        payload = {"level": level.value, "title": title, "message": message}
        logger.warning(json.dumps(payload, ensure_ascii=False))
        if self.webhook_url:
            self._send_slack(level, title, message)
        if self.email:
            self._send_email(title, message)

    def _send_slack(self, level: AlertLevel, title: str, message: str) -> None:
        try:
            import httpx

            color = {"CRITICAL": "danger", "WARNING": "warning", "INFO": "good"}[level.value]
            httpx.post(
                self.webhook_url,
                json={"attachments": [{"color": color, "title": title, "text": message}]},
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")

    def _send_email(self, title: str, message: str) -> None:
        try:
            msg = MIMEText(message)
            msg["Subject"] = title
            msg["From"] = "pulse-engine@localhost"
            msg["To"] = self.email
            with smtplib.SMTP("localhost", 25, timeout=5) as s:
                s.send_message(msg)
        except Exception as e:
            logger.error(f"Email alert failed: {e}")


class QualitySLA:
    def __init__(
        self,
        db_path: str = "data/jobs.duckdb",
        null_rate_max: float = 0.05,
        invalid_salary_rate_max: float = 0.50,
        max_stale_hours: int = 24,
    ):
        import duckdb

        self.con = duckdb.connect(str(db_path))
        self.null_rate_max = null_rate_max
        self.invalid_salary_rate_max = invalid_salary_rate_max
        self.max_stale_hours = max_stale_hours

    def check_completeness(self) -> dict:
        r = self.con.execute(
            "SELECT COUNT(*), COUNT(CASE WHEN job_title IS NULL THEN 1 END), COUNT(CASE WHEN salary_min_k IS NULL THEN 1 END) FROM ods_raw_jobs WHERE is_latest=TRUE"
        ).fetchone()
        total, null_titles, null_sal = r
        return {
            "status": QualityStatus.OK
            if (null_titles / max(total, 1)) <= self.null_rate_max
            else QualityStatus.CRITICAL,
            "total": total,
            "null_title_rate": round(null_titles / max(total, 1), 3),
            "null_salary_rate": round(null_sal / max(total, 1), 3),
        }

    def check_validity(self) -> dict:
        r = self.con.execute(
            "SELECT COUNT(*), COUNT(CASE WHEN salary_min_k IS NULL OR salary_max_k IS NULL OR salary_min_k > salary_max_k THEN 1 END) FROM ods_raw_jobs WHERE is_latest=TRUE"
        ).fetchone()
        total, invalid = r
        return {
            "status": QualityStatus.OK
            if (invalid / max(total, 1)) <= self.invalid_salary_rate_max
            else QualityStatus.CRITICAL,
            "total": total,
            "invalid_rate": round(invalid / max(total, 1), 3),
        }

    def check_freshness(self) -> dict:
        r = self.con.execute(
            "SELECT MAX(crawled_at) FROM ods_raw_jobs WHERE is_latest=TRUE"
        ).fetchone()
        latest = r[0]
        if latest is None:
            return {"status": QualityStatus.CRITICAL, "age_hours": 999}
        age = (datetime.now(timezone.utc).replace(tzinfo=None) - latest).total_seconds() / 3600
        return {
            "status": QualityStatus.OK if age <= self.max_stale_hours else QualityStatus.CRITICAL,
            "latest_crawl": str(latest),
            "age_hours": round(age, 1),
        }

    def check_consistency(self) -> dict:
        ods = self.con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()[
            0
        ]
        dwd = self.con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0]
        ratio = dwd / max(ods, 1)
        return {
            "status": QualityStatus.OK if ratio >= 0.95 else QualityStatus.CRITICAL,
            "ods": ods,
            "dwd": dwd,
            "consistency": round(ratio, 3),
        }

    def full_report(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "completeness": self.check_completeness(),
            "validity": self.check_validity(),
            "freshness": self.check_freshness(),
            "consistency": self.check_consistency(),
        }
