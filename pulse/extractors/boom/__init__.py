"""pulse/extractors/boom/ — 社交媒体爆款监控模块

三级:
  creators.py     — 对标创作者注册表
  scorer.py       — R/M/Tier 三信号评分引擎
  collector.py    — 多平台采集器 (mock ↔ TikHub)
  analyzer.py     — L1 DeepSeek 快评 + L2 接口定义
"""

from .analyzer import L1Analyzer, L2Spec
from .collector import collect_posts
from .creators import CREATOR_LIST, CreatorProfile, Platform, list_creators
from .scorer import compute_baseline, compute_r, freeze_evidence, grade_work, tier_of

__all__ = [
    "CREATOR_LIST",
    "CreatorProfile",
    "L1Analyzer",
    "L2Spec",
    "Platform",
    "collect_posts",
    "compute_baseline",
    "compute_r",
    "freeze_evidence",
    "grade_work",
    "list_creators",
    "tier_of",
]
