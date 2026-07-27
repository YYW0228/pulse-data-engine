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
