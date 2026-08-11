#!/usr/bin/env bash
# track-read.sh — 记录 agent 已 Read 的证据文件 (吞噬 Anthropic cwc-long-running-agents)
# verify-gate.sh 凭此列表放行 results 文件修改
# License: Apache-2.0 (Anthropic PBC, 吞噬适配)
log="${VERIFY_READ_LOG:-./.claude/.evidence-reads}"
path=$(cat | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
case "$path" in
  *screenshots/*|*-console.txt|*-result.txt|*.png|*evidence*)
    [ -f "$path" ] && echo "$path" >> "$log" ;;
esac
exit 0
