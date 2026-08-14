# 吞噬借鉴证据 (ADOPTION EVIDENCE)

> 2026-08-11 | 来源: chekusu/wanman (Apache-2.0) + chekusu/sandbank (无 License, 只借鉴思路)
> 方法: harness-devour 5 阶段吞噬 (评分: wanman 23/30, sandbank 100.0, 文档资产 85.0)
> 全仓库证据链: 本文件在所有 YYW0228 仓库同步 (本地 + GitHub)
> 模式库: harness-devour/patterns/ (24 模式) | 索引: hermes-brain/skills/autonomous-ai-agents/harness-devour/references/

## pulse-data-engine

直接借鉴 (2026-08-11):
- OpLog 审计 (chekusu/sandbank AgentOp): pulse/agent_bus.py oplog()/export_oplog() + boom 采集接入 + 4 tests (f4d04d8)
- AgentBus (chekusu/wanman supervisor → 文件总线): 消息/产物/上下文/审计一体 (4a88e44)
- finops 成本核算 (chekusu/wanman finops → Python 移植): boom --finops 成本报告 (4a88e44)


## deepseek-ai/deepseek-harness (MIT, 2026-08-14)

直接借鉴 (migrated):
- Model-visible = Logged: pulse/llm_audit.py + scripts/audit_reconstruct.py
  + tests (185 passed) — 7 调用点全覆盖/熔断/压缩审计/孤儿检测/归档
- 防回退 CI 门禁: tests/test_llm_audit_coverage.py (裸 LLM 调用/未审计压缩 = 测试红)
- 验证: 真实链路 100% 可重建率, 0 失败 (2026-08-14)

- 全量测试: pulse-data-engine 143 passed
- 服务: 8501/8502 HTTP 200
- 克隆源已清理 (本地无残留)
