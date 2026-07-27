"""
scripts/alert_check.py — 基于 snapshot 的简单告警扫描

无需 Prometheus Alertmanager。读取 data/metrics/snapshot.json，
检查预定义阈值，发现异常输出 JSON 告警。

用法:
  uv run python -m scripts.alert_check
  uv run python -m scripts.alert_check --threshold-dlq-spike 50
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("pulse.alert")


def check_alerts(
    snapshot_path: str = "data/metrics/snapshot.json",
    dlq_spike_threshold: int = 50,
    p95_duration_threshold: float = 15.0,
    min_success_rate: float = 0.8,
) -> list[dict]:
    """检查 snapshot 并返回告警列表"""
    path = Path(snapshot_path)
    if not path.exists():
        return [
            {
                "level": "WARNING",
                "rule": "no_data",
                "message": "metrics snapshot 不存在, 管道尚未运行",
            }
        ]

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return [{"level": "CRITICAL", "rule": "read_error", "message": f"snapshot 读取失败: {e}"}]

    alerts = []
    dlq = data.get("dlq", {})
    dag_tasks = data.get("dag_tasks", {})
    data_rows = data.get("data_rows", {})

    # ── DLQ 突增 ────────────────────────────────────────────────
    total_dlq = sum(dlq.values()) if dlq else data_rows.get("dlq", 0)
    if total_dlq > dlq_spike_threshold:
        alerts.append(
            {
                "level": "WARNING",
                "rule": "dlq_spike",
                "message": f"DLQ {total_dlq} 条 (阈值={dlq_spike_threshold})",
                "value": total_dlq,
            }
        )

    # ── Task 成功率 ──────────────────────────────────────────────
    for key, val in dag_tasks.items():
        # key: "pulse_dag_task_total.test_task.success"
        # key: "pulse_dag_task_total.test_task.failed"
        if "pulse_dag_task_total" in key and "failed" in key:
            task_name = key.split(".")[1] if len(key.split(".")) > 1 else "?"
            failed_count = val
            success_key = f"pulse_dag_task_total.{task_name}.success"
            success_count = dag_tasks.get(success_key, 0)
            total = success_count + failed_count
            if total > 0 and success_count / total < min_success_rate:
                alerts.append(
                    {
                        "level": "CRITICAL",
                        "rule": "low_success_rate",
                        "message": f"{task_name} 成功率 {success_count}/{total} ({success_count / total * 100:.0f}%)",
                        "value": success_count / total,
                    }
                )

    return alerts


def main():
    parser = argparse.ArgumentParser(description="Pulse Alert Check")
    parser.add_argument("--snapshot", default="data/metrics/snapshot.json")
    parser.add_argument("--dlq-spike", type=int, default=50)
    parser.add_argument("--p95-duration", type=float, default=15.0)
    parser.add_argument("--min-success-rate", type=float, default=0.8)
    parser.add_argument("--slack-webhook", default=os.getenv("SLACK_WEBHOOK_URL", ""))
    args = parser.parse_args()

    alerts = check_alerts(
        snapshot_path=args.snapshot,
        dlq_spike_threshold=args.dlq_spike,
        p95_duration_threshold=args.p95_duration,
        min_success_rate=args.min_success_rate,
    )

    if not alerts:
        logger.info("✅ 无告警")
        print(json.dumps({"status": "ok", "alerts": []}))
        return

    for a in alerts:
        print(f"  [{a['level']}] {a['rule']}: {a['message']}")

    output = {"status": "alerts", "alerts": alerts}
    print(json.dumps(output, ensure_ascii=False))

    # Slack 通知 (CRITICAL 级别)
    critical = [a for a in alerts if a["level"] == "CRITICAL"]
    if critical and args.slack_webhook:
        import httpx

        text = "\n".join(f"*{a['rule']}*: {a['message']}" for a in critical)
        try:
            httpx.post(
                args.slack_webhook,
                json={
                    "attachments": [
                        {
                            "color": "#ff0000",
                            "title": "🔴 Pulse Alert",
                            "text": text,
                        }
                    ]
                },
                timeout=10,
            )
            logger.info("Slack CRITICAL 告警发送成功")
        except Exception as e:
            logger.warning(f"Slack 告警失败: {e}")

    sys.exit(1 if critical else 0)


if __name__ == "__main__":
    main()
