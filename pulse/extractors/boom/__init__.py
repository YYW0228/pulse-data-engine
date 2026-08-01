"""pulse/extractors/boom/ — 社交媒体爆款监控模块

三级:
  creators.py     — 对标创作者注册表
  scorer.py       — R/M/Tier 三信号评分引擎
  collector.py    — 多平台采集器 (mock ↔ TikHub)
  analyzer.py     — L1 DeepSeek 快评 + L2 接口定义
"""

from .creators import CREATOR_LIST, list_creators, Platform, CreatorProfile
from .scorer import compute_baseline, compute_r, tier_of, grade_work, freeze_evidence
from .collector import collect_posts
from .analyzer import L1Analyzer, L2Spec

__all__ = [
    "CREATOR_LIST", "list_creators", "Platform", "CreatorProfile",
    "compute_baseline", "compute_r", "tier_of", "grade_work", "freeze_evidence",
    "collect_posts",
    "L1Analyzer", "L2Spec",
]
