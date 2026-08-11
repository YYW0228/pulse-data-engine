#!/bin/bash
# init.sh — 环境初始化 + 基础验证 (Anthropic long-running harness 契约)
# 会话开局跑: bash init.sh  (幂等, 可重复执行)
set -e
cd "$(dirname "$0")"

echo "══ pulse-data-engine init ══"

# 1. 环境初始化
if [ ! -d .venv ]; then
  echo "  → 创建 venv + 安装依赖 (uv)"
  uv venv --python 3.11 .venv
  uv sync --frozen 2>/dev/null || uv pip install --python .venv/bin/python -e ".[dev]" 2>/dev/null || uv pip install --python .venv/bin/python pytest
fi
export PATH="$PWD/.venv/bin:$PATH"


# 2. 基础验证
.venv/bin/python -m pytest -q --no-cov 2>/dev/null | tail -1 || echo "  (无 pytest 或测试未就绪)"


echo "✅ pulse-data-engine ready (git: $(git log --oneline -1 2>/dev/null | cut -c1-50))"
