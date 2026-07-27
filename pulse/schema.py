"""
pulse/schema.py — 数据契约 (Data Contracts as Code)

每一条数据在进入 ODS 之前必须通过 Pydantic 校验。
校验失败 → SCHEMA_VIOLATION → 死信队列 (DLQ)。
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any
from enum import Enum
from datetime import datetime


class ExperienceLevel(str, Enum):
    ENTRY = "应届"
    JUNIOR = "1-3年"
    MID = "3-5年"
    SENIOR = "5-10年"
    EXPERT = "10年以上"


class EducationLevel(str, Enum):
    ANY = "不限"
    JUNIOR_COLLEGE = "大专"
    BACHELOR = "本科"
    MASTER = "硕士"
    PHD = "博士"


class RawJobContract(BaseModel):
    """招聘数据神圣契约 — 进入 ODS 前的终极校验"""

    # ── 必填字段 (None 直接拒绝) ──
    url: str = Field(..., min_length=5, description="岗位 URL，去重指纹源")
    job_title: str = Field(..., min_length=1, max_length=500, description="岗位标题")

    # ── 可选但类型必须正确 ──
    company_name: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=50)
    salary_min_k: Optional[int] = Field(None, ge=0, le=1000, description="最低薪资 (k/月)")
    salary_max_k: Optional[int] = Field(None, ge=0, le=1000, description="最高薪资 (k/月)")
    education: Optional[str] = Field(None, max_length=20)
    experience: Optional[str] = Field(None, max_length=20)
    keyword: Optional[str] = Field(None, max_length=100)
    source: Optional[str] = Field(None, max_length=50)
    domain: Optional[str] = Field(None, max_length=50)

    # ── 自定义校验器 ──

    @field_validator('salary_min_k', 'salary_max_k', mode='before')
    @classmethod
    def coerce_salary(cls, v: Any) -> Optional[int]:
        """薪资必须为数字。字符串 '25k'/'25000' 尝试转换，失败则拒绝"""
        if v is None:
            return None
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
        if isinstance(v, str):
            # 尝试解析 "25k", "25K", "25000"
            cleaned = v.strip().lower().replace('k', '000').replace(',', '')
            try:
                val = int(float(cleaned))
                if val > 0 and val < 1000000:
                    return val // 1000 if val > 1000 else val
            except ValueError:
                pass
            raise ValueError(f"薪资格式无法解析: {v}")
        raise ValueError(f"薪资类型错误: {type(v).__name__}")

    @field_validator('experience', mode='before')
    @classmethod
    def normalize_experience(cls, v: Any) -> Optional[str]:
        if v is None or v == '':
            return None
        valid_levels = {e.value for e in ExperienceLevel}
        if v in valid_levels:
            return v
        # 模糊匹配
        v_lower = v.strip().lower()
        mapping = {
            '应届': ExperienceLevel.ENTRY, 'entry': ExperienceLevel.ENTRY,
            '1年': ExperienceLevel.JUNIOR, '1-3': ExperienceLevel.JUNIOR,
            '3年': ExperienceLevel.MID, '3-5': ExperienceLevel.MID,
            '5年': ExperienceLevel.SENIOR, '5-10': ExperienceLevel.SENIOR,
            '10年': ExperienceLevel.EXPERT, '10以上': ExperienceLevel.EXPERT,
        }
        for key, level in mapping.items():
            if key in v_lower:
                return level.value
        return v  # 保留原始值但不拒绝

    @model_validator(mode='after')
    def check_salary_consistency(self):
        """薪资区间校验: max >= min"""
        if self.salary_min_k is not None and self.salary_max_k is not None:
            if self.salary_max_k < self.salary_min_k:
                raise ValueError(f"薪资区间异常: max({self.salary_max_k}) < min({self.salary_min_k})")
        return self


class ValidationResult(BaseModel):
    """单条数据的校验结果"""
    passed: bool
    record: dict = {}
    errors: list[dict] = []
    error_type: str = ""  # SCHEMA_VIOLATION, or empty if passed


class BatchValidationSummary(BaseModel):
    """批次校验汇总"""
    total: int
    passed: int
    failed: int
    violations: list[dict] = []  # [{url, field, error, raw_value}, ...]
    timestamp: datetime = Field(default_factory=datetime.now)
