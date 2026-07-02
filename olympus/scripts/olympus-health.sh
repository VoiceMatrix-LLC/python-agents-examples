#!/usr/bin/env bash
#
# olympus-health.sh — health check for the Olympus VM and its agents.
#
# Read-only and safe: it inspects, it never restarts or changes anything.
# Exit code 0 = all checks passed, non-zero = at least one check failed
# (so it works as a cron/monitoring probe or a CI gate).
#
# Configure the CHECK_* variables below for your box, then:
#   bash olympus/scripts/olympus-health.sh
#   bash olympus/scripts/olympus-health.sh --quiet   # only print failures
#
set -uo pipefail

# ---------------------------------------------------------------------------
# CONFIG — edit these for Olympus
# ---------------------------------------------------------------------------
DISK_WARN_PCT=90                 # warn if any mount is over this % full
MEM_WARN_PCT=90                  # warn if memory usage over this %
CHECK_SYSTEMD_UNITS=(            # systemd services that must be "active"
  # "agent-1.service"
  # "agent-2.service"
)
CHECK_DOCKER_CONTAINERS=(        # docker containers that must be "running"
  # "agent2"
)
CHECK_HTTP_ENDPOINTS=(           # URLs that must return 2xx/3xx
  # "http://127.0.0.1:8080/health"
)
CHECK_PROCESSES=(                # process name patterns that must be present
  # "python .*agent.py"
)
CHECK_ENV_FILE=""                # e.g. "/opt/agents/.env" — checked for existence only, never printed
# ---------------------------------------------------------------------------

QUIET=0; [[ "${1:-}" == "--quiet" ]] && QUIET=1
FAILED=0
pass() { [[ $QUIET -eq 1 ]] || printf '  \033[32mOK\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILED=1; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$1"; }
head() { [[ $QUIET -eq 1 ]] || printf '\n\033[1m%s\033[0m\n' "$1"; }

head "System"
UP=$(uptime -p 2>/dev/null || echo "unknown")
pass "uptime: $UP"
LOAD=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "?")
CORES=$(nproc 2>/dev/null || echo 1)
pass "load: $LOAD (cores: $CORES)"

head "Disk"
while read -r pct mount; do
  pct_num=${pct%\%}
  if [[ "$pct_num" =~ ^[0-9]+$ ]] && (( pct_num >= DISK_WARN_PCT )); then
    fail "disk $mount at ${pct} (threshold ${DISK_WARN_PCT}%)"
  else
    pass "disk $mount at ${pct}"
  fi
done < <(df -hP -x tmpfs -x devtmpfs 2>/dev/null | awk 'NR>1{print $5" "$6}')

head "Memory"
read -r total used <<<"$(free -m | awk '/^Mem:/{print $2" "$3}')"
if [[ -n "${total:-}" && "$total" -gt 0 ]]; then
  pct=$(( used * 100 / total ))
  if (( pct >= MEM_WARN_PCT )); then fail "memory ${pct}% used (${used}/${total} MB)"
  else pass "memory ${pct}% used (${used}/${total} MB)"; fi
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  head "GPU"
  if nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null; then
    pass "nvidia-smi responded"
  else
    fail "nvidia-smi present but failed"
  fi
fi

if ((${#CHECK_SYSTEMD_UNITS[@]})); then
  head "systemd units"
  for u in "${CHECK_SYSTEMD_UNITS[@]}"; do
    if systemctl is-active --quiet "$u"; then pass "$u active"
    else fail "$u NOT active ($(systemctl is-active "$u" 2>/dev/null))"; fi
  done
fi

if ((${#CHECK_DOCKER_CONTAINERS[@]})); then
  head "docker containers"
  for c in "${CHECK_DOCKER_CONTAINERS[@]}"; do
    state=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
    if [[ "$state" == "running" ]]; then pass "$c running"
    else fail "$c state=$state"; fi
  done
fi

if ((${#CHECK_PROCESSES[@]})); then
  head "processes"
  for p in "${CHECK_PROCESSES[@]}"; do
    if pgrep -f "$p" >/dev/null 2>&1; then pass "process present: $p"
    else fail "process MISSING: $p"; fi
  done
fi

if ((${#CHECK_HTTP_ENDPOINTS[@]})); then
  head "HTTP endpoints"
  for url in "${CHECK_HTTP_ENDPOINTS[@]}"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url" 2>/dev/null || echo 000)
    if [[ "$code" =~ ^[23] ]]; then pass "$url -> $code"
    else fail "$url -> $code"; fi
  done
fi

if [[ -n "$CHECK_ENV_FILE" ]]; then
  head "Env file"
  if [[ -f "$CHECK_ENV_FILE" ]]; then pass "env file present ($CHECK_ENV_FILE)"
  else fail "env file MISSING ($CHECK_ENV_FILE)"; fi
fi

echo
if (( FAILED )); then
  printf '\033[31m✗ Olympus health: FAILURES detected\033[0m\n'; exit 1
else
  printf '\033[32m✓ Olympus health: all checks passed\033[0m\n'; exit 0
fi
