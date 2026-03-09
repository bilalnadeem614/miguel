"""Tools for Miguel to inspect itself and log improvements."""

from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent
IMPROVEMENTS_PATH = AGENT_DIR / "improvements.md"
ARCHITECTURE_PATH = AGENT_DIR / "architecture.md"


def read_own_file(file_path: str) -> str:
    """Read a file within the agent/ directory. Path must be relative to agent/ (e.g. 'core.py', 'tools/capability_tools.py')."""
    target = (AGENT_DIR / file_path).resolve()
    if not str(target).startswith(str(AGENT_DIR.resolve())):
        return "Error: Cannot read files outside agent/ directory."
    if not target.exists():
        return f"Error: File '{file_path}' not found."
    return target.read_text()


def list_own_files() -> str:
    """List all files in the agent/ directory."""
    files = []
    for p in sorted(AGENT_DIR.rglob("*")):
        if p.is_file() and "__pycache__" not in str(p):
            files.append(str(p.relative_to(AGENT_DIR)))
    return "\n".join(files) if files else "No files found."


def get_architecture() -> str:
    """Return Miguel's architecture map — a structured description of all components, their roles, and how they connect. Use this to explain how Miguel works."""
    if ARCHITECTURE_PATH.exists():
        return ARCHITECTURE_PATH.read_text()
    return "Error: architecture.md not found. Use list_own_files and read_own_file to inspect the codebase manually."


def log_improvement(summary: str, files_changed: str) -> str:
    """Log an improvement to improvements.md. files_changed is a comma-separated list of filenames."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"\n### {timestamp}\n**Summary:** {summary}\n**Files changed:** {files_changed}\n"
    with open(IMPROVEMENTS_PATH, "a") as f:
        f.write(entry)
    return f"Logged improvement: {summary}"