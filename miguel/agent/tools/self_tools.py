"""Tools for Miguel to inspect itself and log improvements."""

from datetime import datetime, timezone
from pathlib import Path

from miguel.agent.tools.error_utils import safe_tool

AGENT_DIR = Path(__file__).parent.parent
IMPROVEMENTS_PATH = AGENT_DIR / "improvements.md"
ARCHITECTURE_PATH = AGENT_DIR / "architecture.md"


@safe_tool
def read_own_file(file_path: str) -> str:
    """Read a file within the agent/ directory. Path must be relative to agent/ (e.g. 'core.py', 'tools/capability_tools.py')."""
    if not file_path or not file_path.strip():
        return "Error: file_path must not be empty."
    
    # Normalize and resolve path
    try:
        target = (AGENT_DIR / file_path).resolve()
    except (ValueError, OSError) as e:
        return f"Error: Invalid file path '{file_path}' — {e}"
    
    # Security check: must be within agent/
    agent_resolved = AGENT_DIR.resolve()
    if not str(target).startswith(str(agent_resolved)):
        return "Error: Cannot read files outside agent/ directory."
    
    if not target.exists():
        # Provide helpful suggestions
        parent = target.parent
        if parent.exists():
            siblings = [f.name for f in parent.iterdir() if f.is_file() and "__pycache__" not in str(f)]
            if siblings:
                return f"Error: File '{file_path}' not found. Files in {parent.relative_to(agent_resolved)}/: {', '.join(sorted(siblings))}"
        return f"Error: File '{file_path}' not found. Use list_own_files() to see available files."
    
    if not target.is_file():
        return f"Error: '{file_path}' is a directory, not a file. Use list_own_files() to browse."
    
    return target.read_text()


@safe_tool
def list_own_files() -> str:
    """List all files in the agent/ directory."""
    files = []
    for p in sorted(AGENT_DIR.rglob("*")):
        if p.is_file() and "__pycache__" not in str(p):
            files.append(str(p.relative_to(AGENT_DIR)))
    return "\n".join(files) if files else "No files found."


@safe_tool
def get_architecture() -> str:
    """Return Miguel's architecture map — a structured description of all components, their roles, and how they connect. Use this to explain how Miguel works."""
    if ARCHITECTURE_PATH.exists():
        return ARCHITECTURE_PATH.read_text()
    return "Error: architecture.md not found. Use list_own_files and read_own_file to inspect the codebase manually."


@safe_tool
def log_improvement(summary: str, files_changed: str) -> str:
    """Log an improvement to improvements.md. files_changed is a comma-separated list of filenames."""
    if not summary or not summary.strip():
        return "Error: summary must not be empty."
    if not files_changed or not files_changed.strip():
        return "Error: files_changed must not be empty."
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"\n### {timestamp}\n**Summary:** {summary}\n**Files changed:** {files_changed}\n"
    
    # Create the file if it doesn't exist
    if not IMPROVEMENTS_PATH.exists():
        IMPROVEMENTS_PATH.write_text("# Miguel Improvement Log\n\nEach entry records: batch number, timestamp, what changed, and why.\n\n---\n")
    
    with open(IMPROVEMENTS_PATH, "a") as f:
        f.write(entry)
    return f"Logged improvement: {summary}"