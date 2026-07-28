"""
pulse/extractors/boss.py — BOSS直聘采集器 (Playwright + 登录态)

依赖:
  - data/boss_storage_state.json (通过 scripts/boss_cookies_setup.py 生成)
  - playwright (已安装)

用法:
  from pulse.extractors.boss import BossExtractor
  extractor = BossExtractor()
  jobs = extractor.fetch_jobs(["AI", "大模型"])
"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("pulse.extractor.boss")

# BOSS 直聘城市代码
CITY_CODES = {
    "北京": "100010000", "上海": "100020000", "深圳": "100030000",
    "杭州": "100040000", "广州": "100050000", "成都": "100060000",
    "武汉": "100070000", "南京": "100080000", "西安": "100090000",
}

# 热门城市代码(仅一线)
HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]

DEFAULT_STATE_PATH = Path("data/boss_storage_state.json")


class BossExtractor:
    """BOSS直聘数据采集器 (需登录态)"""

    def __init__(self, state_path: str | Path = DEFAULT_STATE_PATH):
        self.state_path = Path(state_path)
        if not self.state_path.exists():
            raise FileNotFoundError(
                f"登录态文件不存在: {self.state_path}\n"
                f"请先运行: uv run python scripts/boss_cookies_setup.py"
            )

    def _parse_salary(self, salary_desc: str) -> tuple[int | None, int | None]:
        """解析 '30K-50K' → (30, 50)"""
        if not salary_desc:
            return None, None
        m = re.search(r"(\d+)(?:K|k)(?:\s*[-~–至]\s*(\d+)(?:K|k)?)?", salary_desc)
        if m:
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            # 归一化到 k/月
            if lo > 1000:
                lo = lo // 1000
            if hi > 1000:
                hi = hi // 1000
            return lo, hi
        return None, None

    def _parse_experience(self, exp_str: str) -> str | None:
        """BOSS 经验字符串 → 标准格式"""
        mapping = {
            "在校/应届": "应届", "经验不限": None,
            "1年以内": "1年以下", "1-3年": "1-3年",
            "3-5年": "3-5年", "5-10年": "5-10年", "10年以上": "10年以上",
        }
        return mapping.get(exp_str, exp_str)

    def fetch_jobs(
        self,
        keywords: list[str] | None = None,
        cities: list[str] | None = None,
        max_pages: int = 2,
    ) -> list[dict]:
        """采集 BOSS 直聘职位

        Args:
            keywords: 搜索关键词, 默认 ["AI", "人工智能", "大模型", "算法"]
            cities: 城市代码列表, 默认 HOT_CITIES
            max_pages: 每城市每关键词最大页数
        """
        from playwright.sync_api import sync_playwright

        keywords = keywords or ["AI", "人工智能", "大模型", "算法"]
        cities = cities or HOT_CITIES
        all_jobs = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=str(self.state_path),
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
            )
            page = context.new_page()

            for kw in keywords:
                for city in cities:
                    for page_num in range(1, max_pages + 1):
                        jobs = self._fetch_page(page, kw, city, page_num)
                        all_jobs.extend(jobs)
                        logger.info(f"BOSS {kw} city={city} p{page_num}: {len(jobs)} 条")

            browser.close()

        logger.info(f"BOSS 直聘总计: {len(all_jobs)} 条")
        return all_jobs

    def _fetch_page(
        self, page, keyword: str, city: str, page_num: int
    ) -> list[dict]:
        """抓取一页 BOSS 直聘数据"""
        url = (
            f"https://www.zhipin.com/web/geek/job?"
            f"query={keyword}&city={city}&page={page_num}"
        )

        resp_body = []

        def on_response(response):
            if 'search/joblist.json' in response.url:
                try:
                    resp_body.append(response.body())
                except:
                    pass

        page.on('response', on_response)
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)

        if not resp_body:
            logger.warning(f"  BOSS API 无响应: {keyword} city={city} p{page_num}")
            return []

        try:
            data = json.loads(resp_body[0])
        except json.JSONDecodeError:
            return []

        if data.get('code') != 0:
            msg = data.get('message', '')
            logger.warning(f"  BOSS API error: {msg}")
            return []

        raw_jobs = data.get('zpData', {}).get('jobList', [])
        results = []
        for j in raw_jobs:
            sal_min, sal_max = self._parse_salary(j.get('salaryDesc', ''))
            results.append({
                "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
                "job_title": j.get('jobName', ''),
                "company_name": j.get('brandName', ''),
                "city": j.get('cityName', ''),
                "salary_min_k": sal_min,
                "salary_max_k": sal_max,
                "education": j.get('jobDegree', ''),
                "experience": self._parse_experience(j.get('jobExperience', '')),
                "keyword": keyword,
                "source": "boss",
                "domain": "zhipin.com",
            })
        return results


def fetch_all(limit_per_page: int = 2) -> list[dict]:
    """兼容 runner.py 的接口: 多关键词/城市采集"""
    extractor = BossExtractor()
    return extractor.fetch_jobs(max_pages=limit_per_page)
