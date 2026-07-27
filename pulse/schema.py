"""
pulse/schema.py — 数据契约 (Data Contracts)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawJob:
    """原始岗位数据契约 — 进入 ODS 前的最小合法性校验"""
    url: str
    job_title: str
    company_name: Optional[str] = None
    city: Optional[str] = None
    salary_min_k: Optional[int] = None
    salary_max_k: Optional[int] = None
    education: Optional[str] = None
    experience: Optional[str] = None
    keyword: Optional[str] = None
    source: Optional[str] = None
    domain: Optional[str] = None


@dataclass
class DLQEntry:
    """死信队列条目 — 网络/解析失败的原始数据"""
    url: str
    error_type: str  # HTTP_429, HTTP_5xx, PARSE_ERROR, TIMEOUT
    error_message: str
    http_status: Optional[int] = None
    raw_payload: str = ""
    failed_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
