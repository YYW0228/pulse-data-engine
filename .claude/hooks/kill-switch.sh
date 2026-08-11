#!/usr/bin/env bash
# kill-switch.sh — 存在 AGENT_STOP 文件 → 阻断所有工具调用 (吞噬 Anthropic cwc-long-running-agents)
# 用法: touch AGENT_STOP 暂停 / rm AGENT_STOP 恢复
# 接入: Hermes PreToolUse hook 或手动执行
# License: Apache-2.0 (Anthropic PBC, 吞噬适配)
if [ -e "${AGENT_STOP_FILE:-./AGENT_STOP}" ]; then
  cat <<'JSON'
{"decision":"block","reason":"Kill switch engaged: AGENT_STOP file exists. Agent is halted. Remove the file to resume."}
JSON
  exit 2
fi
exit 0
