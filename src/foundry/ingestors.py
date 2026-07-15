"""
Ingestors — real documents and conversations into events.

V1.0 requirement: "Use real documents and conversations."

Each ingestor converts an external format into one or more `ingest`
events. Ingestors do NOT interpret content — no claims, no structure,
no cleverness. Interpretation is the model's job (derive); preservation
is the ingestor's job. The original text is stored verbatim.

Supported:
    ingest_text(kernel, text, source)
    ingest_file(kernel, path)              # .md / .txt
    ingest_chatgpt_export(kernel, path)    # ChatGPT conversations.json
    ingest_claude_export(kernel, path)     # Claude conversation export
"""

from __future__ import annotations

import json
from pathlib import Path

from .kernel import Kernel


def ingest_text(k: Kernel, text: str, source: str = "manual") -> list[dict]:
    return [k.ingest(text, source=source)]


def ingest_file(k: Kernel, path: str | Path) -> list[dict]:
    p = Path(path)
    return [k.ingest(p.read_text(encoding="utf-8"), source=f"file:{p.name}")]


def ingest_chatgpt_export(k: Kernel, path: str | Path) -> list[dict]:
    """
    ChatGPT's conversations.json: a list of conversations, each with a
    `mapping` of message nodes. One event per conversation — the
    conversation is the natural unit of provenance.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = []
    for conv in data:
        title = conv.get("title", "untitled")
        lines = []
        for node in (conv.get("mapping") or {}).values():
            msg = node.get("message")
            if not msg:
                continue
            role = msg.get("author", {}).get("role", "?")
            parts = msg.get("content", {}).get("parts", [])
            text = " ".join(p for p in parts if isinstance(p, str)).strip()
            if text and role != "system":
                lines.append(f"{role}: {text}")
        if lines:
            events.append(
                k.ingest("\n".join(lines), source=f"chatgpt:{title}")
            )
    return events


def ingest_claude_export(k: Kernel, path: str | Path) -> list[dict]:
    """
    Claude export: conversations with `chat_messages` lists of
    {sender, text}. Same principle: one event per conversation.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    events = []
    for conv in data:
        title = conv.get("name", "untitled")
        lines = [
            f"{m.get('sender', '?')}: {m.get('text', '').strip()}"
            for m in conv.get("chat_messages", [])
            if m.get("text", "").strip()
        ]
        if lines:
            events.append(k.ingest("\n".join(lines), source=f"claude:{title}"))
    return events
