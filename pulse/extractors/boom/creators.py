"""
pulse/extractors/boom/creators.py — 对标创作者注册表

手动维护的一批"值得学习"的对标账号。
MVP 从 10 个开始 → 后续通过前端管理扩展到 142 个。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("pulse.boom.creators")

Platform = Literal["douyin", "xhs", "youtube"]


@dataclass
class CreatorProfile:
    """对标创作者画像"""
    name: str                     # 中文名/昵称
    platform: Platform
    platform_id: str              # 平台内唯一 ID
    handle: str = ""              # @handle (YouTube) / 小红书号
    followers: int = 0            # 当前粉丝 (锚定值，会被每日快照覆盖)
    niche: str = ""               # 赛道标签
    note: str = ""                # 备注定
    enabled: bool = True          # 是否在活跃扫描队列


# ── 初期 10 个对标 (来自 AI 培训/科技教育赛道) ──────────────────

CREATOR_LIST: list[CreatorProfile] = [
    # ── 抖音 AI 教育类 ──────────────────────────────────────
    CreatorProfile(name="(待定抖音1)", platform="douyin", platform_id="", niche="AI教育", note="待补充: 选AI工具/面试攻略类博主"),
    CreatorProfile(name="(待定抖音2)", platform="douyin", platform_id="", niche="科技资讯", note="待补充: 选AI行业动态类博主"),

    # ── 小红书职场/教育类 ────────────────────────────────────
    CreatorProfile(name="(待定小红书1)", platform="xhs", platform_id="", niche="职场进阶", note="待补充: 选转行/技能提升类博主"),
    CreatorProfile(name="(待定小红书2)", platform="xhs", platform_id="", niche="AI认知", note="待补充: 选AI科普/工具类博主"),

    # ── YouTube 技术教程类 ───────────────────────────────────
    CreatorProfile(name="(待定YouTube1)", platform="youtube", platform_id="", niche="AI教程", note="待补充: 选深度技术教程类"),
    CreatorProfile(name="(待定YouTube2)", platform="youtube", platform_id="", niche="行业分析", note="待补充: 选AI行业分析类"),

    # ── 混合/多平台 ─────────────────────────────────────────
    CreatorProfile(name="(待定技术博主)", platform="douyin", platform_id="", niche="编程教育", note="待补充"),
    CreatorProfile(name="(待定企业号)", platform="xhs", platform_id="", niche="AI治理", note="待补充"),
    CreatorProfile(name="(待定大师兄)", platform="youtube", platform_id="", niche="AI前沿", note="待补充"),
    CreatorProfile(name="(待定案例)", platform="douyin", platform_id="", niche="创业vlog", note="待补充"),
]


def list_creators(platform: Platform | None = None, niche: str | None = None) -> list[CreatorProfile]:
    """查询创作者，可按平台/赛道过滤"""
    result = [c for c in CREATOR_LIST if c.enabled]
    if platform:
        result = [c for c in result if c.platform == platform]
    if niche:
        result = [c for c in result if c.niche == niche]
    return result


def to_dict(creator: CreatorProfile) -> dict:
    return {
        "name": creator.name,
        "platform": creator.platform,
        "platform_id": creator.platform_id,
        "handle": creator.handle,
        "followers": creator.followers,
        "niche": creator.niche,
        "note": creator.note,
        "enabled": creator.enabled,
    }
