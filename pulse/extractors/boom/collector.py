"""
pulse/extractors/boom/collector.py — 多平台采集器

两层:
  MockCollector  — 无需 API key, 生成模拟数据 (开发/演示用)
  TikHubCollector — 接入 TikHub API (生产用, 需 API key)

使用方法:
  collector = get_collector()           # 自动检测: 有 key → TikHub, 无 → Mock
  posts = collector.collect("douyin", platform_id="xxx")
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

logger = logging.getLogger("pulse.boom.collector")

# ── 自动检测可用引擎 ─────────────────────────────────────────────────


def _tikhub_key() -> str | None:
    """从环境变量获取 TikHub API key"""
    return os.environ.get("TIKHUB_API_KEY") or None


# ── 模拟数据生成 ────────────────────────────────────────────────────


class MockCollector:
    """零依赖模拟采集器 — 用于开发/演示 / 等待 API key 期间"""

    def __init__(self):
        logger.info("[MockCollector] 启动 — 使用模拟数据 (无 TikHub API key)")

    def collect(self, platform: str, platform_id: str, max_posts: int = 20) -> list[dict]:
        """生成模拟作品列表"""
        now = int(time.time())
        posts: list[dict[str, Any]] = []
        for i in range(max_posts):
            base_likes = random.randint(200, 5000)
            posts.append({
                "id": f"mock_{platform}_{platform_id}_{i}",
                "platform": platform,
                "creator_id": platform_id,
                "title": f"模拟作品 #{i+1} — {self._random_title(platform)}",
                "create_time": now - i * 3600 * random.randint(4, 48),
                "likes": base_likes,
                "comments": int(base_likes * random.uniform(0.02, 0.08)),
                "collects": int(base_likes * random.uniform(0.01, 0.05)),
                "shares": int(base_likes * random.uniform(0.005, 0.03)),
                "content_type": random.choice(["视频", "图文"]),
                "cover_url": "",
                "video_url": "",
                "is_mock": True,
            })
        # 让最近 2-3 条数据明显高于基线 (模拟爆款)
        for i in range(min(3, len(posts))):
            posts[i]["likes"] = int(posts[i]["likes"] or 0) * random.randint(5, 15)
            posts[i]["comments"] = int(posts[i]["comments"] or 0) * random.randint(3, 10)
            posts[i]["title"] = f"[🔥模拟爆款] {posts[i]['title']}"
        logger.info(
            f"[MockCollector] 生成了 {len(posts)} 条模拟数据 "
            f"(platform={platform}, creator={platform_id})"
        )
        return posts

    @staticmethod
    def _random_title(platform: str) -> str:
        titles = {
            "douyin": [
                "用 Claude 写代码有多爽",
                "面试AI岗千万别这么说",
                "大模型公司都在偷偷学这个",
                "月薪6万的AI工程师在做什么",
            ],
            "xhs": [
                "从零转行AI治理的100天",
                "AI工程师必备的5项硬技能",
                "2026年最值得学的AI技术栈",
            ],
            "youtube": [
                "Building RAG from Scratch",
                "FineTuning vs RAG: The Real Difference",
                "AI Governance in 2026: Complete Guide",
            ],
        }
        return random.choice(titles.get(platform, titles["douyin"]))


# ── TikHub 采集器 (占位) ────────────────────────────────────────────


class TikHubCollector:
    """TikHub API 采集器 (需 TIKHUB_API_KEY 环境变量)"""

    BASE_URL = "https://api.tikhub.io/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        logger.info("[TikHubCollector] 启动 — 使用 TikHub API")

    def collect(self, platform: str, platform_id: str, max_posts: int = 20) -> list[dict]:
        """
        从 TikHub 拉取指定创作者的最新作品。
        
        TODO: 实现具体的 TikHub API 调用
        - 抖音: /douyin/creator/posts?uid={platform_id}
        - 小红书: /xhs/creator/notes?user_id={platform_id}
        - YouTube: /youtube/channel/videos?channel_id={platform_id}
        
        返回格式与 MockCollector 一致。
        """
        raise NotImplementedError(
            "TikHub 采集器尚未实现。请设置 TIKHUB_API_KEY 环境变量并重试。"
        )


# ── 工厂函数 ────────────────────────────────────────────────────────


def get_collector() -> MockCollector | TikHubCollector:
    """根据是否配置 API key 返回合适的采集器"""
    key = _tikhub_key()
    if key:
        return TikHubCollector(key)
    return MockCollector()


def collect_posts(platform: str, platform_id: str, max_posts: int = 20) -> list[dict]:
    """快捷入口: 一步采集"""
    collector = get_collector()
    return collector.collect(platform, platform_id, max_posts=max_posts)
