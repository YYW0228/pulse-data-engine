#!/usr/bin/env bash
# scripts/rebuild_all.sh — 新机器数据重建 (灾难恢复第 6 步)
# 用法: bash scripts/rebuild_all.sh [--verify]
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 重建数据 (源文档 → 索引) ==="
T0=$(date +%s)

# 0. 准备数据目录 (仓库 clone 后缺失的运行时目录)
mkdir -p data/scene2_intel data/market_knowledge data/customers data/logs

echo "[1/4] 合规知识库 (法规+备案清单)..."
uv run python -m scripts.compliance_index \
  --source /root/projects/china-ai-governance/ai-governance-legal/references \
  --include-jsonl

echo "[2/4] 情报报告 (scene2_intel)..."
if [ -d data/scene2_intel ] && [ "$(ls data/scene2_intel/*.md 2>/dev/null | wc -l)" -gt 0 ]; then
  uv run python -m scripts.compliance_index \
    --source data/scene2_intel --include-jsonl
else
  echo "  ⚠️ scene2_intel 为空 — 需从 DELIVERY_WORKSPACE 同步 (见手册第 5 步)"
fi

echo "[3/4] 市场洞察 (market_knowledge)..."
if [ -d data/market_knowledge ] && [ "$(ls data/market_knowledge/*.md 2>/dev/null | wc -l)" -gt 0 ]; then
  uv run python -m scripts.compliance_index \
    --source data/market_knowledge --include-jsonl
else
  echo "  ⚠️ market_knowledge 为空 — 从 /opt/startalent/market_insight 同步 (CI 产物)"
fi

echo "[4/4] 重建完成, 验证..."
uv run python -c "
import duckdb
con = duckdb.connect('data/compliance.duckdb')
n = con.execute('SELECT COUNT(*) FROM compliance_chunks').fetchone()[0]
print(f'总块数: {n} (预期 483+)')
assert n >= 300, f'重建不完整: {n}'
print('✅ 数据重建验证通过')
con.close()
"

T1=$(date +%s)
echo ""
echo "=== 重建耗时: $((T1 - T0)) 秒 ==="
echo "提示: 客户库/日志等运行时数据按需重建 (customer_onboard / log_rotate)"
