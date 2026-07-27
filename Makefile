# Pulse Data Engine — Makefile
#
# 用法:
#   make test       # 运行测试 + lint
#   make ci         # CI 门禁全量检查
#   make run        # 单次运行管道
#   make deploy     # 生产部署 (GitHub Actions dispatch)
#   make clean      # 清理数据

SHELL := /bin/bash
UV := uv run

.PHONY: test ci run deploy clean

# ── 测试 + 门禁 ────────────────────────────────────────────────────
test:
	$(UV) ruff check .
	$(UV) mypy pulse/ --strict
	$(UV) pytest tests/ --cov=pulse --cov-fail-under=65 -v

ci: test

# ── 本地运行 ────────────────────────────────────────────────────────
run:
	$(UV) python -m pulse.runner

deploy-run:
	$(UV) python -m scripts.run_production

production-report:
	$(UV) python -m scripts.run_production --report-only

# ── Dashboard + WASM 服务 ──────────────────────────────────────────
serve-dashboard:
	$(UV) streamlit run serve.py

serve-wasm:
	$(UV) python -m pulse.wasm_server

serve-metrics:
	$(UV) python -m pulse.metrics_server

# ── 全量部署 ──────────────────────────────────────────────────────────
up:
	@echo "Starting all services..."
	$(UV) python -m pulse.metrics_server &
	$(UV) python -m pulse.wasm_server &
	$(UV) streamlit run serve.py &
	@echo "Services starting..."
	@sleep 2
	@echo "  📊 Metrics:   http://localhost:9464/metrics"
	@echo "  🦆 WASM SQL:  http://localhost:8000/wasm"
	@echo "  🚀 Dashboard: http://localhost:8501"

# ── Dagster ───────────────────────────────────────────────────────────
dagster-ui:
	$(UV) dagster dev -f pulse/assets.py

dagster-run:
	$(UV) python -c "from dagster import DagsterInstance, materialize; from pulse.assets import *; materialize([ods_raw_jobs, dwd_cleaned_jobs, dws_skill_agg, dws_city_agg, parquet_export, iceberg_export, quality_report, backup], resources={}, instance=DagsterInstance.ephemeral())"

# ── 清理 ────────────────────────────────────────────────────────────
clean:
	rm -rf data/backups/*.gz
	rm -rf data/logs/*.jsonl
	rm -rf data/ods_parquet/year=*/
	rm -rf __pycache__ .pytest_cache pulse/__pycache__
	find . -name '*.pyc' -delete
	@echo "清理完成 (数据保留: data/jobs.duckdb)"
