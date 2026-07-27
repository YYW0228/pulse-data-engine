# 快速开始 — 5 分钟跑通 Pulse Data Engine

## 前提

- Python 3.10+
- curl 或 git

## 3 步启动

### 1. 获取代码

```bash
git clone https://github.com/YYW0228/pulse-data-engine
cd pulse-data-engine
```

### 2. 安装依赖 (uv)

```bash
# 安装 uv (如未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步依赖 (≈0.88ms, 从锁文件恢复)
uv sync --frozen
```

### 3. 运行

```bash
uv run python -m pulse.runner
```

### 预期输出

```
DAG 'pulse_etl' 启动, 6 任务
  ✅ fetch_validate: 296 条采集, ODS=1075
  ✅ transform_dwd: 1075 行
  ✅ aggregate_dws: 对账一致=True
  ✅ export_parquet: 158 KB
  ✅ quality_check: 完整=PASS 有效=PASS 新鲜=PASS 一致=PASS
  ✅ backup: gzip 1.3MB → R2
结果: 6 成功 / 0 失败 / 0 跳过
```

## 查看数据

```bash
# 查询最新聚合 (DWS)
uv run python -c "
from pulse.pipeline import Pipeline
p = Pipeline()
rows = p.con.execute('SELECT category, demand_count, avg_salary FROM dws_skill_agg ORDER BY demand_count DESC').fetchall()
for r in rows:
    print(f'{r[0]:12s} {r[1]:4d} 岗  ¥{r[2]}k')
p.close()
"
```

## 查看日志

```bash
# 结构化 JSON 日志
cat data/logs/pulse.jsonl | python -m json.tool | head -10
```

## 查看备份

```bash
ls -lh data/backups/
```

## 完整测试

```bash
uv run python -m pytest tests/ -v
```

## 手动作业：修改配置

所有配置在 `pulse/runner.py` DAG 任务中直接可改：

- 数据源: `fetch_all(limit_per_category=5)` → 改数量
- 重试: `@dag.task(max_retries=3)` → 改重试次数
- SLA 阈值: `QualitySLA(null_rate_max=0.1)` → 放宽/收紧

## 下一步

- [架构设计](ARCHITECTURE.md) — 理解设计决策
- 自定义爬虫: 继承 `pulse/extractors/` 模式
- 部署到生产: 设置 cron `every 6h`
