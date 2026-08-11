# AGENTS.md — Pulse Data Engine 工作区规范

本文件注入所有在 pulse-data-engine 目录运行的 agent 会话。

## 仓库定位

主数据/合规引擎:采集→ODS(SCD2)→DWD→DWS 三层仓 + 8502 合规问答 + 情报管道。
透析评分 9.3/10 (模范仓, 保持)。

## 核心命令 (uv 管理)

```bash
uv run pytest tests/ -q                    # 全量测试 (144+)
uv run pytest tests/test_xxx.py -q         # 单模块
uv run ruff check .                        # lint (push 前必过)
uv run python scripts/vas_goal.py --repo . --goal "..."   # VAS 目标驱动改进
```

## 提交规范

- gate 顺序: ruff → pytest → push (CI 强制)
- 不提交: .venv/ data/*.duckdb __pycache__/ *.pyc
- 测试不得用生产默认 DB 路径 — 显式传临时路径 (DuckDB 锁冲突)
- 生产服务 (8501/8502) venv 是 launchd 托管的, 不要 rm -rf 重建

## 关键约束

- 常驻服务由 launchd 托管 (8502 合规问答生产)
- DAG/duckdb 一致性: workspace_consistency 枚举 (exclusive-lock 默认)
- 吞噬模式落地走 VAS 驱动 (每轮暴露一个工具缺陷并修复 = 正循环)
