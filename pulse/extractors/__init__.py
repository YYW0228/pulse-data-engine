"""
pulse/extractors/remotive.py — Remotive 远程工作 API 适配器

数据源: https://remotive.com/api/remote-jobs
特点: 免费, 无需 API key, 结构化 JSON, 实时
"""
import re, logging, httpx
from datetime import datetime
from typing import Optional

logger = logging.getLogger("pulse.extractor.remotive")

API_URL = "https://remotive.com/api/remote-jobs"


def parse_salary(salary_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """解析薪资格式: '$50k-$100k' → (50, 100)"""
    if not salary_str or salary_str == "-":
        return None, None
    salary_str = salary_str.replace(",", "").replace("$", "").replace(" ", "")
    # 尝试匹配 "50k-100k" 或 "50k"
    match = re.match(r"(\d+)(?:k?)(?:\s*-\s*(\d+)k?)?", salary_str, re.IGNORECASE)
    if match:
        lo = int(match.group(1))
        hi = int(match.group(2)) if match.group(2) else lo
        return (lo, hi) if lo and hi else (None, None)
    return None, None


def fetch(category: str = "data", limit: int = 20) -> list[dict]:
    """从 Remotive API 抓取岗位数据, 转换为 RawJobContract 兼容格式"""
    url = f"{API_URL}?category={category}&limit={limit}"
    try:
        r = httpx.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Remotive API 请求失败: {e}")
        return []

    jobs = data.get("jobs", [])
    logger.info(f"Remotive: {len(jobs)} 条原始数据")

    results = []
    for job in jobs:
        salary_min, salary_max = parse_salary(job.get("salary"))
        results.append({
            "url": job.get("url", ""),
            "job_title": job.get("title", ""),
            "company_name": job.get("company_name", ""),
            "city": job.get("candidate_required_location", "Remote") or "Remote",
            "salary_min_k": salary_min,
            "salary_max_k": salary_max,
            "education": None,
            "experience": None,
            "keyword": job.get("category", ""),
            "source": "remotive",
            "domain": job.get("category", ""),
        })
    return results


def fetch_all(limit_per_category: int = 10) -> list[dict]:
    """多类别抓取"""
    categories = ["data", "engineering", "artificial-intelligence", "product",
                   "management", "design", "sales", "marketing"]
    all_jobs = []
    for cat in categories:
        jobs = fetch(cat, limit_per_category)
        all_jobs.extend(jobs)
    logger.info(f"Remotive 总计: {len(all_jobs)} 条 (来自 {len(categories)} 个分类)")
    return all_jobs
