"""
---
title: Obsidian Voice Assistant
category: complex-agents
tags: [complex-agents, obsidian, knowledge-base, function-tools, rpc]
difficulty: intermediate
description: A voice agent that turns spoken conversation into an interconnected Obsidian-style markdown vault and pushes live graph updates to a frontend.
demonstrates:
  - Wrapping a plain-Python library (ObsidianVault) as LiveKit function tools
  - Letting users build a [[wikilinked]] knowledge base entirely by voice
  - Returning (None, message) tuples so the LLM narrates tool results naturally
  - Exporting a knowledge graph and broadcasting it to a frontend over RPC
  - Keeping vault logic decoupled from the voice/transport layer
---

Obsidian Voice Assistant
========================

Talk to this agent and it manages an Obsidian-compatible vault for you:

    "Make a note called Project Apollo about our moonshot voice agent."
    "Add to it: we picked Deepgram for STT."
    "Link Project Apollo to Voice Agents."
    "What links to Voice Agents?"
    "Search my notes for Deepgram."

Every change is written to real ``.md`` files under ``./vault`` (open that
folder in the Obsidian desktop app and you'll see them), and a fresh
``graph.json`` is exported and pushed to the graph viewer over RPC so the
knowledge graph updates live as you speak.

The actual note logic lives in ``obsidian_vault.py`` — this file is only the
voice/transport layer.
"""

import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession, RunContext
from livekit.plugins import deepgram, openai, silero

from obsidian_vault import ObsidianVault

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger("obsidian-assistant")
logger.setLevel(logging.INFO)

VAULT_DIR = Path(__file__).parent / "vault"


class ObsidianAgent(Agent):
    def __init__(self, ctx: JobContext) -> None:
        super().__init__(
            instructions="""
                You are an Obsidian knowledge-base assistant communicating by voice.
                You help the user capture, organize, and connect their notes in a
                personal markdown vault.

                Guidelines:
                - When the user shares an idea, fact, or task, offer to save it as a note.
                - Prefer short, descriptive note titles (these become [[wikilinks]]).
                - Use link_notes to connect related ideas — a good vault is well linked.
                - When asked what relates to something, use get_backlinks and search_notes.
                - Speak naturally; never read out markdown syntax, brackets, or file paths.
                - Confirm what you did in one short sentence.
            """,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4.1-mini"),
            tts=openai.TTS(),
            vad=silero.VAD.load(),
        )
        self.ctx = ctx
        self.vault = ObsidianVault(VAULT_DIR)

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Greet the user briefly and offer to help capture or connect notes."
        )

    # -- function tools (thin wrappers over ObsidianVault) ----------------- #
    @function_tool
    async def create_note(
        self,
        context: RunContext,
        title: str,
        content: str = "",
        tags: list[str] | None = None,
    ):
        """Create a new note in the vault.

        Args:
            title: Short, descriptive title for the note.
            content: The body text of the note.
            tags: Optional list of tags to categorize the note.
        """
        try:
            self.vault.create_note(title, content, tags=tags, overwrite=True)
        except Exception as e:
            logger.error(f"create_note failed: {e}")
            return None, f"I couldn't create that note: {e}"
        await self._publish_graph()
        return None, f"Saved a note titled {title}."

    @function_tool
    async def append_to_note(self, context: RunContext, title: str, content: str):
        """Append additional text to an existing note (creates it if missing).

        Args:
            title: The title of the note to add to.
            content: The text to append.
        """
        self.vault.append_to_note(title, content)
        await self._publish_graph()
        return None, f"Added that to {title}."

    @function_tool
    async def link_notes(self, context: RunContext, from_title: str, to_title: str):
        """Create a link from one note to another.

        Args:
            from_title: The note the link starts from.
            to_title: The note the link points to.
        """
        self.vault.link_notes(from_title, to_title)
        await self._publish_graph()
        return None, f"Linked {from_title} to {to_title}."

    @function_tool
    async def search_notes(self, context: RunContext, query: str):
        """Search the vault for notes matching a query.

        Args:
            query: The text to search for.
        """
        results = self.vault.search(query, limit=5)
        if not results:
            return None, f"I didn't find any notes matching {query}."
        titles = ", ".join(r["title"] for r in results)
        return None, f"I found {len(results)} notes: {titles}."

    @function_tool
    async def get_backlinks(self, context: RunContext, title: str):
        """List the notes that link to a given note.

        Args:
            title: The note to find backlinks for.
        """
        links = self.vault.get_backlinks(title)
        if not links:
            return None, f"Nothing links to {title} yet."
        return None, f"These notes link to {title}: {', '.join(links)}."

    @function_tool
    async def list_notes(self, context: RunContext):
        """List all notes currently in the vault."""
        titles = self.vault.list_notes()
        if not titles:
            return None, "Your vault is empty. Want to create your first note?"
        return None, f"You have {len(titles)} notes: {', '.join(titles)}."

    # -- frontend sync ----------------------------------------------------- #
    async def _publish_graph(self):
        """Export graph.json and push the latest graph to the frontend via RPC."""
        try:
            graph = self.vault.build_graph()
            self.vault.export_graph()
        except Exception as e:
            logger.error(f"Failed to build/export graph: {e}")
            return

        remote = list(self.ctx.room.remote_participants.values())
        if not remote:
            return
        try:
            await self.ctx.room.local_participant.perform_rpc(
                destination_identity=remote[0].identity,
                method="receive_graph",
                payload=json.dumps(graph),
            )
            logger.info(f"Published graph: {len(graph['nodes'])} notes")
        except Exception as e:
            logger.error(f"RPC receive_graph failed: {e}")


async def entrypoint(ctx: JobContext):
    session = AgentSession()
    agent = ObsidianAgent(ctx)

    await session.start(agent=agent, room=ctx.room)

    # Let a frontend pull the current graph on demand (e.g. right after it connects).
    async def handle_get_graph(_rpc_invocation):
        return json.dumps(agent.vault.build_graph())

    ctx.room.local_participant.register_rpc_method("get_graph", handle_get_graph)
    logger.info(f"Obsidian assistant started. Vault: {VAULT_DIR}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
