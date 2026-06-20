"""
---
title: Obsidian Sample Vault Seeder
category: complex-agents
tags: [complex-agents, obsidian, knowledge-base, demo, seed]
difficulty: beginner
description: Rebuilds a rich, densely interconnected sample Obsidian vault so the graph viewer has something interesting to show.
demonstrates:
  - Programmatically seeding an Obsidian vault with linked notes via ObsidianVault
  - Structuring a knowledge base with MOCs (maps of content), concepts, tools, and projects
  - Producing a graph dense enough to demo backlinks and clustering
---

Seed a rich sample vault
========================

The starter vault only had a handful of notes. This script rebuilds ``./vault``
with a realistic "second brain" about building voice AI agents — maps of
content, concepts, tools, and projects, all cross-linked with [[wikilinks]] so
the knowledge graph actually looks like a graph.

    python seed_vault.py                 # rebuilds ./vault (overwrites notes)
    python seed_vault.py --vault ~/Vault

After seeding, regenerate the viewers:

    python obsidian_vault.py export-graph        # vault/graph.json
    python build_standalone.py                   # phone-friendly HTML
"""

from __future__ import annotations

import argparse

from obsidian_vault import ObsidianVault

# (title, tags, body). Bodies embed [[wikilinks]] so edges form automatically.
NOTES: list[tuple[str, list[str], str]] = [
    # --- Maps of Content -------------------------------------------------- #
    ("Second Brain", ["moc"],
     "The home note of my knowledge base. Start here.\n\n"
     "Areas: [[Voice AI MOC]] · [[Knowledge Management MOC]] · [[Projects MOC]]."),
    ("Voice AI MOC", ["moc", "ai"],
     "Map of everything about real-time voice agents.\n\n"
     "Core: [[Voice Agents]], [[LiveKit]], [[Agent Pipeline]].\n"
     "Stages: [[Speech to Text]] → [[Large Language Model]] → [[Text to Speech]].\n"
     "Supporting: [[Voice Activity Detection]], [[Turn Detection]], [[Function Calling]], [[RAG]]."),
    ("Knowledge Management MOC", ["moc", "pkm"],
     "How I organize what I learn.\n\n"
     "Tools: [[Obsidian]]. Methods: [[Zettelkasten]], [[Spaced Repetition]].\n"
     "Mechanics: [[Wikilinks]], [[Backlinks]], [[Maps of Content]]."),
    ("Projects MOC", ["moc"],
     "Things I'm building.\n\n"
     "[[Project Apollo]] · [[Meeting Notetaker]] · [[Obsidian Voice Assistant]]."),

    # --- Concepts: voice -------------------------------------------------- #
    ("Voice Agents", ["ai", "concept"],
     "Real-time AI you talk to. Built on [[LiveKit]] and an [[Agent Pipeline]]. "
     "Can use [[Function Calling]] to take actions and [[RAG]] for knowledge."),
    ("Agent Pipeline", ["ai", "concept"],
     "The chain that powers a [[Voice Agents]] turn: [[Voice Activity Detection]] detects speech, "
     "[[Speech to Text]] transcribes it, the [[Large Language Model]] reasons, and "
     "[[Text to Speech]] speaks the reply. [[Turn Detection]] decides when the user is done."),
    ("Speech to Text", ["ai", "concept"],
     "Converts audio to text. Provider used here: [[Deepgram]]. Feeds the [[Large Language Model]]. "
     "Part of the [[Agent Pipeline]]."),
    ("Large Language Model", ["ai", "concept"],
     "Reasons over the conversation and decides what to say or do. Provider: [[OpenAI]]. "
     "Drives [[Function Calling]] and consumes [[RAG]] context. Part of the [[Agent Pipeline]]."),
    ("Text to Speech", ["ai", "concept"],
     "Turns the model's reply into audio. Providers: [[OpenAI]], [[Cartesia]]. "
     "Final stage of the [[Agent Pipeline]]."),
    ("Voice Activity Detection", ["ai", "concept"],
     "Detects when someone is speaking. Implementation: [[Silero]]. Gates the [[Agent Pipeline]]."),
    ("Turn Detection", ["ai", "concept"],
     "Decides when the user has finished a turn so the [[Voice Agents]] can respond. "
     "Works with [[Voice Activity Detection]]."),
    ("Function Calling", ["ai", "concept"],
     "Lets the [[Large Language Model]] call tools — e.g. the [[Obsidian Voice Assistant]] "
     "uses it to create and link notes in a vault."),
    ("RAG", ["ai", "concept"],
     "Retrieval-Augmented Generation: feed the [[Large Language Model]] relevant notes from a "
     "knowledge base before it answers. Pairs naturally with a [[Second Brain]]."),

    # --- Concepts: PKM ---------------------------------------------------- #
    ("Wikilinks", ["pkm", "concept"],
     "Links between notes written as double brackets. Power the graph and create [[Backlinks]]. "
     "The native syntax of [[Obsidian]]."),
    ("Backlinks", ["pkm", "concept"],
     "The reverse of [[Wikilinks]]: every note shows what points to it. Core to [[Obsidian]]."),
    ("Maps of Content", ["pkm", "concept"],
     "Hub notes (MOCs) that curate links to related notes, like [[Second Brain]]. "
     "An alternative to rigid folders in [[Knowledge Management MOC]]."),
    ("Zettelkasten", ["pkm", "method"],
     "A note-taking method of small, atomic, linked notes. Influences how I use [[Wikilinks]] "
     "and [[Obsidian]]."),
    ("Spaced Repetition", ["pkm", "method"],
     "Review notes at increasing intervals to remember them. Complements [[Zettelkasten]]."),

    # --- Tools ------------------------------------------------------------ #
    ("Obsidian", ["tool", "pkm"],
     "Markdown knowledge base app. Notes are plain files connected by [[Wikilinks]] with "
     "[[Backlinks]] and a graph view. The basis of the [[Obsidian Voice Assistant]]."),
    ("LiveKit", ["tool", "infra"],
     "Real-time infrastructure for [[Voice Agents]]. Provides the audio transport and the "
     "agents SDK that runs the [[Agent Pipeline]]."),
    ("Deepgram", ["tool", "ai"],
     "Speech-to-text provider used for [[Speech to Text]]."),
    ("OpenAI", ["tool", "ai"],
     "Provides the [[Large Language Model]] and one [[Text to Speech]] option."),
    ("Cartesia", ["tool", "ai"],
     "Low-latency [[Text to Speech]] provider."),
    ("Silero", ["tool", "ai"],
     "Open-source [[Voice Activity Detection]] model."),

    # --- Projects --------------------------------------------------------- #
    ("Project Apollo", ["project"],
     "A moonshot to build the ultimate [[Voice Agents]] product. Uses [[LiveKit]], "
     "[[RAG]] over my [[Second Brain]], and [[Function Calling]]."),
    ("Meeting Notetaker", ["project"],
     "Agent that listens to meetings via [[Speech to Text]] and writes structured notes into "
     "[[Obsidian]]. A cousin of the [[Obsidian Voice Assistant]]."),
    ("Obsidian Voice Assistant", ["project"],
     "This project: build an [[Obsidian]] vault by voice. Uses the [[Agent Pipeline]] with "
     "[[Function Calling]] to create notes and [[Wikilinks]]. Visualized as a graph."),
]


def seed(vault_dir: str) -> int:
    vault = ObsidianVault(vault_dir)
    # Clear existing demo notes so the seed is reproducible.
    for note in vault.all_notes():
        note.path.unlink()
    for title, tags, body in NOTES:
        vault.create_note(title, body, tags=tags, overwrite=True)
    vault.export_graph()
    graph = vault.build_graph()
    return len(graph["nodes"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed a rich sample Obsidian vault.")
    p.add_argument("--vault", default="vault")
    args = p.parse_args(argv)
    n = seed(args.vault)
    print(f"Seeded {n} interconnected notes into {args.vault}/ and wrote graph.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
