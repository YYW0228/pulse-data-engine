#!/usr/bin/env bash
# scripts/rebuild_all.sh — 新机器数据重建 (灾难恢复第 6 步)
# 用法: bash scripts/rebuild_all.sh [--verify]
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 重建数据 (源文档 → 索引) ==="
T0=$(date +%s)

echo "[1/3] 合规知识库 (246 块)..."
uv run python -m scripts.compliance_index \
  --source /root/projects/china-ai-governance/ai-governance-legal/references \
  --include-jsonl

echo "[2/3] 情报报告 (124 块)..."
uv run python -m scripts.compliance_index \
  --source data/scene2_intel --include-jsonl

echo "[3/3] 重建完成, 验证..."
uv run python -c "
import duckdb
con = duckdb.connect('data/compliance.duckdb')
n = con.execute('SELECT COUNT(*) FROM compliance_chunks').fetchone()[0]
print(f'总块数: {n} (预期 370)')
assert n >= 300, f'重建不完整: {n}'
print('✅ 数据重建验证通过')
con.close()
"

T1=$(date +%s)
echo "=== 重建耗时: $((T1-T0)) 秒 ==="

if [[ "${1:-}" == "--verify" ]]; then
  echo "=== 问答验证 ==="
  uv run python -m scripts.compliance_qa --query "算法备案的要求" | head -5
fi
