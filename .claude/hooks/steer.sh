#!/usr/bin/env bash
# steer.sh — STEER.md 有内容 → 注入操作员转向指令并清空 (吞噬 Anthropic cwc-long-running-agents)
# 用法: echo "先修测试再继续" > STEER.md  → agent 下一轮工具调用被阻断并注入此指令
# License: Apache-2.0 (Anthropic PBC, 吞噬适配)
f="${AGENT_STEER_FILE:-./STEER.md}"
if [ -s "$f" ]; then
  note=$(cat "$f")
  reason=$(python3 -c 'import json,sys; print(json.dumps("OPERATOR STEERING: " + sys.argv[1] + "\n\nPause what you were about to do, incorporate this guidance, then continue toward the feature goal."))' "$note" 2>/dev/null) || exit 0
  printf '{"decision":"block","reason":%s}\n' "$reason"
  : > "$f"
  exit 2
fi
exit 0
