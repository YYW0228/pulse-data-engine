"""
pulse/extractors/boss.py — BOSS直聘采集器 (ScraplingAdapter CDP 模式)

依赖:
  - Mac 本地, Brave/Chrome 浏览器
  - ScraplingAdapter(mode='cdp') 管理 CDP 生命周期

用法:
  from pulse.extractors.boss import BossExtractor
  extractor = BossExtractor()
  jobs = extractor.fetch_jobs(["AI", "大模型"])
"""
import json
import logging
import re

logger = logging.getLogger("pulse.extractor.boss")

HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]
KEYWORDS = ["AI", "大模型", "人工智能", "算法", "数据工程", "后端开发", "产品经理"]


def _parse_salary(s: str) -> tuple:
    """'30K-50K', '30k-50k', '30-50K', '30000-50000' → (30, 50)"""
    if not s:
        return None, None
    # 先尝试 '数字K-数字K' 格式
    m = re.search(r"(\d+)(?:K|k)?\s*[-~–至]\s*(\d+)(?:K|k)?", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        # 如果是元/月 (如 30000), 归一化到 k/月
        return (lo // 1000 or lo, hi // 1000 or hi) if lo > 1000 else (lo, hi)
    # 单值: '30K' 或 '30000'
    m = re.search(r"(\d+)(?:K|k)?", s)
    if m:
        v = int(m.group(1))
        v = v // 1000 if v > 1000 else v
        return (v, v)
    return None, None


class BossExtractor:
    """BOSS直聘数据采集器 — 基于 ScraplingAdapter CDP 模式

    利用用户本地 Brave/Chrome 的登录态 + CDP 协议绕过反爬。
    """

    def __init__(self):
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            from pulse.fetchers.scrapling_fetcher import ScraplingAdapter

            self._adapter = ScraplingAdapter(mode="cdp")
        return self._adapter

    def fetch_jobs(
        self,
        keywords: list[str] | None = None,
        cities: list[str] | None = None,
        max_pages: int = 2,
    ) -> list[dict]:
        """采集 BOSS 直聘职位

        Args:
            keywords: 搜索关键词 (默认 KEYWORDS)
            cities: 城市代码 (默认 HOT_CITIES)
            max_pages: 每城市每关键词页数
        """
        keywords = keywords or KEYWORDS
        cities = cities or HOT_CITIES
        all_jobs = []

        for kw in keywords:
            for city in cities:
                for pn in range(1, max_pages + 1):
                    jobs = self._fetch_page(kw, city, pn)
                    all_jobs.extend(jobs)
                    if jobs:
                        logger.info(
                            "BOSS %s city=%s p%d: %d 条", kw, city, pn, len(jobs)
                        )

        logger.info("BOSS 总计: %d 条", len(all_jobs))
        return all_jobs

    def _fetch_page(self, keyword: str, city: str, page_num: int) -> list[dict]:
        """抓取一页 BOSS 数据"""
        url = (
            f"https://www.zhipin.com/web/geek/job?"
            f"query={keyword}&city={city}&page={page_num}"
        )

        result = self.adapter.fetch(url, capture_xhr="search/joblist.json")

        if not result.success:
            logger.warning("BOSS fetch failed: %s", result.error_message)
            return []

        # 从捕获的 XHR 中找 joblist 数据
        for xhr in self.adapter.captured_xhr:
            try:
                data = json.loads(xhr["body"])
            except (json.JSONDecodeError, KeyError):
                continue

            if data.get("code") != 0:
                continue

            raw = data.get("zpData", {}).get("jobList", [])
            return [
                {
                    "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
                    "job_title": j.get("jobName", ""),
                    "company_name": j.get("brandName", ""),
                    "city": j.get("cityName", ""),
                    "salary_min_k": _parse_salary(j.get("salaryDesc", ""))[0],
                    "salary_max_k": _parse_salary(j.get("salaryDesc", ""))[1],
                    "education": j.get("jobDegree", ""),
                    "experience": j.get("jobExperience", ""),
                    "keyword": keyword,
                    "source": "boss",
                    "domain": "zhipin.com",
                }
                for j in raw
            ]

        logger.warning("BOSS API 未捕获: %s city=%s p%d", keyword, city, page_num)
        return []

    def close(self):
        if self._adapter:
            self._adapter.close_cdp()
            self._adapter = None


def fetch_all(limit_per_page: int = 2) -> list[dict]:
    """兼容 runner.py 接口"""
    extractor = BossExtractor()
    try:
        return extractor.fetch_jobs(max_pages=limit_per_page)
    finally:
        extractor.close()
