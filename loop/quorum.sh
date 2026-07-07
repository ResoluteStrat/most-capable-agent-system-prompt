#!/usr/bin/env bash
# Optional pre-gate: 3 cheap models vote on the triage signals; the expensive
# loop only runs when at least 2 of 3 say "actionable".
set -euo pipefail
cd "$(dirname "$0")"
{ git log --oneline -20; gh issue list --limit 20 2>/dev/null || true; \
  gh run list --limit 10 2>/dev/null || true; } > /tmp/signals.txt

V=0
for m in deepseek/deepseek-v4-flash qwen/qwen-3.6 moonshotai/kimi-k2.6; do
  llm -m "openrouter/$m" -s "$(cat triage.md)" < /tmp/signals.txt \
    | grep -q "status: actionable" && V=$((V+1))
done
[ "$V" -ge 2 ] && exec ./loop.sh || echo "quorum: quiet ($V/3)"
