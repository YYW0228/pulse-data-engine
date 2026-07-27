"""
scripts/run_production.py — 生产环境管道运行器

目标: 从 `uv run python -m pulse.runner` 进化到生产级部署。

特性:
  - .env 文件加载
  - run_id 版本化 (日期+hash)
  - DLQ 摘要报告
  - Parquet → R2 同步
  - 运行状态 JSON 输出 (供 CI 消费)
  - 健康检查输出
  - Slack 通知 (失败时)

用法:
  # 单次运行 (从项目根目录)
  uv run python -m scripts.run_production

  # 指定 run_id (重跑某天)
  uv run python -m scripts.run_production --run-id pulse_etl_20260727_120000

  # 仅生成报告
  uv run python -m scripts.run_production --report-only

  # 开发模式
  uv run python -m scripts.run_production --dev
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 日志 (JSON 行, CI 友好) ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pulse.prod")


def load_env() -> None:
    """加载 .env 文件 (如果存在)"""
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
        logger.info(f"已加载 {env_file}")


def generate_run_id() -> str:
    """生成版本化 run_id: pulse_etl_20260727_120000_3a1b2c"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    h = hashlib.md5(ts.encode()).hexdigest()[:6]
    return f"pulse_etl_{ts}_{h}"


def dlq_summary(db_path: str = "data/jobs.duckdb") -> dict:
    """DLQ 死信队列摘要"""
    import duckdb

    con = duckdb.connect(db_path)
    try:
        # 表可能存在但为空
        total = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0

        # 按错误类型分组
        by_type = con.execute(
            "SELECT error_type, COUNT(*) as cnt FROM dlq_jobs GROUP BY error_type ORDER BY cnt DESC"
        ).fetchall()

        # 最近 5 条
        recent = con.execute(
            "SELECT url, error_type, error_message, failed_at "
            "FROM dlq_jobs ORDER BY failed_at DESC LIMIT 5"
        ).fetchall()

        return {
            "total": total,
            "by_type": {r[0]: r[1] for r in by_type},
            "recent": [
                {
                    "url": r[0][:80],
                    "error_type": r[1],
                    "error_message": str(r[2])[:100],
                    "failed_at": str(r[3]),
                }
                for r in recent
            ],
        }
    except Exception:
        return {"total": 0, "by_type": {}, "recent": []}
    finally:
        con.close()


def pipeline_report(db_path: str = "data/jobs.duckdb") -> dict:
    """管道运行报告"""
    import duckdb

    con = duckdb.connect(db_path)
    try:
        ods = con.execute("SELECT COUNT(*) FROM ods_raw_jobs").fetchone()[0] or 0
        latest = (
            con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()[0] or 0
        )
        dwd = con.execute("SELECT COUNT(*) FROM dwd_cleaned_jobs").fetchone()[0] or 0
        dlq = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0

        # DWS 聚合
        dws = con.execute(
            "SELECT category, demand_count, avg_salary FROM dws_skill_agg ORDER BY demand_count DESC LIMIT 5"
        ).fetchall()

        parquet_dir = Path("data/ods_parquet")
        parquet_files = list(parquet_dir.rglob("*.parquet")) if parquet_dir.exists() else []
        parquet_size = sum(f.stat().st_size for f in parquet_files)

        return {
            "ods_total": ods,
            "ods_latest": latest,
            "dwd": dwd,
            "dlq": dlq,
            "top_categories": [
                {"category": r[0], "count": r[1], "avg_salary_k": r[2]} for r in dws
            ],
            "parquet_files": len(parquet_files),
            "parquet_size_kb": round(parquet_size / 1024, 1),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()


def sync_parquet_to_r2(
    parquet_dir: str = "data/ods_parquet",
    bucket: str = "pulse-data-engine-parquet",
    force: bool = False,
) -> dict:
    """同步 Parquet 到 R2 (如果凭证可用)"""
    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not account_id or not token:
        return {"status": "skipped", "reason": "CF_ACCOUNT_ID 或 CLOUDFLARE_API_TOKEN 未设置"}

    try:
        from scripts.sync_r2 import sync_parquet

        stats = sync_parquet(account_id, bucket, parquet_dir, force=force)
        return {"status": "ok", "uploaded": stats["uploaded"], "files": stats["files"]}
    except Exception as e:
        logger.error(f"R2 同步失败: {e}")
        return {"status": "failed", "error": str(e)}


def notify_slack(webhook_url: str | None, result: dict) -> None:
    """发送 Slack 通知"""
    if not webhook_url:
        return

    import httpx

    summary = result.get("summary", {})
    success = summary.get("success", 0)
    failed = summary.get("failed", 0)
    run_id = result.get("run_id", "?")

    color = "#36a64f" if failed == 0 else "#ff0000"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Pulse Data Engine* — Run `{run_id[:30]}`"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"✅ {success} 成功 / ❌ {failed} 失败 / ⏭️ {summary.get('skipped', 0)} 跳过",
            },
        },
    ]
    if result.get("report"):
        r = result["report"]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"ODS={r.get('ods_latest', '?')} DWD={r.get('dwd', '?')} DLQ={r.get('dlq', '?')}",
                },
            }
        )

    try:
        httpx.post(
            webhook_url,
            json={
                "attachments": [{"color": color, "blocks": blocks}],
            },
            timeout=10,
        )
        logger.info("Slack 通知发送成功")
    except Exception as e:
        logger.warning(f"Slack 通知失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="Pulse Data Engine — 生产运行")
    parser.add_argument("--run-id", help="指定 run_id (默认自动生成)")
    parser.add_argument("--report-only", action="store_true", help="仅生成报告, 不运行管道")
    parser.add_argument("--dev", action="store_true", help="开发模式: 跳过 R2 同步")
    parser.add_argument("--skip-sync", action="store_true", help="跳过 Parquet → R2 同步")
    parser.add_argument(
        "--with-metrics",
        action="store_true",
        default=True,
        help="启动 /metrics HTTP 端点 (默认开启)",
    )
    args = parser.parse_args()

    t0 = time.time()
    load_env()

    # 启动 /metrics HTTP 端点 (线程)
    metrics_thread = None
    if args.with_metrics:
        try:
            from pulse.metrics_server import run as run_metrics_server

            metrics_thread = threading.Thread(
                target=run_metrics_server,
                kwargs={"port": 9464},
                daemon=True,
            )
            metrics_thread.start()
            logger.info("📊 Metrics 端点已启动: http://localhost:9464/metrics")
        except Exception as e:
            logger.warning(f"Metrics 端点启动失败: {e}")

    # ── 版本化 run_id ─────────────────────────────────────────
    run_id = args.run_id or generate_run_id()
    logger.info(f"运行开始 | run_id={run_id} | dev={args.dev}")

    result: dict = {"run_id": run_id, "status": "running"}

    if args.report_only:
        logger.info("报告模式")
        result["report"] = pipeline_report()
        result["dlq"] = dlq_summary()
        result["status"] = "completed"
        print(json.dumps(result, ensure_ascii=False, default=str))
        return

    # ── 运行管道 ───────────────────────────────────────────────────
    from pulse.runner import run_once

    try:
        dag_result = run_once()
        summary = dag_result.get("summary", {})
        result["summary"] = summary
        result["status"] = "completed" if summary.get("failed", 0) == 0 else "failed"
        logger.info(f"DAG 完成: {summary.get('success', 0)}成功/{summary.get('failed', 0)}失败")
    except Exception as e:
        logger.exception("管道运行崩溃")
        result["status"] = "crashed"
        result["error"] = str(e)

    # ── 生成报告 ─────────────────────────────────────────────────
    result["report"] = pipeline_report()
    result["dlq"] = dlq_summary()
    result["duration_s"] = round(time.time() - t0, 1)

    # ── R2 同步 ────────────────────────────────────────────────
    if not args.dev and not args.skip_sync:
        result["r2_sync"] = sync_parquet_to_r2()

    # ── Slack 通知 ─────────────────────────────────────────────
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook and result.get("status") in ("failed", "crashed"):
        notify_slack(webhook, result)

    # ── JSON 输出 (供 CI 消费) ──────────────────────────────────
    print(json.dumps(result, ensure_ascii=False, default=str))

    # ── Metrics 快照 (供跨进程 Prometheus 采集) ────────────────
    from pulse.metrics import SNAPSHOT_PATH, dump_snapshot
    dump_snapshot()
    # 额外写入 report 数据 (alert_check 消费)
    try:
        import json as _j
        report_snapshot = {
            "timestamp": result.get("report", {}).get("ods_latest", "") or datetime.now(timezone.utc).isoformat(),
            "data_rows": {
                "ods_latest": result.get("report", {}).get("ods_latest", 0),
                "dwd": result.get("report", {}).get("dwd", 0),
                "dlq": result.get("report", {}).get("dlq", 0),
            },
            "dlq": result.get("dlq", {}).get("by_type", {}),
            "dag_tasks": {},
            "summary": result.get("summary", {}),
            "duration_s": result.get("duration_s", 0),
            "status": result.get("status", "unknown"),
        }
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(_j.dumps(report_snapshot, ensure_ascii=False, default=str))
    except OSError:
        pass  # 非关键 — 快照写入失败不影响管道结果

    # ── 退出码 ─────────────────────────────────────────────────
    if result["status"] in ("failed", "crashed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
