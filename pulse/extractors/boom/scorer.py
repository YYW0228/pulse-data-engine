"""
pulse/extractors/boom/scorer.py — R/M/Tier 三信号评分引擎

衡量一条内容是否"爆款"的核心逻辑：
  R   = 作品指标 / 创作者近20条中位数          (相对倍数)
  M   = 点赞数 / 粉丝数                       (破圈校验)
  Tier = 粉丝体量层 × M 门槛校准                (体量归一)

移植自 pluvio9yte 的 scorer.py (零外部依赖, 纯函数)
"""

from __future__ import annotations

import logging
import statistics
import time
from typing import Literal

logger = logging.getLogger("pulse.boom.scorer")

# ── 类型 ────────────────────────────────────────────────────────────

Grade = Literal["T3", "T2", "T1", "low_quality", "ordinary"]
Platform = Literal["douyin", "xhs", "youtube"]

# ── 核心指标选择 ────────────────────────────────────────────────────


def core_metric(platform: Platform, post: dict) -> float:
    """提取平台核心互动指标 (用于 R 值计算)"""
    if platform == "douyin":
        return float(post.get("likes", 0))
    elif platform == "xhs":
        # 小红书: 点赞 + 收藏 (互动总和)
        return float(post.get("likes", 0) + post.get("collects", 0))
    elif platform == "youtube":
        return float(post.get("likes", 0))
    return float(post.get("likes", 0))


# ── 信号一: R 值 (创作者内相对倍数) ──────────────────────────────────


def compute_baseline(posts: list[dict], platform: Platform, window: int = 20) -> float:
    """
    滚动中位数基线
    
    用中位数而非均值: 样本少时均值易被极端值带偏。
    至少返回 1.0 防止除零。
    """
    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("create_time") or 0,
        reverse=True,
    )
    values = [core_metric(platform, p) for p in sorted_posts[:window]]
    if not values:
        return 1.0
    return max(statistics.median(values), 1.0)


def compute_r(post_metric: float, baseline: float) -> float:
    """R = 这条作品的核心指标 / 基线中位数"""
    if baseline <= 0:
        return 1.0
    return round(post_metric / baseline, 2)


# ── 信号二: M 值 (赞粉比, 破圈校验) ─────────────────────────────────


def compute_m(likes: float, followers: float) -> float:
    """M = 点赞数 / 粉丝数
    
    M 值越高 → 内容在粉丝池之外也获得传播 → 破圈了
    """
    if followers <= 0:
        return 0.0
    return round(likes / followers, 4)


# ── 信号三: Tier (粉丝体量层 × M 门槛校准) ───────────────────────────


def tier_of(followers: int):
    """按粉丝量返回 (层级, M 基准)"""
    if followers < 10_000:
        return ("C", 0.30)    # 素人
    if followers < 100_000:
        return ("B", 0.15)    # 腰部
    if followers < 1_000_000:
        return ("A", 0.08)    # 中部
    return ("S", 0.04)         # 头部


# ── 分级阶梯 ────────────────────────────────────────────────────────


def grade_work(r: float, m: float, m_base: float) -> tuple[Grade, str]:
    """R 和 M 两个信号同时达标才能定级
    
    Args:
        r:      R 值 (相对倍数)
        m:      M 值 (赞粉比)
        m_base: 该 Tier 的 M 基准
    
    Returns:
        (grade_code, grade_label)
    """
    if r >= 8.0 and m >= 3.0 * m_base:
        return ("T3", "现象级")
    if r >= 4.0 and m >= 1.5 * m_base:
        return ("T2", "爆款")
    if r >= 2.0 and m >= 1.0 * m_base:
        return ("T1", "小爆")
    if r >= 2.0 and m < 1.0 * m_base:
        return ("low_quality", "低质爆款")
    return ("ordinary", "普通")


# ── 证据冻结 ────────────────────────────────────────────────────────


def freeze_evidence(post: dict, creator_followers: int, baseline: float) -> dict:
    """一条作品首次被评级时, 冻结当时的基线和粉丝快照
    
    后续同一作品的数据更新只改 R 的分子 (新互动数),
    不改基线 — 防止一个月后整体数据涨了回溯偏差。
    """
    platform: Platform = post.get("platform", "douyin")
    metric = core_metric(platform, post)
    r = compute_r(metric, baseline)
    m = compute_m(post.get("likes", 0), creator_followers)
    tier_name, m_base = tier_of(creator_followers)
    grade_code, grade_label = grade_work(r, m, m_base)

    evidence = {
        "work_id": post.get("id", ""),
        "grade_code": grade_code,
        "grade_label": grade_label,
        "r_value": r,
        "m_value": m,
        "m_base": m_base,
        "tier": tier_name,
        "creator_followers_at_grade": creator_followers,
        "baseline_at_grade": baseline,
        "baseline_sample_size": 20,
        "graded_at": int(time.time()),
        "likes_at_grade": post.get("likes", 0),
        "comments_at_grade": post.get("comments", 0),
        "collects_at_grade": post.get("collects", 0),
        "shares_at_grade": post.get("shares", 0),
    }
    return evidence
