#!/usr/bin/env bash
#
# smoke-test.sh — quick post-deploy sanity checks for the agents on Olympus.
#
# Unlike the health check (which inspects a running system), this verifies the
# code/environment is actually wired up: venv works, deps import, env vars are
# present, and each agent at least starts up without crashing on import.
#
# Safe by default: it does NOT start long-running workers or send real traffic.
# Exit 0 = all good, non-zero = something is broken.
#
#   bash olympus/scripts/smoke-test.sh
#
set -uo pipefail

# ---------------------------------------------------------------------------
# CONFIG — edit for Olympus
# ---------------------------------------------------------------------------
VENV_PATH="TODO_/opt/agents/venv"           # path to the Python venv
REPO_DIR="TODO_/opt/agents/python-agents-examples"  # repo root on the VM
REQUIRED_ENV=(                               # env vars that must be set (values never printed)
  "LIVEKIT_URL"
  "LIVEKIT_API_KEY"
  "LIVEKIT_API_SECRET"
  # "OPENAI_API_KEY"
  # "DEEPGRAM_API_KEY"
)
# Agent entrypoints to import-check (they must parse + import cleanly).
AGENT_ENTRYPOINTS=(
  # "basics/listen_and_respond.py"
  # "complex-agents/medical_office_triage/triage.py"
)
# ---------------------------------------------------------------------------

FAILED=0
pass() { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILED=1; }
head() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head "Environment"
if [[ -d "$VENV_PATH" ]]; then
  # shellcheck disable=SC1091
  source "$VENV_PATH/bin/activate" && pass "activated venv $VENV_PATH"
else
  fail "venv not found at $VENV_PATH"; echo "Fix VENV_PATH and re-run."; exit 1
fi
PYV=$(python --version 2>&1); pass "python: $PYV"

head "Required env vars (presence only — values not printed)"
# Optionally source the repo .env so vars are visible to this check.
[[ -f "$REPO_DIR/.env" ]] && set -a && . "$REPO_DIR/.env" && set +a
for v in "${REQUIRED_ENV[@]}"; do
  if [[ -n "${!v:-}" ]]; then pass "$v is set"
  else fail "$v is NOT set"; fi
done

head "Dependency import check"
python - <<'PY' && pass "core deps import" || fail "core dependency import failed"
import importlib, sys
mods = ["livekit.agents", "dotenv"]
bad = []
for m in mods:
    try: importlib.import_module(m)
    except Exception as e: bad.append(f"{m}: {e}")
if bad:
    print("\n".join(bad)); sys.exit(1)
PY

if ((${#AGENT_ENTRYPOINTS[@]})); then
  head "Agent import/compile check"
  cd "$REPO_DIR" || { fail "cannot cd to $REPO_DIR"; exit 1; }
  for f in "${AGENT_ENTRYPOINTS[@]}"; do
    if [[ ! -f "$f" ]]; then fail "missing file: $f"; continue; fi
    # Byte-compile: catches syntax errors without running the worker.
    if python -m py_compile "$f" 2>/tmp/smoke_err; then pass "compiles: $f"
    else fail "compile error: $f -> $(cat /tmp/smoke_err)"; fi
  done
fi

echo
if (( FAILED )); then
  printf '\033[31m✗ Smoke test FAILED\033[0m\n'; exit 1
else
  printf '\033[32m✓ Smoke test passed\033[0m\n'; exit 0
fi
