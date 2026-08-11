#!/usr/bin/env bash
# verify-gate.sh — Default-FAIL 证据门: 无证据 Read → 禁止修改 results 文件 (吞噬 Anthropic)
# 证据: agent 必须先 Read 截图/日志 (track-read.sh 记录), 才能标记 feature 通过
# 适配: RESULTS_FILE 可配 (默认 test-results.json / feature_list.json)
# License: Apache-2.0 (Anthropic PBC, 吞噬适配)
log="${VERIFY_READ_LOG:-./.claude/.evidence-reads}"
results="${RESULTS_FILE:-feature_list.json}"

input=$(cat)
target=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)

# 只守卫 results 文件
case "$target" in "$results"|*/"$results") ;; *) exit 0 ;; esac

if [ ! -s "$log" ]; then
  cat <<'JSON'
{"decision":"block","reason":"Cannot modify the results file: no screenshot or console-log evidence has been Read this session. Open the evidence file with the Read tool first, then retry."}
JSON
  exit 2
fi
# 消费证据: 下一次修改需新证据
: > "$log"
exit 0
