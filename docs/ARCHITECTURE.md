# 架构设计 — Pulse Data Engine

## 为什么是这个设计？

### 问题 1：为什么用 DuckDB 而不是 PostgreSQL/Snowflake？

**对标方案对比**：

| 维度 | DuckDB | PostgreSQL | Snowflake |
|------|--------|-----------|-----------|
| 成本 | $0 | $0 (自建) | $200-1000/月 |
| 无服务器 | ✅ WASM 浏览器直查 | ❌ 需服务器 | ✅ 但贵 |
| 列式压缩 | ✅ 20:1 | ❌ 行式 | ✅ |
| 单机性能 | ⚡ 百万行/秒 | 一般 | 取决于配置 |
| 学习曲线 | ⭐ 易 | ⭐⭐⭐ | ⭐⭐⭐ |

**结论**: 对于 <100GB + 分析型工作负载，DuckDB 是压倒性最优选择。

### 问题 2：为什么需要 SCD Type 2？

招聘数据是时间序列数据：

- 岗位薪资会涨跌 (25k→30k)
- 技能要求会变化 (Python→Python+AI)
- 公司状态会改变 (招聘中→已关闭)

不追踪历史 = 无法回答：

- "AI 工程师薪资过去 6 个月涨了多少？"
- "哪些技能需求在增长？"

**SCD Type 2** = 每次数据变化产生一个新版本，保留完整审计日志。

```
实体 (url) ──→ entity_id (md5 稳定指纹)
                  │
          ┌───────┴───────┐
          ▼               ▼
    内容未变          内容改变
    (content_hash=)   (content_hash≠)
          │               │
          ▼               ▼
    UPDATE            UPDATE 旧: is_latest=FALSE
    crawled_at        INSERT 新: is_latest=TRUE
                      (保留历史版本)
```

### 问题 3：为什么分离 ODS/DWD/DWS 三层？

这是 **Medallion Architecture** (Databricks 提出的标准数仓模式)。

```
ODS (操作数据存储)
├── 原始数据直接入库 (最小清洗)
├── 保留所有字段 (包括脏数据)
├── 作用: 数据溯源 + 审计
├── 行数: 1075
└── 不可修改 (append-only)
       │
       ▼  ETL (清洗 + 分类 + 过滤)
       │
DWD (数据仓库明细)
├── 类型校验 + 空值处理
├── SCD Type 2 版本过滤 (is_latest=TRUE)
├── 8 分类 (AI/ML 算法 / 后端 / 数据工程...)
├── 行数: 1075 (ODS - DLQ)
└── 作用: 分析基础
       │
       ▼  Aggregation (GROUP BY + percentile)
       │
DWS (数据仓库汇总)
├── 预计算薪资百分位 (p25/p50/p75)
├── 按城市 + 职位分类聚合
├── 行数: 7 技能 + 12 城市
└── 作用: BI 仪表板 / API 响应
```

**不分层的后果**: 查询薪资中位数需要全表扫描 + 实时计算，每次 DAG 运行需要重复清洗。

---

## 关键设计决策

### 1. 双哈希幂等合并

```python
entity_id = md5(url)                    # 实体指纹, 稳定不变
content_hash = md5(title|salary|city)   # 内容指纹, 只对业务变化敏感
```

| 场景 | 行为 | 结果 |
|------|------|------|
| 新实体 | INSERT | 1 条新行 |
| 内容未变 | UPDATE crawled_at | 0 新行, 标记活跃 |
| 内容改变 | UPDATE 旧 + INSERT 新 | 2 行, is_latest 区分 |

**防止存储爆炸**: content_hash 基于业务内容，不是时间戳。同一个岗位连续 30 天不变 → 只有 1 行。

### 2. Data Contracts (数据契约)

Pydantic 在数据进入 ODS 前执行 6 项校验：

| 校验 | 规则 | 拒绝示例 |
|------|------|---------|
| 非空 | title min_length=1 | job_title="" |
| 类型 | salary_min_k=Integer | salary_min_k="25k"→自动转换 ✅ |
| 范围 | 0 <= salary <= 1000 (单位 k) | salary_min_k=25000→归一化为 25 |
| 一致性 | max >= min | min=50, max=30 |
| 格式 | URL 长度 >= 5 | url="abc" |
| 经验 | 枚举匹配 | 应届/1-3年/3-5年/5-10年/10年以上 |

### 3. DAG 编排 vs Airflow

为什么不用 Airflow？

| 维度 | Pulse DAG (200 行) | Airflow |
|------|-------------------|---------|
| 依赖 | 0 (纯 Python) | PostgreSQL + Redis |
| 部署 | import 即用 | 需要 scheduler + webserver |
| 重试 | 内建指数退避 | 需额外配置 |
| 状态 | DuckDB dag_runs | PostgreSQL |
| 重量 | 200 行 | 50MB+ |

**结论**: 对于单机、6 个任务的场景，200 行自定义 DAG 远优于 Airflow 的重型架构。

### 4. 零成本交付链路

```
热数据: DuckDB (内存向量化引擎)
  → 冷数据: Parquet 文件 (Hive 分区)
  → 对象存储: Cloudflare R2 (免费 10GB)
  → 查询引擎: DuckDB WASM (浏览器内, 零服务器)
  → 代理: Cloudflare Worker (CORS + Range, 免费 100k 请求/天)
```

每层都是免费层。月运营费 = $0。

---

## 数据流 (Data Flow)

```
                        ┌──────────────────┐
                        │  Remotive API     │
                        │  296 条/批        │
                        └────────┬─────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  fetch_validate (DAG Task 1)                     │
  │  ├── fetch_all() → 296 条                        │
  │  ├── validate_and_route()                        │
  │  │   ├── 280 pass → merge_into_ods (SCD Type 2) │
  │  │   └── 16 fail → write_dlq (SCHEMA_VIOLATION) │
  │  └── verify() → 对账 True/False                   │
  └─────────────────────────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  transform_dwd (DAG Task 2)                     │
  │  ├── 读取 ODS (is_latest=TRUE)                  │
  │  ├── 类型转换 + 空值过滤                         │
  │  ├── 正则分类 (8 优先级)                          │
  │  └── 写入 dwd_cleaned_jobs                       │
  └─────────────────────────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  aggregate_dws (DAG Task 3)                     │
  │  ├── GROUP BY category: COUNT, AVG, percentile  │
  │  ├── GROUP BY city: COUNT, AVG                  │
  │  └── verify(): DWS + excluded == DWD == ODS      │
  └─────────────────────────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  export_parquet (DAG Task 4)                    │
  │  └── COPY ... PARTITION BY (year, month, date)  │
  │      → data/ods_parquet/year=2026/month=7/      │
  └─────────────────────────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  quality_check (DAG Task 5)                     │
  │  └── SLA 4 维: 完整性/有效性/新鲜度/一致性        │
  │      → CRITICAL → Slack/Email 告警               │
  └─────────────────────────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────┐
  │  backup (DAG Task 6)                            │
  │  ├── gzip: 14MB → 1.3MB (9%)                    │
  │  └── R2: backups/pulse/jobs_.duckdb.gz           │
  └─────────────────────────────────────────────────┘
```

---

## 监控与运维

### 质量 SLA (4 维度)

| 维度 | 阈值 | 异常处理 |
|------|------|---------|
| 完整性 | 空值率 < 5% | CRITICAL → 告警 |
| 有效性 | 无效薪资 < 10% | CRITICAL → 告警 |
| 新鲜度 | 数据 < 24h 未更新 | CRITICAL → 告警 |
| 一致性 | ODS↔DWD >= 95% | CRITICAL → 告警 |

### 备份策略

```
频率: DAG 每次运行后 (每 6h)
本地: data/backups/jobs_*.duckdb.gz
远程: R2 → backups/pulse/jobs_*.duckdb.gz
保留: 最近 7 个
压缩: 14MB → 1.3MB (9%)
恢复: BackupManager.restore("r2://backups/pulse/jobs_...")
```

---

## 性能基线

| 操作 | 耗时 | 吞吐量 |
|------|------|--------|
| Pydantic 单条校验 | 3.5μs | 284,895/s |
| 批量校验 1000 条 | 6.3ms | 159,665/s |
| 正则分类 1000 条 | 10.4ms | 95,857/s |
| 合并 100 条新数据 | 339ms | 2.95/s |
| 合并 1000 条新数据 | 2.94s | 0.34/s |
| 全管道 (100 条) | 454ms | 2.2/s |

---

## 限制

| 限制 | 原因 | 替代方案 |
|------|------|---------|
| 单机 <100GB | DuckDB 不分布式 | Spark / Databricks |
| 纯批处理 | 设计选择 (招聘数据批次) | Kafka + 流处理 |
| 无用户权限 | 单用户场景 | 加 RBAC 层 |
| 无 Web UI | 设计选择 | Streamlit / Grafana |

---

> **架构是权衡的艺术。Pulse Data Engine 为 <100GB、单机、零成本场景做了最优权衡。**
