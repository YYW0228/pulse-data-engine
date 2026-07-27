"""pulse/extractors/shopify_mock.py — 跨境电商 Mock 数据源

模拟 Shopify API 返回, 包含正常数据 + 脏数据 (测试 DLQ + Circuit Breaker)
"""
import logging
import random

logger = logging.getLogger("pulse.extractor.shopify")

# ── 真实商品样本 ──────────────────────────────────────────────────────

PRODUCTS = [
    {"title": "无线蓝牙耳机 AirPods Pro 2", "price": 299, "stock": 1500, "category": "电子产品", "brand": "TechBrand"},
    {"title": "有机绿茶 500g 礼盒装", "price": 89, "stock": 3200, "category": "食品饮料", "brand": "山间茶园"},
    {"title": "女士纯棉T恤 圆领短袖", "price": 59, "stock": 2800, "category": "服装", "brand": "SimpleWear"},
    {"title": "智能手表 Amazfit GTR 4", "price": 189, "stock": 890, "category": "电子产品", "brand": "Amazfit"},
    {"title": "不锈钢保温杯 500ml", "price": 45, "stock": 5000, "category": "家居", "brand": "HomePlus"},
    {"title": "儿童益智积木 200粒", "price": 79, "stock": 2100, "category": "玩具", "brand": "乐智"},
    {"title": "男士商务皮鞋 真皮", "price": 268, "stock": 760, "category": "鞋靴", "brand": "商务绅士"},
    {"title": "瑜伽垫 加厚防滑 10mm", "price": 39, "stock": 4200, "category": "运动户外", "brand": "FitLife"},
    {"title": "猫粮 成猫 鸡肉味 2kg", "price": 59, "stock": 3800, "category": "宠物用品", "brand": "PetCare"},
    {"title": "移动电源 20000mAh 快充", "price": 129, "stock": 1600, "category": "电子产品", "brand": "PowerUp"},
]

DIRTY_RECORDS = [
    # 空标题
    {"title": "", "price": 99, "stock": 100, "category": "测试", "brand": "TestBrand"},
    # 负价格
    {"title": "异常商品-负价", "price": -50, "stock": 10, "category": "异常", "brand": "BadBrand"},
    # 超长库存 (超出 SQL field 范围)
    {"title": "虚拟商品", "price": 9999, "stock": 10 ** 7, "category": "虚拟", "brand": "云服务"},
    # URL 过短
    {"title": "短链接商品", "price": 299, "stock": 100, "category": "电子产品", "brand": None},
]


def _generate(count: int = 100, dirty_ratio: float = 0.05) -> list[dict]:
    """生成 Mock 商品数据

    Args:
        count: 总条数
        dirty_ratio: 脏数据比例 (默认 5%)

    Returns:
        list[dict]: 含 product_id 的唯一商品列表
    """
    results = []
    dirty_count = max(1, int(count * dirty_ratio))
    clean_count = count - dirty_count

    # 生成正常商品 (循环样本 + 随机变体)
    for i in range(clean_count):
        base: dict = random.choice(PRODUCTS)
        _adj: int = random.choice([0, -10, 10, -20, 20])
        results.append({
            "url": f"https://shopify.com/products/{base['brand'].lower()}-{_adj}",
            "product_title": f"{base['title']} ({_adj})",
            "price": base["price"] + _adj,
            "original_price": base["price"] * 2,
            "stock": max(0, base["stock"] + random.randint(-100, 100)),
            "category": base["category"],
            "brand": base["brand"],
            "supplier": random.choice(["广州供应商", "义乌小商品", "深圳代工厂", "杭州电商"]),
            "source": "shopify",
            "domain": "shopify.com",
        })

    # 生成脏数据
    for i in range(dirty_count):
        base = random.choice(DIRTY_RECORDS)
        url_slug = base["title"].replace(" ", "-") or f"dirty-{i}"
        results.append({
            "url": f"https://shopify.com/products/{url_slug}-{i}",
            "product_title": base["title"],
            "price": base["price"],
            "original_price": base["price"] * 3 if base["price"] > 0 else -150,
            "stock": base["stock"],
            "category": base["category"],
            "brand": base.get("brand", "") or "",
            "supplier": "",
            "source": "shopify",
            "domain": "shopify.com",
        })

    random.shuffle(results)
    return results


def fetch_all(limit: int = 100) -> list[dict]:
    """模拟 Shopify API 全量采集"""
    from pulse.contracts.retail import ProductContract, product_to_ods

    raw = _generate(count=limit)
    logger.info(f"Shopify Mock: {len(raw)} 条 (含 {max(1, int(limit*0.05))} 条脏数据)")

    # 先过 Contract 校验, 失败进 DLQ, 通过返回 ODS-compatible dict
    passed = []
    failed = 0
    for item in raw:
        try:
            ProductContract(**item)
            passed.append(product_to_ods(item))
        except Exception:
            failed += 1

    logger.info(f"  Passed: {len(passed)}, Failed (→DLQ): {failed}")
    return passed
