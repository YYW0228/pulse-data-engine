# 情报简报: privacy-legal
**生成时间**: 2026-06-29 11:05
**状态**: ⚠️ 演示模式 (Reddit API blocked)

---
## 已验证的可行路径
1. `web_extract("reddit.com/r/LocalLLaMA")` → 拿全文摘要
2. `web_search("site:reddit.com/r/LocalLLaMA ...")` → 精准关键词搜索
3. xurl (X API) → 需先完成 OAuth 认证

## 建议
部署 Hermes cron 任务替代本地 Python 脚本，
详见 `scripts/intel-pipeline/README.md`
