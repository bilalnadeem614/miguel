"""Persistent memory system for Miguel.

Stores facts, user preferences, project context, and interaction summaries
in a SQLite database that persists across conversations. This gives Miguel
long-term memory — it can remember things from past sessions.

Storage schema:
    memories(id, key, value, category, created_at, updated_at)

Categories:
    - fact: Things Miguel has learned (e.g. "Python 3.12 released Oct 2023")
    - preference: User preferences (e.g. "User prefers concise answers")
    - context: Project/session context (e.g. "Working on a Flask web app")
    - summary: Interaction summaries (e.g. "Helped user debug auth issue")
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from miguel.agent.tools.error_utils import safe_tool

MEMORY_DB = Path(__file__).parent.parent / "memory.db"

VALID_CATEGORIES = {"fact", "preference", "context", "summary"}


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the memory database, creating the table if needed."""
    conn = sqlite3.connect(str(MEMORY_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'fact',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)
    """)
    conn.commit()
    return conn


@safe_tool
def remember(key: str, value: str, category: str = "fact") -> str:
    """Store a piece of information in persistent memory.

    Use this to save facts, user preferences, project context, or session summaries
    so they persist across conversations.

    Args:
        key: Short label for the memory (e.g. "user_name", "project_language").
        value: The information to remember (e.g. "Alice", "Python with FastAPI").
        category: One of 'fact', 'preference', 'context', 'summary'. Default: 'fact'.

    Returns:
        Confirmation message with the memory ID.
    """
    if not key or not key.strip():
        return "Error: key cannot be empty."
    if not value or not value.strip():
        return "Error: value cannot be empty."

    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        return f"Error: category must be one of {VALID_CATEGORIES}, got '{category}'."

    key = key.strip()
    value = value.strip()
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_conn()
    try:
        # Check if a memory with this exact key and category already exists — update it
        existing = conn.execute(
            "SELECT id FROM memories WHERE key = ? AND category = ?",
            (key, category),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE memories SET value = ?, updated_at = ? WHERE id = ?",
                (value, now, existing["id"]),
            )
            conn.commit()
            return f"Updated memory #{existing['id']} — {category}/{key}: {value}"
        else:
            cursor = conn.execute(
                "INSERT INTO memories (key, value, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (key, value, category, now, now),
            )
            conn.commit()
            return f"Stored memory #{cursor.lastrowid} — {category}/{key}: {value}"
    finally:
        conn.close()


@safe_tool
def recall(query: str, category: Optional[str] = None, limit: int = 10) -> str:
    """Search persistent memory by keyword.

    Searches both keys and values for the query string (case-insensitive).
    Optionally filter by category.

    Args:
        query: Search term to look for in memory keys and values.
        category: Optional category filter ('fact', 'preference', 'context', 'summary').
        limit: Maximum results to return (default 10).

    Returns:
        Matching memories formatted as a readable list, or a message if none found.
    """
    if not query or not query.strip():
        return "Error: query cannot be empty."

    limit = max(1, min(limit, 50))
    query_pattern = f"%{query.strip()}%"

    conn = _get_conn()
    try:
        if category and category.strip():
            category = category.lower().strip()
            if category not in VALID_CATEGORIES:
                return f"Error: category must be one of {VALID_CATEGORIES}, got '{category}'."
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? AND (key LIKE ? OR value LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (category, query_pattern, query_pattern, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE (key LIKE ? OR value LIKE ?) ORDER BY updated_at DESC LIMIT ?",
                (query_pattern, query_pattern, limit),
            ).fetchall()

        if not rows:
            return f"No memories found matching '{query.strip()}'."

        lines = [f"Found {len(rows)} memor{'y' if len(rows) == 1 else 'ies'} matching '{query.strip()}':\n"]
        for row in rows:
            lines.append(
                f"  [#{row['id']}] ({row['category']}) **{row['key']}**: {row['value']}"
                f"  _(saved: {row['updated_at'][:16]})_"
            )
        return "\n".join(lines)
    finally:
        conn.close()


@safe_tool
def forget(memory_id: int) -> str:
    """Delete a specific memory by its ID.

    Args:
        memory_id: The numeric ID of the memory to delete (shown in recall/list results as #N).

    Returns:
        Confirmation of deletion, or error if not found.
    """
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return f"No memory found with ID #{memory_id}."

        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        return f"Deleted memory #{memory_id} — {row['category']}/{row['key']}: {row['value']}"
    finally:
        conn.close()


@safe_tool
def list_memories(category: Optional[str] = None, limit: int = 20) -> str:
    """List all stored memories, optionally filtered by category.

    Args:
        category: Optional category filter ('fact', 'preference', 'context', 'summary'). If omitted, shows all.
        limit: Maximum results to return (default 20).

    Returns:
        Formatted list of memories, or a message if none exist.
    """
    limit = max(1, min(limit, 100))

    conn = _get_conn()
    try:
        if category and category.strip():
            category = category.lower().strip()
            if category not in VALID_CATEGORIES:
                return f"Error: category must be one of {VALID_CATEGORIES}, got '{category}'."
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
            header = f"Memories in category '{category}'"
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            header = "All memories"

        if not rows:
            return "No memories stored yet." if not category else f"No memories in category '{category}'."

        # Group by category for readability
        by_cat: dict[str, list] = {}
        for row in rows:
            cat = row["category"]
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(row)

        lines = [f"{header} ({len(rows)} total):\n"]
        for cat in sorted(by_cat.keys()):
            lines.append(f"**{cat.upper()}:**")
            for row in by_cat[cat]:
                lines.append(
                    f"  [#{row['id']}] **{row['key']}**: {row['value']}"
                    f"  _(updated: {row['updated_at'][:16]})_"
                )
            lines.append("")
        return "\n".join(lines)
    finally:
        conn.close()