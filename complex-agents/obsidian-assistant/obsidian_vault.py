"""
---
title: Obsidian Vault Integration
category: complex-agents
tags: [complex-agents, obsidian, knowledge-base, markdown, tool]
difficulty: intermediate
description: A reusable, dependency-light library for reading, writing, searching, and linking notes in an Obsidian-style markdown vault.
demonstrates:
  - Managing a folder of Obsidian-compatible .md notes (vault) from Python
  - Parsing and writing YAML-style frontmatter without extra dependencies
  - Resolving [[wikilinks]] and computing backlinks across notes
  - Building a knowledge graph (nodes + edges) for visualization
  - Exposing the vault as a CLI so it can be tested without LiveKit
---

ObsidianVault
=============

This is the *foundation* shared by the voice agent and the graph viewer in this
example. It has **no LiveKit dependency** so you can use it (and test it) on its
own, point it at a real Obsidian vault, or drop it into any other agent.

An Obsidian "vault" is just a folder of plain-markdown ``.md`` files. Notes link
to each other with ``[[Wikilinks]]`` and carry metadata in a YAML *frontmatter*
block at the top of the file:

    ---
    tags: [project, idea]
    created: 2026-06-20T10:00:00
    aliases: [PKM]
    ---
    # My Note

    This note links to [[Another Note]].

Because that format is exactly what the Obsidian desktop app reads, any vault
this class writes can be opened directly in Obsidian.

Run ``python obsidian_vault.py --help`` to use it from the command line.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# [[Wikilink]] matcher. Supports [[Note]] and [[Note|display text]].
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# #tag matcher used as a fallback when frontmatter has no explicit tags.
INLINE_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9_/-]+)")


def slugify(title: str) -> str:
    """Turn a note title into a safe filename stem (without extension)."""
    slug = title.strip()
    # Obsidian itself keeps spaces in filenames, but a slug is friendlier for
    # cross-platform filesystems and URLs used by the graph viewer.
    slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "untitled"


@dataclass
class Note:
    """An in-memory view of a single markdown note."""

    title: str
    path: Path
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def tags(self) -> list[str]:
        fm_tags = self.frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [fm_tags]
        if fm_tags:
            return list(fm_tags)
        # Fall back to inline #hashtags found in the body.
        return sorted(set(INLINE_TAG_RE.findall(self.body)))

    @property
    def links(self) -> list[str]:
        """Titles this note points to via [[wikilinks]] (de-duplicated, ordered)."""
        seen: dict[str, None] = {}
        for match in WIKILINK_RE.findall(self.body):
            seen.setdefault(match.strip(), None)
        return list(seen.keys())


# --------------------------------------------------------------------------- #
# Minimal frontmatter (de)serialization.
# We intentionally avoid a YAML dependency: notes only use scalars and simple
# lists, which we can round-trip safely by hand.
# --------------------------------------------------------------------------- #
def _dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    if not frontmatter:
        return ""
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(_dump_scalar(v) for v in value)
            lines.append(f"{key}: [{rendered}]")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split raw file text into (frontmatter dict, body string)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return {}, text
    fm: dict[str, Any] = {}
    body_start = None
    for i in range(1, len(parts)):
        line = parts[i]
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            fm[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        elif raw in ("true", "false"):
            fm[key] = raw == "true"
        else:
            fm[key] = raw
    if body_start is None:
        return {}, text
    body = "\n".join(parts[body_start:])
    return fm, body.lstrip("\n")


class ObsidianVault:
    """Read/write/search/link notes in an Obsidian-style vault directory."""

    def __init__(self, vault_dir: str | Path):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)

    # -- locating notes ---------------------------------------------------- #
    def _path_for(self, title: str) -> Path:
        return self.vault_dir / f"{slugify(title)}.md"

    def _iter_paths(self):
        return sorted(self.vault_dir.glob("*.md"))

    def exists(self, title: str) -> bool:
        return self._path_for(title).exists()

    def resolve(self, title_or_slug: str) -> Note | None:
        """Find a note by exact title, slug, or alias (case-insensitive)."""
        target = title_or_slug.strip().lower()
        target_slug = slugify(title_or_slug)
        for note in self.all_notes():
            if note.title.lower() == target:
                return note
            if slugify(note.title) == target_slug:
                return note
            aliases = note.frontmatter.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            if any(a.lower() == target for a in aliases):
                return note
        return None

    # -- CRUD -------------------------------------------------------------- #
    def create_note(
        self,
        title: str,
        content: str = "",
        tags: list[str] | None = None,
        links: list[str] | None = None,
        overwrite: bool = False,
    ) -> Note:
        """Create (or overwrite) a note with frontmatter and a body."""
        path = self._path_for(title)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Note already exists: {title!r}. Use overwrite=True.")

        body = content.strip()
        if links:
            link_md = " ".join(f"[[{l}]]" for l in links)
            body = f"{body}\n\nRelated: {link_md}" if body else f"Related: {link_md}"

        frontmatter: dict[str, Any] = {
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        if tags:
            frontmatter["tags"] = list(tags)

        self._write(path, title, frontmatter, body)
        return Note(title=title, path=path, frontmatter=frontmatter, body=body)

    def read_note(self, title: str) -> Note | None:
        note = self.resolve(title)
        return note

    def append_to_note(self, title: str, content: str, create: bool = True) -> Note:
        """Append a line/paragraph to an existing note (or create it)."""
        note = self.resolve(title)
        if note is None:
            if not create:
                raise FileNotFoundError(f"Note not found: {title!r}")
            return self.create_note(title, content)
        new_body = f"{note.body.rstrip()}\n\n{content.strip()}".strip()
        self._write(note.path, note.title, note.frontmatter, new_body)
        note.body = new_body
        return note

    def link_notes(self, from_title: str, to_title: str) -> Note:
        """Add a [[wikilink]] from one note to another (creating both if needed)."""
        source = self.resolve(from_title) or self.create_note(from_title)
        # Make sure the target exists so the link is not a dangling reference.
        if self.resolve(to_title) is None:
            self.create_note(to_title)
        if to_title in source.links:
            return source
        return self.append_to_note(source.title, f"See also [[{to_title}]].")

    def delete_note(self, title: str) -> bool:
        note = self.resolve(title)
        if note is None:
            return False
        note.path.unlink()
        return True

    # -- queries ----------------------------------------------------------- #
    def all_notes(self) -> list[Note]:
        notes: list[Note] = []
        for path in self._iter_paths():
            text = path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            title = fm.get("title") or self._title_from_body(body) or path.stem
            notes.append(Note(title=str(title), path=path, frontmatter=fm, body=body))
        return notes

    def list_notes(self) -> list[str]:
        return [n.title for n in self.all_notes()]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Case-insensitive full-text search over titles, tags, and bodies."""
        q = query.strip().lower()
        results: list[dict[str, Any]] = []
        for note in self.all_notes():
            haystack = f"{note.title}\n{' '.join(note.tags)}\n{note.body}".lower()
            if q in haystack:
                score = (
                    3 * note.title.lower().count(q)
                    + 2 * sum(t.lower().count(q) for t in note.tags)
                    + note.body.lower().count(q)
                )
                results.append(
                    {"title": note.title, "score": score, "excerpt": self._excerpt(note.body, q)}
                )
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    def get_backlinks(self, title: str) -> list[str]:
        """Return titles of all notes that link *to* this note."""
        target = self.resolve(title)
        target_title = target.title if target else title
        target_slug = slugify(target_title)
        backlinks: list[str] = []
        for note in self.all_notes():
            if note.title == target_title:
                continue
            if any(slugify(link) == target_slug for link in note.links):
                backlinks.append(note.title)
        return backlinks

    def build_graph(self) -> dict[str, Any]:
        """Return a {nodes, edges} graph of the whole vault for visualization."""
        notes = self.all_notes()
        titles_by_slug = {slugify(n.title): n.title for n in notes}
        backlink_count: dict[str, int] = {n.title: 0 for n in notes}
        edges: list[dict[str, str]] = []
        for note in notes:
            for link in note.links:
                target_title = titles_by_slug.get(slugify(link), link)
                edges.append({"source": note.title, "target": target_title})
                if target_title in backlink_count:
                    backlink_count[target_title] += 1
        nodes = [
            {
                "id": n.title,
                "slug": slugify(n.title),
                "tags": n.tags,
                "links": len(n.links),
                "backlinks": backlink_count.get(n.title, 0),
            }
            for n in notes
        ]
        return {"nodes": nodes, "edges": edges}

    def export_graph(self, out_path: str | Path | None = None) -> Path:
        """Write the graph as JSON (consumed by the graph viewer)."""
        out_path = Path(out_path) if out_path else self.vault_dir / "graph.json"
        out_path.write_text(json.dumps(self.build_graph(), indent=2), encoding="utf-8")
        return out_path

    # -- helpers ----------------------------------------------------------- #
    def _write(self, path: Path, title: str, frontmatter: dict[str, Any], body: str) -> None:
        fm = dict(frontmatter)
        fm.setdefault("title", title)
        header = dump_frontmatter(fm)
        # Body always starts with an H1 of the title for nice Obsidian display.
        body_text = body if body.lstrip().startswith("#") else f"# {title}\n\n{body}"
        content = f"{header}\n\n{body_text}\n" if header else f"{body_text}\n"
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _title_from_body(body: str) -> str | None:
        for line in body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return None

    @staticmethod
    def _excerpt(body: str, query: str, width: int = 80) -> str:
        idx = body.lower().find(query)
        if idx == -1:
            return body[:width].replace("\n", " ").strip()
        start = max(0, idx - width // 2)
        end = min(len(body), idx + width // 2)
        snippet = body[start:end].replace("\n", " ").strip()
        return f"...{snippet}..." if start > 0 or end < len(body) else snippet


# --------------------------------------------------------------------------- #
# CLI — lets you exercise the vault without running the agent.
# --------------------------------------------------------------------------- #
def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage an Obsidian-style markdown vault.")
    parser.add_argument(
        "--vault", default="vault", help="Path to the vault directory (default: ./vault)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create a note")
    p_create.add_argument("title")
    p_create.add_argument("--content", default="")
    p_create.add_argument("--tags", nargs="*", default=None)
    p_create.add_argument("--links", nargs="*", default=None)
    p_create.add_argument("--overwrite", action="store_true")

    p_append = sub.add_parser("append", help="Append text to a note")
    p_append.add_argument("title")
    p_append.add_argument("content")

    p_link = sub.add_parser("link", help="Link one note to another")
    p_link.add_argument("from_title")
    p_link.add_argument("to_title")

    p_read = sub.add_parser("read", help="Print a note")
    p_read.add_argument("title")

    p_search = sub.add_parser("search", help="Search the vault")
    p_search.add_argument("query")

    p_back = sub.add_parser("backlinks", help="Show backlinks to a note")
    p_back.add_argument("title")

    sub.add_parser("list", help="List all notes")
    sub.add_parser("graph", help="Print the vault graph as JSON")
    sub.add_parser("export-graph", help="Write graph.json to the vault")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_cli().parse_args(argv)
    vault = ObsidianVault(args.vault)

    if args.command == "create":
        note = vault.create_note(
            args.title, args.content, tags=args.tags, links=args.links, overwrite=args.overwrite
        )
        print(f"Created: {note.path}")
    elif args.command == "append":
        note = vault.append_to_note(args.title, args.content)
        print(f"Updated: {note.path}")
    elif args.command == "link":
        note = vault.link_notes(args.from_title, args.to_title)
        print(f"Linked {args.from_title!r} -> {args.to_title!r}")
    elif args.command == "read":
        note = vault.read_note(args.title)
        print(note.path.read_text(encoding="utf-8") if note else f"Not found: {args.title}")
    elif args.command == "search":
        for r in vault.search(args.query):
            print(f"[{r['score']}] {r['title']}: {r['excerpt']}")
    elif args.command == "backlinks":
        links = vault.get_backlinks(args.title)
        print("\n".join(links) if links else "(no backlinks)")
    elif args.command == "list":
        print("\n".join(vault.list_notes()) or "(empty vault)")
    elif args.command == "graph":
        print(json.dumps(vault.build_graph(), indent=2))
    elif args.command == "export-graph":
        path = vault.export_graph()
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
