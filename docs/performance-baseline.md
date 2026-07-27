# Performance Baseline — pulse-data-engine
# Generated: 2026-07-27
# Run: uv run pytest tests/test_performance.py --benchmark-only

## Throughput

| Test | Mean | OPS | Target | Status |
|------|------|-----|--------|--------|
| Contract validation (single) | 3.5μs | 284,895/s | >1000/s | ✅ |
| Batch validate 1000 | 6.3ms | 159,665/s | >500/s | ✅ |
| Classify 1000 | 10.4ms | 95,857/s | >1000/s | ✅ |
| Merge 100 new | 339ms | 2.95/s | >33/s | ✅ |
| Merge 1000 new | 2.94s | 0.34/s | >0.1/s | ✅ |
| Merge 1000 dup | 1.53s | 0.66/s | >0.2/s | ✅ |
| Full pipeline 100 | 454ms | 2.20/s | >0.1/s | ✅ |

## SLA Targets

| Operation | Target | Current | Headroom |
|-----------|--------|---------|----------|
| Validate (single) | <10μs | 3.5μs | 2.8x |
| Validate (batch 1k) | <10s | 6.3ms | 1587x |
| Merge (100 new) | <3s | 339ms | 8.8x |
| Merge (1000 new) | <10s | 2.94s | 3.4x |
| Full pipeline (100) | <10s | 454ms | 22x |
