# 🚀 Pulse Data Engine

> **零成本数据湖** — 从爬虫到可视化，一条管道，月运营费 **$0**

独立数据引擎 | ODS/DWD/DWS 三层数仓 | SCD Type 2 | DLQ 死信队列 | Parquet 冷存储 | DuckDB WASM 浏览器 SQL 直查

---

## 为什么你需要它？

### 对标对比

| 方案 | 设置时间 | 月成本 | 学习曲线 | 无服务器 |
|------|---------|--------|---------|---------|
| **Pulse（推荐）** | **5 min** | **$0** | **⭐⭐ 易** | **✅ 完全** |
| Airflow | 2 天 | $100-500 | ⭐⭐⭐⭐ 难 | ❌ 需服务器 |
| Databricks | 1 天 | $200-1000 | ⭐⭐⭐ 中 | ✅ |
| dbt Cloud | 1 天 | $100+ | ⭐⭐⭐ 中 | ✅ |

**关键数字**: 3 年省下 **$36,000** vs Databricks

---

## 快速开始（3 步，5 分钟）

```bash
# 1. 克隆
git clone https://github.com/YYW0228/pulse-data-engine
cd pulse-data-engine

# 2. 装依赖 (uv, 比 pip 快 100x)
uv sync --frozen

# 3. 运行
uv run python -m pulse.runner
```

预期输出:

```
采集: 296 条 (Remotive, 8 分类)
校验: 280 通过 / 16 失败 (→DLQ)
ODS: 1075 条 (SCD Type 2)
DWD: 1075 行 (清洗+分类)
DWS: 对账一致=True, DLQ=172
Parquet: 158 KB → R2 备份 ✅
```

---

## 架构一图胜千言

```
┌─ 数据源 ─────────────────────┐
│ Remotive API (免费, 无需 key) │
│ BOSS直聘 (待 cookies 激活)     │
└──────────┬─────────────────────┘
           ▼
┌─ Data Contracts (Pydantic) ──┐
│ ✅ 280 通过 → ODS              │
│ ❌ 16 拒绝 → DLQ (隔离)        │
└──────────┬─────────────────────┘
           ▼
┌─ 三层数仓 ────────────────────┐  ← Medallion Architecture
│ ODS:  1075 原始 (SCD Type 2)  │
│ DWD:  1075 清洗 (8 分类)      │
│ DWS:  7 聚合 (薪资 percentile) │
└──────────┬─────────────────────┘
           ▼
┌─ 输出 ────────────────────────┐
│ 📊 Parquet 湖 → R2 (零成本)   │
│ 📋 JSON 日志 → ELK 可聚合     │
│ 💾 gzip 备份 → R2 远程 (9%)   │
│ 🦆 DuckDB WASM → 浏览器 SQL   │
└───────────────────────────────┘
```

---

## 关键特性

| 特性 | 实现 | 价值 |
|------|------|------|
| **SCD Type 2** | 双哈希幂等 (entity_id + content_hash) | 薪资历史可回溯, 版本不膨胀 |
| **Data Contracts** | Pydantic v2, 薪资归一化 (25k→25) | 脏数据在入口被拦截 |
| **DLQ 死信队列** | SCHEMA_VIOLATION 自动隔离 | 管道永不崩溃 |
| **DAG 编排** | 轻量级, 拓扑排序, 自动重试 | 7x24 无人值守 |
| **质量 SLA** | 4 维检查 (完整/有效/新鲜/一致) | 数据问题 5 分钟内告警 |
| **零成本** | DuckDB + uv + R2 + WASM | 月运营费 $0 |
| **备份恢复** | gzip + R2, 保留 7 天, 9% 压缩比 | 灾难恢复 < 1min |

---

## 适用场景

| 场景 | 适合 | 不适合 |
|------|------|--------|
| 初创公司 (无预算) | ✅ 零成本数据基础设施 | ❌ |
| 数据分析师 (快速原型) | ✅ 5 分钟从 0 到数据管道 | ❌ |
| 高校教学 (开源教材) | ✅ 完整数据工程教学案例 | ❌ |
| 企业 PoC 验证 | ✅ 3 天验证数据方案 | ❌ |
| 超大规模 (>100GB) | ❌ DuckDB 单机瓶颈 | ✅ Spark/Databricks |

---

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| 包管理 | **uv** (Rust) | pip 的 100x 速度, 确定性锁文件 |
| 热存储 | **DuckDB** | 列式 OLAP, SCD Type 2 状态机 |
| 冷存储 | **Parquet** (Hive 分区) | 20:1 压缩率, 谓词下推 |
| 校验 | **Pydantic** v2 | 类型安全, 自动文档生成 |
| 编排 | **pulse/dag.py** | 200 行轻量 DAG, 无需外部依赖 |
| 交付 | **Cloudflare R2** + **Worker** | 零成本对象存储, CORS 代理 |
| 查询 | **DuckDB WASM** | 浏览器 SQL 直查 R2 Parquet |

---

## 数字

```
34 测试 (100% 通过)    6 任务 DAG (每 6h)    6 个 commit 作者
$0 月运营              1075 岗位数据          158 KB Parquet 湖
27μs 单条校验          2.94s 合并 1000 条    9% 备份压缩比
```

---

**pulse-data-engine** — 从爬虫到可视化，一条管道，月运营费 $0。

> **架构迁移说明**: `pulse/dag.py` 中的手写 DAG 已标记为 deprecated。
> 所有新逻辑应使用 `pulse/assets.py`（Dagster 资产定义）。
> 详见 [编排架构](pulse/assets.py)。

---

---

## 生产部署

### 1. 配置 Secrets

在 GitHub 仓库 `Settings → Secrets and variables → Actions` 设置：

| Secret | 说明 | 获取方式 |
|--------|------|---------|
| `CF_ACCOUNT_ID` | Cloudflare 账户 ID | Dashboard → 右侧 "Account ID" |
| `CLOUDFLARE_API_TOKEN` | R2 读写权限 Token | R2 → 管理 → 创建 API 令牌 |
| `SLACK_WEBHOOK_URL` | Slack 通知 (可选) | Slack App → Incoming Webhooks |

本地开发用 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 填入真实值
```

### 2. 定时调度

Push 到 `main` 后自动激活 GitHub Actions cron（`daily-pipeline.yml`）：

- **定时执行**: 每天 02:00, 08:00, 14:00, 20:00 UTC
- **手动触发**: Actions → Daily Pipeline → Run workflow
- **失败通知**: Slack webhook（如果配置了 `SLACK_WEBHOOK_URL`）
- **Artifacts**: 每次运行结果保留 7 天（JSON report + 日志）

### 3. 本地一键部署

```bash
make deploy-run        # 单次生产运行 (含 metrics + report)
make production-report # 仅查看最新报告 (不运行管道)
make up                # 启动全部服务:
                       #   :9464 — Metrics  (Prometheus scrape)
                       #   :8000  — WASM SQL (浏览器直查 Parquet)
                       #   :8501  — Dashboard (Streamlit 数据对账)
```

### 4. 查看 Metrics

Metrics 服务器运行在 `:9464`：

| 端点 | 说明 |
|------|------|
| `GET /metrics` | Prometheus 格式 (scrape target) |
| `GET /snapshot` | 最新运行快照 (JSON) |
| `GET /health` | 服务健康 + 最近运行时间 |

```bash
# 直接查看
curl http://localhost:9464/metrics | grep pulse_

# 或配置 Prometheus scrape
# scrape_configs:
#   - job_name: 'pulse'
#     static_configs:
#       - targets: ['localhost:9464']
```

### 5. Grafana Dashboard

导入 `grafana/dashboard.json` 到 Grafana，包含 6 个面板：

- DAG 任务耗时 (P95)
- 任务成功率
- DLQ 行数 + 按错误类型
- ODS/DWD 数据量
- DAG 运行耗时趋势

### 6. Alerting

内置 Python 告警扫描脚本：

```bash
# 手动扫描最新 snapshot
uv run python -m scripts.alert_check

# 自定义阈值
uv run python -m scripts.alert_check \
  --dlq-spike 100 \
  --p95-duration 30.0 \
  --min-success-rate 0.85
```

触发条件自动发 Slack。进阶用户可配置 Prometheus Alertmanager。

### 7. 常见问题

**DLQ 持续增长** — 检查 `data/logs/pulse.jsonl` 中 `SCHEMA_VIOLATION` 的原始记录，调整 `pulse/schema.py` 中 Data Contract 的容错规则。

**R2 同步失败** — 确认 `CF_ACCOUNT_ID` 和 `CLOUDFLARE_API_TOKEN` 已设置且对应 R2 bucket 名称匹配。

**WASM 查询为空** — 先运行一次管道生成 Parquet 数据，确认 `data/ods_parquet/` 非空。

**Metrics 全部为 0** — Metrics 定义在进程启动时注册，实际值在管道运行后填充。确保先跑 `make deploy-run` 再查 `/metrics`。

---

> **架构是权衡的艺术。Pulse Data Engine 为 <100GB、单机、零成本场景做了最优权衡。**
