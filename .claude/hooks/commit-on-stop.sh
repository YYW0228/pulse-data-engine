#!/usr/bin/env bash
# commit-on-stop.sh — 会话结束自动 git commit (吞噬 Anthropic cwc-long-running-agents)
# 只提交 tracked 文件改动 (ephemeral 产物不入库); 无改动则静默
# License: Apache-2.0 (Anthropic PBC, 吞噬适配)
if git rev-parse --git-dir >/dev/null 2>&1; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git commit -am "session checkpoint: $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1
  fi
fi
exit 0
