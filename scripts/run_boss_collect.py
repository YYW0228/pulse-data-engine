"""
scripts/run_boss_collect.py — BOSS 直聘 采集 → 校验 → DuckDB

用法:
  uv run python scripts/run_boss_collect.py

前置条件:
  1. uv sync (已完成)
  2. data/boss_storage_state.json (首次需运行 boss_cookies_setup.py)
"""
import logging
import sys
from pathlib import Path

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pulse.logging_config import setup_logging
from pulse.pipeline import Pipeline

setup_logging()
logger = logging.getLogger("boss_collect")

def main():
    # 1. 采集
    logger.info("=" * 50)
    logger.info("BOSS直聘 采集开始")
    logger.info("=" * 50)

    try:
        from pulse.extractors.boss import BossExtractor
        extractor = BossExtractor()
        # 默认: 关键词 AI/人工智能/大模型/算法, 5 个一线城市, 每页 2 页
        raw = extractor.fetch_jobs(max_pages=2)
    except FileNotFoundError as e:
        logger.error(str(e))
        return
    except Exception as e:
        logger.error(f"采集失败: {e}")
        return

    if not raw:
        logger.warning("未采集到数据")
        return

    logger.info(f"采集到 {len(raw)} 条原始数据")

    # 2. 校验 + 入库
    p = Pipeline()
    p.init_schema()

    result = p.validate_and_route(raw)
    logger.info(
        f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败"
    )

    if result["passed"]:
        stats = p.merge_into_ods(result["passed"])
        logger.info(f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变")

    # 3. 刷新 DWD/DWS
    dwd_count = p.refresh_dwd()
    logger.info(f"DWD: {dwd_count} 行")
    p.refresh_dws()
    logger.info("DWS: 聚合完成")

    # 4. 统计
    ods_row = p.con.execute(
        "SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE"
    ).fetchone()
    ods_count = ods_row[0] if ods_row else 0
    dlq_row = p.con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()
    dlq_count = dlq_row[0] if dlq_row else 0
    logger.info(f"最终状态: ODS={ods_count} DLQ={dlq_count}")
    p.close()

    print(f"\n✅ 完成: ODS={ods_count} DLQ={dlq_count}")

if __name__ == "__main__":
    main()
