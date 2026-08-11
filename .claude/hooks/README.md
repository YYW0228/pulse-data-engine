# Hooks (吞噬 Anthropic cwc-long-running-agents, Apache-2.0)

确定性拦截点 — 放"不能出错"的逻辑; LLM 判断放 evaluator/skills。

| Hook | 事件 | 作用 |
|---|---|---|
| kill-switch.sh | PreToolUse | `touch AGENT_STOP` 暂停 agent / `rm` 恢复 |
| steer.sh | PreToolUse | `echo "指令" > STEER.md` 中途转向 |
| verify-gate.sh | PostToolUse | Default-FAIL: 无证据 Read → 禁止改 results 文件 |
| track-read.sh | PostToolUse | 记录已 Read 的证据文件 (供 verify-gate) |
| commit-on-stop.sh | Stop | 会话结束自动 git commit (tracked 文件) |
| evaluator.md | agent | 怀疑式独立评审 (PASS/NEEDS_WORK) |

用法:
  touch AGENT_STOP              # 暂停 agent
  rm AGENT_STOP                 # 恢复
  echo "先修测试" > STEER.md     # 转向
  RESULTS_FILE=feature_list.json verify-gate  # 证据门接 feature_list
