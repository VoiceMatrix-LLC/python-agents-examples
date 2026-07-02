# Ready-to-paste task prompts for Claude Code on Olympus

Paste any of these into the `claude` prompt **on the Olympus VM** (SSH in, run
`claude` from your working directory). They assume the VM has `CLAUDE.md` and the
`olympus/scripts/` from this kit. Fill in the `<...>` bits.

---

## Health check

```
Run a full health check of Olympus. Execute olympus/scripts/olympus-health.sh,
then also check: disk on all mounts, memory, load vs core count, and the status
of each agent listed in CLAUDE.md. Summarize what's healthy, what's degraded, and
anything that needs attention. Do NOT restart or change anything — read-only.
```

## Smoke test after a deploy

```
We just deployed. Run olympus/scripts/smoke-test.sh and report the result. If any
agent fails its import/compile check or a required env var is missing, show me the
exact error and the file/line involved. Don't start long-running workers and don't
send real traffic.
```

## Investigate a specific agent

```
Agent <name> seems unhealthy. Investigate read-only: check its process/service
status, tail the last 200 log lines, look for stack traces or repeated errors, and
check whether its provider API keys are present in the env. Give me a diagnosis and
a proposed fix, but do NOT restart or edit anything until I approve.
```

## Debug a crash

```
<name> crashed at <time>. Read its logs around that timestamp, identify the root
cause, and trace it to the responsible code. Propose a minimal fix as a diff. Don't
apply it yet — show me the diff and how you'd verify it first.
```

## Review a change before it ships

```
Review the uncommitted changes in this repo (git diff) for correctness and for
anything risky on a live VM — secrets, breaking config, disruptive restarts. Flag
issues by file:line. Don't push.
```

## Develop a feature (safe loop)

```
Build <feature description>. Work on a new branch, not main. Write the code, run
olympus/scripts/smoke-test.sh to verify it imports/compiles, show me the diff and
test output, and stop before pushing or deploying so I can review.
```

## Restart an agent (guarded — only when you mean it)

```
Restart agent <name>. First confirm from logs/metrics that it is safe to restart
(no in-flight session it would drop). Show me that evidence, restart it with the
command in CLAUDE.md, then verify it comes back healthy via the health script.
```

---

### Tips
- Keep the "don't push / don't restart / show me first" guardrail in prompts until
  you trust the loop — the Olympus Claude has real power on a live box.
- The `CLAUDE.md` on the VM is doing half the work: the better you fill it in, the
  less you need to spell out in each prompt.
