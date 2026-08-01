"""
scripts/run_boom_collect.py — 爆款监控每日扫描

用法:
  uv run python scripts/run_boom_collect.py              # 全平台扫描
  uv run python scripts/run_boom_collect.py --platform douyin  # 单平台
  uv run python scripts/run_boom_collect.py --mock-only   # 仅模拟数据 (无 API key)

调度建议 (crontab):
  20 0 * * * cd /root/projects/pulse-data-engine && uv run python scripts/run_boom_collect.py
"""

from __future__ import annotations

import argparse
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_boom_collect")


def run_scan(platform: str | None = None, mock_only: bool = False):
    """执行一轮扫描: 采集 → 评分 → L1 分析 → 写库"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from pulse.extractors.boom import (
        L1Analyzer,
        collect_posts,
        compute_baseline,
        freeze_evidence,
        list_creators,
    )
    from pulse.pipelines.boom_pipeline import BoomPipeline

    pipe = BoomPipeline()
    l1 = L1Analyzer()

    targets = list_creators(platform=platform) if platform else list_creators()
    logger.info(f"开始扫描: {len(targets)} 个创作者")

    total_collected = 0
    total_booms = 0

    for creator in targets:
        logger.info(f"  采集 [{creator.platform}] {creator.name}")
        try:
            posts = collect_posts(creator.platform, creator.platform_id, max_posts=20)
        except NotImplementedError as e:
            logger.warning(f"  ⚠ {e}")
            pipe.log_scan(
                creator.platform, 1, 0, 0,
                error=f"TikHub not configured for {creator.platform}"
            )
            continue

        if not posts:
            continue

        baseline = compute_baseline(posts, creator.platform)
        total_collected += len(posts)

        for post in posts:
            evidence = freeze_evidence(post, creator.followers or 10000, baseline)
            if evidence["grade_code"] in ("T3", "T2", "T1"):
                total_booms += 1
                logger.info(
                    f"    🔥 [{evidence['grade_code']}] "
                    f"{post.get('title', '')[:40]} "
                    f"(R={evidence['r_value']}, M={evidence['m_value']})"
                )

            # 写作品
            work = {
                "work_id": post.get("id", ""),
                "platform": creator.platform,
                "creator_id": creator.platform_id,
                "creator_name": creator.name,
                "title": post.get("title", ""),
                "create_time": post.get("create_time", 0),
                "likes": post.get("likes", 0),
                "comments": post.get("comments", 0),
                "collects": post.get("collects", 0),
                "shares": post.get("shares", 0),
                "content_type": post.get("content_type", "视频"),
                "cover_url": post.get("cover_url", ""),
                "video_url": post.get("video_url", ""),
                **evidence,
            }
            pipe.save_work(work)

            # L1 分析只对 T2+ 执行 (节约 API 预算)
            if evidence["grade_code"] in ("T3", "T2"):
                context = {
                    "baseline": baseline,
                    "grade": f"{evidence['grade_code']} {evidence['grade_label']}",
                }
                analysis = l1.analyze(post, context)
                analysis["tier"] = "L1"
                analysis["raw_result"] = dict(analysis)  # avoid self-reference
                pipe.save_analysis(analysis)
                logger.info(f"      L1分析完成: {analysis.get('summary', '')[:40]}...")

        pipe.log_scan(creator.platform, 1, len(posts),
                      sum(1 for p in posts if freeze_evidence(
                          p, creator.followers or 10000, baseline
                      )["grade_code"] in ("T3", "T2", "T1")))

    pipe.close()
    logger.info(f"扫描完成: {total_collected} 条作品, {total_booms} 个爆款")
    return total_collected, total_booms


def main():
    parser = argparse.ArgumentParser(description="爆款监控每日扫描")
    parser.add_argument("--platform", choices=["douyin", "xhs", "youtube"],
                        help="限定平台 (默认全部)")
    parser.add_argument("--mock-only", action="store_true",
                        help="仅用模拟数据 (跳过 TikHub)")
    args = parser.parse_args()

    start = time.time()
    collected, booms = run_scan(platform=args.platform, mock_only=args.mock_only)
    elapsed = time.time() - start
    logger.info(f"耗时: {elapsed:.1f}s | 采集: {collected} | 爆款: {booms}")


if __name__ == "__main__":
    main()
