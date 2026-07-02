#!/usr/bin/env bash
#
# SessionStart hook for the Claude Code running ON Olympus.
#
# Wire it up in the working dir's .claude/settings.json:
#
#   {
#     "hooks": {
#       "SessionStart": [
#         { "hooks": [ { "type": "command",
#                        "command": "bash olympus/hooks/session-start.sh" } ] }
#       ]
#     }
#   }
#
# It prints a compact status banner so every Claude session on the VM starts
# already knowing whether the box is healthy. Keep it fast and read-only.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

echo "=== Olympus session start ==="
echo "host: $(hostname)   date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "load:$(awk '{print $1,$2,$3}' /proc/loadavg 2>/dev/null)  cores:$(nproc 2>/dev/null)"
df -hP / 2>/dev/null | awk 'NR==2{print "disk /:",$5,"used"}'
free -m 2>/dev/null | awk '/^Mem:/{printf "mem: %d/%d MB used\n",$3,$2}'

# Run the health check quietly; surface only problems to the session context.
if [[ -x olympus/scripts/olympus-health.sh ]]; then
  if ! bash olympus/scripts/olympus-health.sh --quiet; then
    echo "!! health check reported FAILURES — investigate before mutating anything"
  else
    echo "health: all checks passed"
  fi
fi
echo "Reminder: this is a live VM. Follow the guardrails in CLAUDE.md."
echo "============================="
exit 0
