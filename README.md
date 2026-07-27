# pulse-data-engine

独立数据引擎 — ODS/DWD/DWS 三层数仓 + SCD Type 2 + DLQ + Parquet + DuckDB WASM

## 架构

```
输入 → validate_and_route() → [pass] → merge_into_ods (SCD Type 2)
                               [fail] → write_dlq(SCHEMA_VIOLATION)
```

## 快速开始

```bash
# 依赖管理 (uv, 10-100x pip)
uv sync --frozen        # 从锁文件恢复, ~1ms
uv run python -m pulse.runner  # 运行 DAG

# 或单次运行
uv run python -c "from pulse.pipeline import Pipeline; p=Pipeline(); p.run_full()"
```

## DAG 任务

| 任务 | 职责 | 依赖 | 重试 |
|------|------|------|------|
| validate | Pydantic Data Contracts 校验 | — | 2次 |
| merge_ods | SCD Type 2 幂等合并 | validate | 2次 |
| transform_dwd | 清洗+分类 | merge_ods | 2次 |
| aggregate_dws | 预聚合 | transform_dwd | 2次 |
| export_parquet | Parquet 湖导出 | aggregate_dws | 2次 |

## 7x24 无人值守

```bash
# cron job: every 6h
cd /root/projects/pulse-data-engine
uv sync --frozen
uv run python -m pulse.runner
```

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| 包管理 | uv (Rust) | 10-100x pip, 确定性锁文件 |
| 热存储 | DuckDB | SCD Type 2 状态机 |
| 冷存储 | Parquet (Hive分区) | 列式压缩, 172KB→1043行 |
| 数据契约 | Pydantic v2 | Schema 校验, 脏数据拦截 |
| DAG编排 | pulse/dag.py | 轻量级, 状态存 DuckDB |
| 代理服务 | Cloudflare Worker | CORS + Range 请求桥接 |
| 前端查询 | DuckDB WASM | 浏览器 SQL → R2 Parquet |

## 对账

```sql
SELECT * FROM read_parquet('data/ods_parquet/*/*/*/*.parquet');
```
