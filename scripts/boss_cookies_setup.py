"""
boss_cookies_setup.py — BOSS直聘 Cookies 导出

用法:
  uv run python scripts/boss_cookies_setup.py

流程:
  1. 打开浏览器窗口到 BOSS直聘
  2. 你手动登录 (扫码/手机验证码)
  3. 登录成功后按回车, storage state 自动保存
"""
import json
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("boss_cookies")

STATE_PATH = Path("data/boss_storage_state.json")

def main():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        page = context.new_page()

        logger.info("打开 BOSS直聘... 请在浏览器中手动登录 (扫码/手机)")
        page.goto(
            'https://www.zhipin.com/web/geek/job?query=AI&city=100010000',
            wait_until='domcontentloaded',
            timeout=30000
        )

        input("\n登录完成后，按 Enter 键保存登录状态...")

        # 保存完整 storage state (cookies + localStorage)
        state = context.storage_state()
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        logger.info(f"✅ 登录状态已保存 → {STATE_PATH} ({len(state.get('cookies',[]))} cookies)")

        # 验证: 用保存的状态启动无头浏览器
        logger.info("验证登录状态...")
        ctx2 = browser.new_context(
            storage_state=str(STATE_PATH),
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        page2 = ctx2.new_page()

        resp_body = []
        def on_resp(response):
            if 'search/joblist.json' in response.url:
                try:
                    resp_body.append(response.body())
                except:
                    pass
        page2.on('response', on_resp)

        page2.goto(
            'https://www.zhipin.com/web/geek/job?query=AI&city=100010000',
            wait_until='domcontentloaded',
            timeout=30000
        )
        page2.wait_for_timeout(5000)

        if resp_body:
            data = json.loads(resp_body[0])
            code = data.get('code')
            logger.info(f"验证结果: code={code}")
            if code == 0:
                jobs = data.get('zpData', {}).get('jobList', [])
                logger.info(f"✅ 成功! 获取到 {len(jobs)} 个职位")
                for job in jobs[:3]:
                    print(f"  {job.get('jobName')} @ {job.get('brandName')} - {job.get('salaryDesc')}")
            else:
                logger.warning(f"验证失败: {data.get('message', '')}")
        else:
            # 可能 timeout 不够，试 DOM 方式
            logger.info("尝试 DOM 提取...")
            try:
                cards = page2.eval_on_selector_all(
                    '[class*="job-card"], [class*="job-list"]',
                    'els => els.length'
                )
                logger.info(f"找到 {cards} 个 DOM 卡片")
            except:
                logger.warning("DOM 提取也失败")

        ctx2.close()
        browser.close()

if __name__ == '__main__':
    main()
