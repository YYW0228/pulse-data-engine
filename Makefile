# Pulse Data Engine — Makefile
#
# 用法:
#   make test       # 运行测试 + lint
#   make ci         # CI 门禁全量检查
#   make run        # 单次运行管道
#   make deploy     # 生产部署 (GitHub Actions dispatch)
#   make up         # 启动全部服务
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

# ── 服务 ──────────────────────────────────────────────────────────
serve-dashboard:
	$(UV) streamlit run serve.py

serve-wasm:
	$(UV) python -m pulse.wasm_server

serve-metrics:
	$(UV) python -m pulse.metrics_server

# ── Dagster 编排 ─────────────────────────────────────────────────────
dagster-ui:
	$(UV) dagster dev -f pulse/assets.py

dagster-daemon:
	export DAGSTER_HOME=$${DAGSTER_HOME:-/root/.dagster} && \
	mkdir -p $$DAGSTER_HOME && \
	$(UV) dagster-daemon run -w workspace.yaml

dagster-schedule-start:
	export DAGSTER_HOME=$${DAGSTER_HOME:-/root/.dagster} && \
	$(UV) dagster schedule start pulse_etl_schedule -f pulse/assets.py

dagster-run:
	export DAGSTER_HOME=$${DAGSTER_HOME:-/root/.dagster} && \
	$(UV) dagster job execute -f pulse/assets.py -j pulse_etl_job

# ── 全量部署 (所有服务 + 调度) ───────────────────────────────────────
up:
	@echo "Starting all services..."
	$(UV) python -m pulse.metrics_server &
	$(UV) python -m pulse.wasm_server &
	$(UV) streamlit run serve.py &
	$(UV) dagster-daemon run -w workspace.yaml &
	$(UV) python -m scripts.telegram_poller &
	@echo "  📊 Metrics:   http://localhost:9464/metrics"
	@echo "  🦆 WASM SQL:  http://localhost:8000/wasm"
	@echo "  🚀 Dashboard: http://localhost:8501"
	@echo "  🎬 Dagster:   http://localhost:3000 (dagster dev)"
	@echo "  📨 Telegram:  data/telegram_inbox.jsonl"

# ── 停服务 ────────────────────────────────────────────────────────────
down:
	-pkill -f pulse.metrics_server 2>/dev/null
	-pkill -f pulse.wasm_server 2>/dev/null
	-pkill -f streamlit 2>/dev/null
	-pkill -f dagster-daemon 2>/dev/null
	@echo "Services stopped"

# ── 清理 ────────────────────────────────────────────────────────────
clean:
	rm -rf data/backups/*.gz
	rm -rf data/logs/*.jsonl
	rm -rf data/ods_parquet/year=*/
	rm -rf __pycache__ .pytest_cache pulse/__pycache__
	find . -name '*.pyc' -delete
	@echo "清理完成 (数据保留: data/jobs.duckdb)"
