"""
BOSS 直聘终极采集 — CDP + Scrapling DynamicFetcher

原理:
  1. 用 Subprocess 启动 Brave (带 --remote-debugging-port=9222)
  2. Scrapling DynamicFetcher 通过 CDP 连接到 Brave
  3. capture_xhr 自动捕获 search/joblist.json 的 API 响应
  4. 全程用"真实浏览器 + 真实登录态", 零风控

用法:
  uv run python scripts/boss_fetcher_cdp.py
"""
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("boss_cdp")

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data/boss_storage_state.json"
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CDP_PORT = 9222

HOT_CITIES = ["100010000", "100020000", "100030000", "100040000", "100050000"]
KEYWORDS = ["AI", "大模型", "人工智能", "算法", "数据工程", "后端开发", "产品经理"]


def parse_salary(s: str) -> tuple:
    import re
    if not s: return None, None
    m = re.search(r"(\d+)(?:K|k)?(?:\s*[-~–至]\s*(\d+)(?:K|k)?)?", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        return (lo // 1000 or lo, hi // 1000 or hi) if lo > 1000 else (lo, hi)
    return None, None


def start_brave():
    """启动 Brave 带 CDP"""
    # 先关掉正在运行的 Brave
    subprocess.run(["osascript", "-e", 'tell application "Brave Browser" to quit'], timeout=5)
    time.sleep(1)

    # 用新进程启动 Brave (不要阻塞)
    brave = subprocess.Popen(
        [BRAVE_PATH, f"--remote-debugging-port={CDP_PORT}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    logger.info(f"Brave 已启动 (pid={brave.pid}), CDP 端口 {CDP_PORT}")

    # 等 CDP 就绪
    import urllib.request
    for _ in range(15):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
            logger.info("CDP 就绪")
            return brave
        except Exception:
            time.sleep(1)
    logger.warning("CDP 未就绪, 继续尝试...")
    return brave


def fetch_jobs_cdp(keywords=None, cities=None, max_pages=2):
    """通过 CDP 连接到 Brave 采集 BOSS 数据"""
    keywords = keywords or KEYWORDS
    cities = cities or HOT_CITIES
    all_jobs = []

    brave_proc = start_brave()

    try:
        from scrapling.fetchers import DynamicFetcher

        # 只需一次会话 — 登录态在 Brave 中已有
        page = DynamicFetcher.fetch(
            "https://www.zhipin.com/web/geek/job?query=AI&city=100010000",
            cdp_url=f"http://127.0.0.1:{CDP_PORT}",
            headless=False,  # 让用户看到浏览器
            capture_xhr="search/joblist.json",
            timeout=30000,
        )

        # 检查是否成功
        if page.status >= 400:
            logger.error(f"BOSS 页面加载失败: status={page.status}")
            return []

        # 已捕获的 API 数据
        captured = getattr(page, 'captured_xhr', [])
        logger.info(f"页面加载完成, 已捕获 {len(captured)} 个 API 响应")

        # 从第一个捕获的响应中提取数据
        if captured:
            for c in captured:
                try:
                    data = json.loads(c.get('body', '{}'))
                except (json.JSONDecodeError, TypeError):
                    # 可能是 Response 对象
                    if hasattr(c, 'text'):
                        try:
                            data = json.loads(c.text)
                        except:
                            continue
                    else:
                        continue

                if data.get('code') == 0:
                    jobs = data.get('zpData', {}).get('jobList', [])
                    kw = "AI"  # 当前搜索词
                    for j in jobs:
                        s_min, s_max = parse_salary(j.get('salaryDesc', ''))
                        all_jobs.append({
                            "url": f"https://www.zhipin.com/job_detail/{j.get('encryptJobId', '')}.html",
                            "job_title": j.get('jobName', ''),
                            "company_name": j.get('brandName', ''),
                            "city": j.get('cityName', ''),
                            "salary_min_k": s_min,
                            "salary_max_k": s_max,
                            "education": j.get('jobDegree', ''),
                            "experience": j.get('jobExperience', ''),
                            "keyword": kw,
                            "source": "boss",
                            "domain": "zhipin.com",
                        })
                        logger.info(f"  通过 capture_xhr 获取 {len(jobs)} 条")

        # 如果 capture_xhr 没有数据, 尝试逐个 API 调用来采集多个关键词
        if not all_jobs:
            logger.info("capture_xhr 无数据, 尝试逐个调用 API...")
            # 这里需要保持会话, 可能要用 DynamicSession

        # 保存登录态
        if hasattr(page, 'storage_state'):
            state = page.storage_state()
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False))
            logger.info(f"登录态已保存 → {STATE_PATH}")

    finally:
        # 关闭 Brave
        if brave_proc:
            brave_proc.terminate()
            time.sleep(1)
            if brave_proc.poll() is None:
                brave_proc.kill()

    logger.info(f"BOSS 总计: {len(all_jobs)} 条")
    return all_jobs


def run_pipeline():
    jobs = fetch_jobs_cdp()
    if not jobs:
        logger.warning("未采集到数据")
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

    print(f"\n✅ 入库完成! 运行 push-pulse 推送到 VPS")


if __name__ == "__main__":
    run_pipeline()
