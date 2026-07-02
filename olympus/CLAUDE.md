# Olympus VM — Operator Guide for Claude Code

> This file tells the Claude Code instance running **on the Olympus VM** how this
> machine is laid out, how our agents run, and what it may and may not touch.
> Copy this file to the root of the working directory you run `claude` from on
> Olympus (rename to `CLAUDE.md`). Fill in every `TODO(fill-in)` — the more
> accurate this is, the better and safer Claude's actions will be.

## What Olympus is

Olympus is our production/staging Linux VM. It runs our voice/AI **agents**
deployed to **Azure and GCP**. Treat it as a live system: assume something may be
serving real traffic unless proven otherwise. **Never** restart, kill, deploy, or
delete anything without first checking whether it is live (see Guardrails).

- Host: `TODO(fill-in: hostname)`
- OS: `TODO(fill-in: e.g. Ubuntu 22.04 LTS)`
- Cloud: Azure + GCP  ·  Region(s): `TODO(fill-in)`
- Owner / on-call: `TODO(fill-in)`

## Layout (fill these in — they drive everything)

| Thing | Path / value |
|---|---|
| Repo(s) checked out here | `TODO(fill-in: e.g. /opt/agents/python-agents-examples)` |
| Python venv | `TODO(fill-in: e.g. /opt/agents/venv)` |
| `.env` / secrets file | `TODO(fill-in: e.g. /opt/agents/.env — DO NOT print its contents)` |
| Log directory | `TODO(fill-in: e.g. /var/log/agents/)` |
| How agents run | `TODO(fill-in: systemd units? docker compose? pm2? tmux?)` |
| Deploy method | `TODO(fill-in: git pull + restart? CI? script?)` |

## The agents running on this box

List each long-running agent so Claude knows what "healthy" means. Example rows —
replace with reality:

| Agent / service | Runs as | Health signal | Restart command |
|---|---|---|---|
| `TODO agent-1` | `systemd: agent-1.service` | process up + LiveKit room joins | `sudo systemctl restart agent-1` |
| `TODO agent-2` | `docker: agent2` | HTTP 200 on `:PORT/health` | `docker restart agent2` |

Our agents are built on **LiveKit Agents** (`livekit-agents` Python SDK). A worker
is typically started with `python <path>/agent.py dev` (or `start` in prod) and
connects out to LiveKit + provider APIs (OpenAI, Deepgram, Cartesia, Anthropic,
ElevenLabs, etc.). Required env at minimum: `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
`LIVEKIT_API_SECRET`, plus per-provider keys.

## Standard operating commands

```bash
# Activate the environment before running anything Python
source TODO_VENV_PATH/bin/activate

# Health check (see olympus/scripts/olympus-health.sh)
bash olympus/scripts/olympus-health.sh

# Smoke test the agents (see olympus/scripts/smoke-test.sh)
bash olympus/scripts/smoke-test.sh

# Tail logs
journalctl -u TODO_SERVICE -n 200 --no-pager      # systemd
docker logs --tail 200 TODO_CONTAINER             # docker
```

## Guardrails — read before acting

**Always allowed (read-only, safe):**
- Reading files, logs, `git status`/`git log`/`git diff`
- Running the health-check and smoke-test scripts
- `systemctl status`, `docker ps`, `top`, `df -h`, `free -m`, `nvidia-smi`

**Ask a human first (mutating / disruptive):**
- Restarting, stopping, or deploying **any** agent that might be serving traffic
- Editing `.env`, secrets, systemd units, docker-compose, cron, firewall
- `git push`, `git reset --hard`, force operations, deleting files
- Anything touching Azure/GCP resources (`az`, `gcloud`) that changes state

**Never:**
- Print, echo, or commit secrets / API keys / `.env` contents
- Run destructive commands (`rm -rf`, disk/format ops, mass `kill`) unprompted
- Disable TLS verification, security tooling, or auth
- Deploy straight to prod without a smoke test passing first

## How to hand results back
When a task finishes, report: what changed, what you ran to verify, and anything
you deliberately did **not** touch because it needed sign-off. If you edited code,
show the diff and the verification output rather than saying "done."

---
*Keep this file current — every wrong or missing detail above is a way for an
automated task to do the wrong thing on a live box.*
