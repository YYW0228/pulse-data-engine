"""pulse/contracts/retail.py — 零售商品数据契约 (ProductContract)"""

from pydantic import BaseModel, Field, field_validator
from typing import Any


class ProductContract(BaseModel):
    """商品数据契约 — 跨境电商/零售领域"""

    url: str = Field(..., min_length=5, description="商品链接 (去重指纹)")
    product_title: str = Field(..., min_length=1, max_length=500, description="商品标题")
    price: float | None = Field(None, ge=0, le=1_000_000, description="售价 (元)")
    original_price: float | None = Field(None, ge=0, le=1_000_000, description="原价")
    stock: int | None = Field(None, ge=0, le=100_000, description="库存量")
    category: str | None = Field(None, max_length=100, description="品类")
    brand: str | None = Field(None, max_length=200, description="品牌")
    supplier: str | None = Field(None, max_length=200, description="供应商")
    source: str | None = Field(None, max_length=50, description="数据源")
    domain: str | None = Field(None, max_length=50)

    @field_validator("price", "original_price", mode="before")
    @classmethod
    def coerce_price(cls, v: Any) -> float | None:
        if v is None:
            return None
        return round(float(v), 2)


def product_to_ods(product: dict) -> dict:
    """适配器: ProductContract → ODS 表结构

    将零售商品字段映射到现有 ods_raw_jobs 表的通用列:
      product_title  → job_title (标题)
      price          → salary_min_k (数值1)
      original_price → salary_max_k (数值2)
      category       → keyword (分类)
      brand          → company_name (品牌/公司)
      supplier       → education (额外文本)
      stock          → experience (整数值)
    """
    return {
        "url": product["url"],
        "job_title": product.get("product_title", ""),
        "company_name": product.get("brand", ""),
        "city": product.get("supplier", ""),
        "salary_min_k": int(product["price"]) if product.get("price") is not None else None,
        "salary_max_k": int(product["original_price"]) if product.get("original_price") is not None else None,
        "education": str(product.get("stock", "")) if product.get("stock") is not None else None,
        "experience": product.get("category", ""),
        "keyword": product.get("category", ""),
        "source": product.get("source", "shopify"),
        "domain": product.get("domain", "shopify.com"),
    }
