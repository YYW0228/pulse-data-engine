"""
boss_fetcher.py — BOSS直聘采集 (最终版)

用法:
  首次: uv run python scripts/boss_fetcher.py          # 有头, 过验证码
  之后: uv run python scripts/boss_fetcher.py --headless  # 无头采集

流程:
  1. 用 Brave/Chrome 真实用户数据启动
  2. 首次需要你手动过验证码 (一次)
  3. 登录态保存后下次自动复用
"""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("boss")

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data/boss_storage_state.json"
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BRAVE_USER_DATA = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
CHROME_USER_DATA = Path.home() / "Library/Application Support/Google/Chrome"

HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]


def find_browser():
    """找用户安装的浏览器"""
    if os.path.exists(BRAVE_PATH):
        return BRAVE_PATH, BRAVE_USER_DATA
    if os.path.exists(CHROME_PATH):
        return CHROME_PATH, CHROME_USER_DATA
    return None, None


def is_running(proc_name: str) -> bool:
    try:
        return bool(subprocess.run(["pgrep", "-f", proc_name], capture_output=True, text=True, timeout=3).stdout.strip())
    except: return False


def parse_salary(s: str) -> tuple:
    if not s: return None, None
    m = re.search(r"(\d+)(?:K|k)?(?:\s*[-~–至]\s*(\d+)(?:K|k)?)?", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        return (lo // 1000 or lo, hi // 1000 or hi) if lo > 1000 else (lo, hi)
    return None, None


def fetch_jobs(keywords=None, cities=None, max_pages=2, headless=True):
    keywords = keywords or ["AI", "大模型", "人工智能", "算法"]
    cities = cities or HOT_CITIES
    all_jobs = []

    browser_path, user_data_dir = find_browser()
    if not browser_path:
        logger.error("未找到 Brave 或 Chrome")
        return []

    # 关掉正在运行的浏览器
    browser_name = "Brave Browser" if "Brave" in browser_path else "Google Chrome"
    if is_running(browser_name.replace(" ", "\\ ")):
        logger.info(f"正在退出 {browser_name}...")
        subprocess.run(["osascript", "-e", f'tell application "{browser_name}" to quit'], timeout=10)
        time.sleep(2)

    # 用临时目录复制用户数据 (避免锁)
    tmp_dir = Path(tempfile.mkdtemp(prefix="boss_profile_"))
    logger.info("准备浏览器环境...")

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(tmp_dir),
                headless=headless,
                executable_path=browser_path,
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
                        logger.info(f"BOSS {kw} city={city} p{pn}: {len(jobs)} 条")

            # 保存登录态
            state = context.storage_state()
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False))
            logger.info(f"✅ 登录态已保存 → {STATE_PATH}")
            context.close()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info(f"✅ BOSS 总计: {len(all_jobs)} 条")
    return all_jobs


def _fetch_page(page, keyword, city, page_num):
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
    page.wait_for_timeout(5000)

    if not resp_body:
        logger.warning(f"  ⚠️ API 无响应 (可能需过验证码)")
        return []

    data = json.loads(resp_body[0])
    if data.get('code') != 0:
        logger.warning(f"  ⚠️ API={data.get('code')}: {data.get('message','')}")
        return []

    raw = data.get('zpData', {}).get('jobList', [])
    return [{
        "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
        "job_title": j.get('jobName', ''),
        "company_name": j.get('brandName', ''),
        "city": j.get('cityName', ''),
        "salary_min_k": (parse_salary(j.get('salaryDesc', ''))[0]),
        "salary_max_k": (parse_salary(j.get('salaryDesc', ''))[1]),
        "education": j.get('jobDegree', ''),
        "experience": j.get('jobExperience', ''),
        "keyword": keyword,
        "source": "boss",
        "domain": "zhipin.com",
    } for j in raw]


def run_pipeline():
    """采集 → 校验 → DuckDB 全流程"""
    sys.path.insert(0, str(ROOT))
    from pulse.pipeline import Pipeline

    jobs = fetch_jobs(headless="--headless" in sys.argv)
    if not jobs:
        return

    logger.info(f"入库 {len(jobs)} 条...")
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


if __name__ == "__main__":
    run_pipeline()
