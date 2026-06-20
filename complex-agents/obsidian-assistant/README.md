# Obsidian Voice Assistant

Build and explore an **Obsidian-style knowledge base entirely by voice.**

[Obsidian](https://obsidian.md) is a popular "second brain" app: your notes are
plain markdown files in a folder (a *vault*), connected with `[[wikilinks]]` and
visualized as a knowledge graph. This example brings that idea to the LiveKit
Agents platform — you *talk* to an agent and it captures, organizes, and links
your notes, while a browser graph view updates live as you speak.

It ships in **three layers**, each usable on its own:

| Layer | File | What it is |
|-------|------|------------|
| 1. Vault tool | `obsidian_vault.py` | A reusable, dependency-light Python library (and CLI) that reads/writes/searches/links notes in an Obsidian-compatible vault. **No LiveKit dependency** — point it at a real Obsidian vault and use it from any agent. |
| 2. Voice agent | `agent.py` | A LiveKit voice agent that exposes the vault as function tools, so you build your knowledge base by conversation. Broadcasts the graph to a frontend over RPC on every change. |
| 3. Graph viewer | `graph-viewer/index.html` | A self-contained "mini Obsidian in the browser": an interactive force-directed graph of your notes with backlinks and search. No build step. |

---

## Layer 1 — The vault tool (works standalone)

The vault is just a folder of `.md` files with YAML frontmatter and `[[wikilinks]]`
— exactly what the Obsidian desktop app reads, so any vault this creates opens
directly in Obsidian.

Try it from the command line (no LiveKit needed):

```bash
cd complex-agents/obsidian-assistant

python obsidian_vault.py create "Project Apollo" --content "Our moonshot voice agent." --tags project idea
python obsidian_vault.py create "Voice Agents" --content "Realtime AI over [[Project Apollo]]." --tags ai
python obsidian_vault.py link "Project Apollo" "Voice Agents"
python obsidian_vault.py backlinks "Voice Agents"     # -> Project Apollo
python obsidian_vault.py search moonshot
python obsidian_vault.py export-graph                 # writes vault/graph.json
```

Use it in your own code:

```python
from obsidian_vault import ObsidianVault
vault = ObsidianVault("~/MyObsidianVault")   # an existing vault works too
vault.create_note("Idea", "A thought.", tags=["inbox"])
vault.link_notes("Idea", "Project Apollo")
print(vault.get_backlinks("Project Apollo"))
```

## Layer 2 — The voice agent

```bash
pip install -r ../../requirements.txt   # from repo root
python complex-agents/obsidian-assistant/agent.py dev
```

Then connect with any LiveKit frontend (e.g. the `base-frontend-template`) and say:

- *"Make a note called Project Apollo about our moonshot voice agent."*
- *"Add to it: we picked Deepgram for STT."*
- *"Link Project Apollo to Voice Agents."*
- *"What links to Voice Agents?"*
- *"Search my notes for Deepgram."*

Notes are written to `./vault/*.md` and `./vault/graph.json` is refreshed and
pushed to the frontend over RPC after every change. The agent uses Deepgram STT,
OpenAI LLM + TTS, and Silero VAD (swap any of these in `ObsidianAgent.__init__`).

## Layer 3 — The graph viewer

```bash
cd complex-agents/obsidian-assistant
python -m http.server 8000
# open http://localhost:8000/graph-viewer/
```

It loads `vault/graph.json` and renders an interactive graph: node size reflects
how connected a note is, clicking a node highlights its links and shows
backlinks, and the search box filters the graph. (A sample vault is included so
it renders immediately.) You can also open `graph-viewer/index.html` directly
and use **Open graph.json…** to load a file without a server.

To make it update **live** while you talk, register a `receive_graph` RPC method
in your LiveKit frontend and call the viewer's `render(graph)` with the payload —
`agent.py` already broadcasts the graph on every change (and answers a
`get_graph` RPC so a frontend can pull the current state on connect).

## How the layers fit together

```
You (voice) ──► agent.py ──► obsidian_vault.py ──► ./vault/*.md   (open in Obsidian)
                   │                  │
                   │                  └──► vault/graph.json
                   └──── RPC "receive_graph" ────► graph-viewer (live graph)
```

The transport (voice/RPC) and the knowledge logic (vault) are intentionally
decoupled, so you can reuse `obsidian_vault.py` anywhere or put a different
frontend on top.
