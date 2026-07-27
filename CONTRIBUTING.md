# Pulse Data Engine — 贡献指南

## 本地开发

```bash
# 安装 pre-commit hooks
pre-commit install

# 运行测试
uv run pytest -v

# 检查代码质量
uv run ruff check .
uv run mypy pulse/ --strict

# 修复自动可修复项
uv run ruff check --fix .
```

## Pull Request Checklist

提交 PR 前逐项确认：

- [ ] `ruff check .` — 0 errors
- [ ] `mypy pulse/ --strict` — 0 errors
- [ ] `pytest --cov=pulse --cov-fail-under=65` — 全部通过，覆盖率不下降
- [ ] 新功能包含对应 **metrics 埋点**（`pulse/metrics.py` 注册新指标）
- [ ] 新 metrics 有对应单元测试（`tests/test_metrics.py`）
- [ ] Alerting 规则评估：新功能是否影响 DLQ / success rate / duration？若是，更新 `scripts/alert_check.py` 或 Grafana dashboard
- [ ] README / docs 更新（如果有新增配置、命令、环境变量）
- [ ] `make deploy-run --dev` 验证端到端
- [ ] AI 生成代码部分已进行 human review（架构一致性、边缘 case、安全性）
- [ ] Secrets/credentials 未 hardcode（使用 GitHub Secrets 或 `.env`）

## 指标命名规范

```
pulse.{layer}.{entity}.{metric_type}

示例:
  pulse.dag.task.duration_seconds      — DAG task 耗时
  pulse.pipeline.ods_rows              — ODS 数据量
  pulse.fetch.http.total               — HTTP 请求计数
  pulse.r2.upload.bytes_total          — R2 上传字节量
```

新增指标前检查是否已有同名指标，避免重复注册。

## CI 门禁

代码 push / PR 时自动运行（`.github/workflows/ci.yml`）：

1. `ruff check .` — 代码风格
2. `mypy pulse/ --strict` — 类型安全
3. `pytest --cov=pulse --cov-fail-under=65` — 功能正确 + 覆盖率
4. `gitleaks` — Secret 扫描

任何一步失败 → 合并不通过。
