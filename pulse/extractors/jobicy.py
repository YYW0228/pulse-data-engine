"""
pulse/extractors/jobicy.py — Jobicy 远程工作 API 适配器

数据源: https://jobicy.com/api/v2/remote-jobs
特点: 免费, 无需 API key, 结构化 JSON, 多分类
"""

import logging

logger = logging.getLogger("pulse.extractor.jobicy")

API_URL = "https://jobicy.com/api/v2/remote-jobs"


def _coerce_keyword(val: str | list[str]) -> str:
    """转 keyword 为字符串 (Jobicy 返回数组)"""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""


def fetch(count: int = 20, geo: str = "usa") -> list[dict]:
    """从 Jobicy API 获取远程岗位

    Args:
        count: 返回条数 (max 50)
        geo: 地区过滤 (usa / canada / anywhere)

    Returns:
        list[dict]: RawJobContract 兼容格式的岗位列表
    """
    import httpx

    url = f"{API_URL}?count={count}&geo={geo}"
    try:
        r = httpx.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Jobicy API 请求失败: {e}")
        return []

    jobs = data.get("jobs", [])
    logger.info(f"Jobicy: {len(jobs)} 条原始数据 (geo={geo})")

    results = []
    for job in jobs:
        # 薪资: Jobicy 返回 salary_currency + salary_min + salary_max (单位 千美元/年)
        sal_min = job.get("salaryMin")
        sal_max = job.get("salaryMax")
        # 转成 k/月 (美元年薪k → 月薪k)
        if sal_min and isinstance(sal_min, (int, float)):
            sal_min = max(1, int(sal_min / 12))
        if sal_max and isinstance(sal_max, (int, float)):
            sal_max = max(1, int(sal_max / 12))

        # 城市: jobLocation 字段, 可能是 "Remote - USA" 格式
        city = job.get("jobLocation", "") or job.get("jobLocation", "Remote")
        # 提取城市名 (去掉 "Remote - " 前缀)
        if city and city.startswith("Remote"):
            city = city.replace("Remote - ", "").replace("Remote, ", "").strip()
        if not city:
            city = "Remote"

        results.append(
            {
                "url": job.get("url", job.get("jobSlug", "")),
                "job_title": job.get("jobTitle", "Untitled"),
                "company_name": job.get("companyName", ""),
                "city": city,
                "salary_min_k": sal_min,
                "salary_max_k": sal_max,
                "education": None,
                "experience": None,
                "keyword": _coerce_keyword(job.get("jobIndustry", "")),
                "source": "jobicy",
                "domain": "jobicy.com",
            }
        )

    return results


def fetch_all(limit_per_geo: int = 15) -> list[dict]:
    """多地区抓取"""
    geos = ["usa", "canada", "anywhere"]
    all_jobs = []
    for geo in geos:
        jobs = fetch(count=limit_per_geo, geo=geo)
        all_jobs.extend(jobs)
    logger.info(f"Jobicy 总计: {len(all_jobs)} 条 (来自 {len(geos)} 个地区)")
    return all_jobs
