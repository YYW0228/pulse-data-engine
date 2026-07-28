"""
BOSS直聘采集器 v2 — 用 Brave 真实浏览器

原理:
  用 Brave 的 User Data 启动, 继承你已有的登录态.
  首次运行可能需要手动过安全验证, 之后自动复用.
"""
import json
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boss")

STATE_PATH = Path("data/boss_storage_state.json")

CITY_CODES = {
    "北京": "100010000", "上海": "100020000", "深圳": "100030000",
    "杭州": "100040000", "广州": "100050000", "成都": "100060000",
}
HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]


def parse_salary(salary_desc: str) -> tuple:
    import re
    if not salary_desc:
        return None, None
    m = re.search(r"(\d+)(?:K|k)(?:\s*[-~–至]\s*(\d+)(?:K|k)?)?", salary_desc)
    if m:
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        return (lo // 1000 or lo, hi // 1000 or hi) if lo > 1000 else (lo, hi)
    return None, None


def fetch_jobs(
    keywords: list[str] | None = None,
    cities: list[str] | None = None,
    max_pages: int = 2,
    headless: bool = True,
) -> list[dict]:
    """采集 BOSS直聘 (使用 Brave 登录态)"""
    keywords = keywords or ["AI", "大模型", "人工智能", "算法"]
    cities = cities or HOT_CITIES
    all_jobs = []

    # Mac 上 Brave 的用户数据目录
    brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    user_data_dir = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"

    with sync_playwright() as p:
        # 用 Brave 可执行文件 + 持久化上下文 (继承登录态)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            executable_path=brave_path,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        for kw in keywords:
            for city in cities:
                for pn in range(1, max_pages + 1):
                    jobs = _fetch_page(page, kw, city, pn)
                    all_jobs.extend(jobs)
                    logger.info(f"BOSS {kw} {city} p{pn}: {len(jobs)} 条")

        # 保存登录态供后续无头使用
        state = context.storage_state()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False))
        logger.info(f"登录态已保存 → {STATE_PATH}")

        context.close()

    logger.info(f"BOSS 总计: {len(all_jobs)} 条")
    return all_jobs


def _fetch_page(page, keyword: str, city: str, page_num: int) -> list[dict]:
    """抓取一页"""
    url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}&page={page_num}"
    resp_body = []

    def on_resp(response):
        if 'search/joblist.json' in response.url:
            try:
                resp_body.append(response.body())
            except:
                pass

    page.on('response', on_resp)
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)

    if not resp_body:
        logger.warning(f"  API 无响应: {keyword} {city} p{page_num}")
        return []

    data = json.loads(resp_body[0])
    if data.get('code') != 0:
        logger.warning(f"  API error: {data.get('message', '')}")
        return []

    raw = data.get('zpData', {}).get('jobList', [])
    results = []
    for j in raw:
        sal_min, sal_max = parse_salary(j.get('salaryDesc', ''))
        results.append({
            "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
            "job_title": j.get('jobName', ''),
            "company_name": j.get('brandName', ''),
            "city": j.get('cityName', ''),
            "salary_min_k": sal_min,
            "salary_max_k": sal_max,
            "education": j.get('jobDegree', ''),
            "experience": j.get('jobExperience', ''),
            "keyword": keyword,
            "source": "boss",
            "domain": "zhipin.com",
        })
    return results


if __name__ == "__main__":
    # 测试：先有头模式运行一次，过安全验证
    import sys
    headless = "--headless" in sys.argv
    jobs = fetch_jobs(headless=headless, max_pages=1)
    print(f"\n✅ 采集 {len(jobs)} 条")
    for j in jobs[:5]:
        print(f"  {j['job_title']} @ {j['company_name']} | {j.get('salary_min_k','')}-{j.get('salary_max_k','')}k")
