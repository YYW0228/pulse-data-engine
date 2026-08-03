# 客户接入报告: acme

> 生成时间: 2026-08-03 10:22:17

## 数据概况
| 指标 | 值 |
|------|-----|
| 文档数 | 3 |
| 分块数 | 18 |
| 字符数 | 2,625 |
| 独立库 | data/customers/acme/acme.duckdb |

## 下一步
1. 定义 30-50 道金标验收问题
2. 运行问答验证: `uv run python -m scripts.compliance_qa --query "..."` (需先 set_customer_db)
3. 调整分块/检索参数直到金标命中 ≥80%
