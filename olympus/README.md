# Olympus Kit — driving Claude Code on your Olympus VM

This folder is a starter kit for using the **Claude Code (Max plan)** that's
installed **on your Olympus Linux VM** to check health, smoke test, review/debug,
and develop features on that box.

Important: the Claude session that generated this kit runs in a sandboxed cloud
container scoped to this GitHub repo and **cannot reach Olympus**. The agent that
*can* act on Olympus is the `claude` installed there. This kit is the material you
put on Olympus so that agent works well and safely.

## Contents

| File | What it's for |
|---|---|
| `CLAUDE.md` | Operator guide for the Olympus Claude — VM layout, agents, guardrails. **Copy to your working-dir root on Olympus and fill in the `TODO`s.** |
| `scripts/olympus-health.sh` | Read-only health probe (disk, mem, load, GPU, services, endpoints). Exit 0/1 — cron- and CI-friendly. |
| `scripts/smoke-test.sh` | Post-deploy sanity: venv, deps import, env vars present, agents compile. |
| `hooks/session-start.sh` | SessionStart hook so every Claude session on the VM opens with a health banner. |
| `PROMPTS.md` | Ready-to-paste task prompts (health, smoke, debug, review, feature, restart). |

## Get it onto Olympus

If Olympus already checks out this repo, just pull and you have it:

```bash
# on Olympus, in the repo
git fetch origin claude/olympus-vm-review-gjawjd
git checkout claude/olympus-vm-review-gjawjd   # or merge/cherry-pick the olympus/ dir
chmod +x olympus/scripts/*.sh olympus/hooks/*.sh
cp olympus/CLAUDE.md ./CLAUDE.md               # then edit the TODOs
```

Then edit `CLAUDE.md` and the CONFIG blocks in the two scripts to match your box.

## Three ways to actually drive it

### 1. SSH + terminal (simplest, works today)
```bash
ssh you@olympus
cd /path/to/working-dir
claude            # then paste a prompt from PROMPTS.md
```

### 2. Automate recurring checks with cron
```bash
# health probe every 15 min; log failures
*/15 * * * * cd /path/to/repo && bash olympus/scripts/olympus-health.sh --quiet >> /var/log/olympus-health.log 2>&1
```
(For alerting, pipe a failure to email/Slack/webhook — ask the Olympus Claude to
add that once you pick a channel.)

### 3. Claude Code on the web / app (trigger tasks from your phone or browser)
Claude Code on the web runs sessions in managed cloud environments. To have those
sessions act on **your** hardware, you register a **self-hosted environment / pool**
(these show up with `ccpool_` IDs) pointed at Olympus. Once set up, you start a task
from claude.ai/code (or the mobile app) and it runs on the VM.

- Overview & setup: https://code.claude.com/docs/en/claude-code-on-the-web
- Concepts (environments, sources, sessions, triggers): same docs, "Environments"
  and "Sources" pages.

Note: self-hosted pool setup is an infra step (you connect Olympus as a runner).
It's more work than SSH but gives you the "kick off a task from anywhere" workflow
you described. If you want, the Olympus Claude can walk you through wiring it up
once you're SSH'd in — that's the right place to do it since it needs VM access.

## Recommended first run

1. Put the kit on Olympus and fill in `CLAUDE.md`.
2. SSH in, run `bash olympus/scripts/olympus-health.sh` — fix anything red.
3. Fill the CONFIG in `smoke-test.sh`, run it.
4. Open `claude`, paste the **health check** prompt from `PROMPTS.md`, and let it
   give you a first report. Grow from there.
