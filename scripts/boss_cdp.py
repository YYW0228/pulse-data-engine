"""
BOSS 直聘采集 — Playwright CDP + Brave

流程:
  1. 启动 Brave (带 --remote-debugging-port=9222)
  2. Playwright connect_over_cdp 连接
  3. 利用 Brave 已有的登录态, 逐个关键词/城市采集
  4. 数据 -> DuckDB

用法:
  uv run python scripts/boss_cdp.py
"""
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("boss_cdp")

ROOT = Path(__file__).resolve().parent.parent
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CDP_PORT = 9222

HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]
KEYWORDS = ["AI", "大模型", "人工智能", "算法", "数据工程", "后端开发", "产品经理"]


def parse_salary(s: str) -> tuple:
    if not s: return None, None
    m = re.search(r"(\d+)(?:K|k)?(?:\s*[-~–至]\s*(\d+)(?:K|k)?)?", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        return (lo // 1000 or lo, hi // 1000 or hi) if lo > 1000 else (lo, hi)
    return None, None


def start_brave():
    """关掉旧的, 启动 Brave CDP"""
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to quit'], timeout=5)
    time.sleep(1)
    brave = subprocess.Popen(
        [BRAVE_PATH, f"--remote-debugging-port={CDP_PORT}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # 等 CDP
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
            logger.info(f"Brave CDP 就绪 (pid={brave.pid})")
            return brave
        except Exception:
            time.sleep(1)
    logger.error("Brave CDP 启动超时")
    return brave


def fetch_jobs(keywords=None, cities=None, max_pages=2):
    """通过 CDP + Brave 采集 BOSS 直聘"""
    keywords = keywords or KEYWORDS
    cities = cities or HOT_CITIES
    all_jobs = []

    brave_proc = start_brave()

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # 连接到 Brave CDP
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            logger.info(f"已连接 Brave, 默认上下文: {len(browser.contexts)} 个")

            # 用默认上下文 (继承 Brave 的登录态)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            for kw in keywords:
                for city in cities:
                    for pn in range(1, max_pages + 1):
                        jobs = _fetch_page(page, kw, city, pn)
                        all_jobs.extend(jobs)
                        logger.info(f"✓ {kw} {city} p{pn}: {len(jobs)} 条")

            browser.close()

    finally:
        if brave_proc:
            brave_proc.terminate()
            time.sleep(1)
            if brave_proc.poll() is None:
                brave_proc.kill()

    logger.info(f"总计: {len(all_jobs)} 条")
    return all_jobs


def _fetch_page(page, keyword, city, page_num):
    """在已有页面中导航, 捕获 API 响应"""
    url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}&page={page_num}"
    resp_data = []

    def on_resp(response):
        if 'search/joblist.json' in response.url:
            try:
                body = response.body()
                data = json.loads(body)
                resp_data.append(data)
            except:
                pass

    page.on('response', on_resp)
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)

    if not resp_data:
        logger.warning(f"  ⚠️ 无响应: {keyword} {city} p{page_num}")
        # 检查页面状态
        title = page.title()
        body_text = page.eval_on_selector('body', 'el => el.innerText.substring(0, 200)')
        if '安全验证' in title:
            logger.warning(f"  安全验证, 请在浏览器中手动通过")
        return []

    data = resp_data[0]
    if data.get('code') != 0:
        logger.warning(f"  ⚠️ API={data.get('code')}: {data.get('message','')}")
        return []

    raw = data.get('zpData', {}).get('jobList', [])
    return [{
        "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
        "job_title": j.get('jobName', ''),
        "company_name": j.get('brandName', ''),
        "city": j.get('cityName', ''),
        "salary_min_k": parse_salary(j.get('salaryDesc', ''))[0],
        "salary_max_k": parse_salary(j.get('salaryDesc', ''))[1],
        "education": j.get('jobDegree', ''),
        "experience": j.get('jobExperience', ''),
        "keyword": keyword,
        "source": "boss",
        "domain": "zhipin.com",
    } for j in raw]


def run_pipeline():
    jobs = fetch_jobs()
    if not jobs:
        logger.warning("未采集到数据, 退出")
        return

    sys.path.insert(0, str(ROOT))
    from pulse.pipeline import Pipeline

    p = Pipeline()
    p.init_schema()
    result = p.validate_and_route(jobs)
    logger.info(f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败")

    if result["passed"]:
        stats = p.merge_into_ods(result["passed"])
        logger.info(f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变")

    p.refresh_dwd()
    p.refresh_dws()
    row = p.con.execute("SELECT COUNT(*) FROM ods_raw_jobs WHERE is_latest=TRUE").fetchone()
    logger.info(f"✅ 完成! ODS={row[0] if row else 0} 行")
    p.close()

    print(f"\n✅ 入库完成! ODS={row[0] if row else 0} 行")
    print("运行 push-pulse 推送到 VPS")


if __name__ == "__main__":
    run_pipeline()
