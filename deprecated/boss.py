"""
pulse/extractors/boss.py — BOSS直聘爬虫适配器 (Playwright)

状态: ⚠️ 需要有效 cookies
  - BOSS直聘在 headless 模式下返回空页 (code 37)
  - 需要真实浏览器登录后的 cookies 文件
  - 使用方式: 先在真实浏览器登录 BOSS, 导出 cookies 到 data/chrome_profile/
  - 或: 设置 HEADLESS=False, 手动登录一次

用法:
  from pulse.extractors.boss import BOSSCrawler
  crawler = BOSSCrawler(headless=True)
  jobs = await crawler.fetch_jobs("AI工程师")
"""

import asyncio
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("pulse.extractor.boss")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: {} };
"""

CITY_CODES = {
    "北京": "100010000",
    "上海": "100020000",
    "深圳": "100030000",
    "杭州": "100040000",
    "广州": "100050000",
    "成都": "100060000",
    "武汉": "100070000",
    "南京": "100080000",
    "西安": "100090000",
}

POSITIONS = ["AI工程师", "大模型", "数据工程", "后端开发", "DevOps", "产品经理", "技术总监"]


class BOSSCrawler:
    def __init__(
        self,
        headless: bool = True,
        profile_dir: str = "data/chrome_profile",
        cookies_file: str = "data/boss_cookies.json",
    ):
        self.headless = headless
        self.profile_dir = Path(profile_dir)
        self.cookies_file = Path(cookies_file)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def _setup_page(self, browser) -> tuple:
        """创建反检测页面"""
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        # 加载已有 cookies
        if self.cookies_file.exists():
            cookies = json.loads(self.cookies_file.read_text())
            await context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies")

        page = await context.new_page()
        await page.add_init_script(STEALTH_JS)
        return page, context

    async def fetch_jobs(
        self, position: str, city_code: str = "100010000", max_pages: int = 3
    ) -> list[dict]:
        """抓取 BOSS直聘职位列表"""
        from playwright.async_api import async_playwright

        all_jobs = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless, args=["--disable-blink-features=AutomationControlled"]
            )
            page, context = await self._setup_page(browser)

            for page_num in range(1, max_pages + 1):
                url = (
                    f"https://www.zhipin.com/web/geek/job?"
                    f"city={city_code}&query={position}&page={page_num}"
                )
                try:
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                    await asyncio.sleep(2)

                    # 检测反爬
                    if "captcha" in await page.content():
                        logger.warning(f"CAPTCHA on page {page_num} for {position}")
                        break

                    jobs = await page.evaluate("""() => {
                        const items = document.querySelectorAll('.job-list-item, .job-card-wrapper');
                        return Array.from(items).map(el => ({
                            url: el.querySelector('a')?.href || '',
                            job_title: el.querySelector('.job-name, .job-title')?.textContent?.trim() || '',
                            company_name: el.querySelector('.company-name, .company-full-name')?.textContent?.trim() || '',
                            city: el.querySelector('.job-area, .job-city')?.textContent?.trim() || '',
                            salary_text: el.querySelector('.salary, .job-salary')?.textContent?.trim() || '',
                            source: 'boss',
                            domain: 'zhipin.com'
                        }));
                    }""")

                    for job in jobs:
                        job["salary_min_k"], job["salary_max_k"] = self._parse_salary(
                            job.pop("salary_text", "")
                        )

                    all_jobs.extend(jobs)
                    logger.info(f"BOSS {position} p{page_num}: {len(jobs)} jobs")

                except Exception as e:
                    logger.warning(f"BOSS {position} p{page_num}: {e}")
                    break

            await context.close()
            await browser.close()

        return all_jobs

    @staticmethod
    def _parse_salary(salary_text: str) -> tuple[int | None, int | None]:
        """解析 '30-50k' → (30, 50)"""
        if not salary_text:
            return None, None
        m = re.search(r"(\d+)-(\d+)\s*k", salary_text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None, None

    @staticmethod
    @staticmethod
    def save_cookies_guide() -> None:
        """打印 cookies 导出指南"""
        print("""
BOSS直聘 Cookies 导出指南:
  1. 在真实浏览器登录 https://www.zhipin.com
  2. 打开 DevTools → Application → Cookies
  3. 导出 cookies 为 JSON 文件 → data/boss_cookies.json
  4. 或使用 Playwright 的 playwright.open 录制:
     $ python -c "from pulse.extractors.boss import BOSSCrawler; import asyncio; asyncio.run(BOSSCrawler(headless=False).fetch_jobs('测试'))"
     # 手动登录一次, cookies 自动保存到 data/chrome_profile/
""")


async def fetch_all(limit_per_category: int = 3) -> list[dict]:
    """多职位并发抓取 (异步)"""
    crawler = BOSSCrawler(headless=True)
    positions = POSITIONS
    tasks = [crawler.fetch_jobs(pos, max_pages=limit_per_category) for pos in positions]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs = []
    for r in results:
        if isinstance(r, list):
            all_jobs.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"BOSS fetch failed: {r}")
    return all_jobs
