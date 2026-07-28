"""
scripts/import_boss_json.py — 导入从浏览器导出的 BOSS 数据到 DuckDB

用法:
  cp ~/Downloads/boss_jobs.json ~/projects/pulse-data-engine/data/
  uv run python scripts/import_boss_json.py
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pulse.pipeline import Pipeline
from pulse.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("import_boss")

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "boss_snapshot.json"
ALT_PATHS = [
    Path(__file__).resolve().parent.parent / "data" / "boss_jobs.json",
]

def main():
    path = DATA_PATH
    if not path.exists():
        for ap in ALT_PATHS:
            if ap.exists():
                path = ap
                break

    if not path.exists():
        logger.error(f"文件不存在: {path}")
        logger.info("请先运行采集: uv run python -c 'from pulse.extractors.boss import BossExtractor; ...'")
        logger.info("或从浏览器导出 boss_jobs.json 放入 data/")
        return

    raw = json.loads(path.read_text(encoding="utf-8"))
    logger.info(f"加载 {len(raw)} 条数据")

    p = Pipeline()
    p.init_schema()

    result = p.validate_and_route(raw)
    logger.info(f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败")

    if result["passed"]:
        stats = p.merge_into_ods(result["passed"])
        logger.info(f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变")

    p.refresh_dwd()
    p.refresh_dws()

    row = p.con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()
    dlq = p.con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()
    logger.info(f"最终: ODS={row[0] if row else 0} DLQ={dlq[0] if dlq else 0}")
    p.close()

    print(f"\n✅ 入库完成! ODS={row[0] if row else 0} 行")
    print("运行下面命令推送到 VPS:")
    print("  push-pulse")

if __name__ == "__main__":
    main()
