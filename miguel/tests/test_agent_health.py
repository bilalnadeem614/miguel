"""Health checks run by the runner after each improvement batch."""

import ast
import json
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent / "agent"

REQUIRED_CAPABILITY_FIELDS = {"id", "title", "description", "priority", "status", "category", "added_at", "completed_at"}


def check_syntax() -> list[str]:
    """AST-parse all Python files in agent/. Returns list of errors (empty = pass)."""
    errors = []
    for py_file in AGENT_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError as e:
            errors.append(f"Syntax error in {py_file.relative_to(AGENT_DIR.parent)}: {e}")
    return errors


def check_capabilities_schema() -> list[str]:
    """Validate that capabilities.json has the correct structure."""
    errors = []
    caps_path = AGENT_DIR / "capabilities.json"

    if not caps_path.exists():
        return ["capabilities.json is missing"]

    try:
        data = json.loads(caps_path.read_text())
    except json.JSONDecodeError as e:
        return [f"capabilities.json is not valid JSON: {e}"]

    if not isinstance(data, dict):
        return ["capabilities.json root must be an object"]

    if "capabilities" not in data:
        errors.append("capabilities.json missing 'capabilities' key")
        return errors

    if not isinstance(data["capabilities"], list):
        errors.append("'capabilities' must be a list")
        return errors

    for i, cap in enumerate(data["capabilities"]):
        if not isinstance(cap, dict):
            errors.append(f"Capability at index {i} is not an object")
            continue
        missing = REQUIRED_CAPABILITY_FIELDS - set(cap.keys())
        if missing:
            errors.append(f"Capability '{cap.get('id', f'index {i}')}' missing fields: {missing}")

    return errors


def check_agent_creates() -> list[str]:
    """Try to import and instantiate the agent. Returns list of errors."""
    errors = []
    try:
        import importlib
        import sys

        # Clear cached modules so we get fresh imports
        modules_to_clear = [key for key in sys.modules if key.startswith("miguel.agent")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        import miguel.agent.core
        importlib.reload(miguel.agent.core)
        a = miguel.agent.core.create_agent()
        if a is None:
            errors.append("create_agent() returned None")
    except Exception as e:
        errors.append(f"Failed to create agent: {type(e).__name__}: {e}")
    return errors


def run_all_checks() -> list[str]:
    """Run all health checks. Returns combined list of errors."""
    errors = []
    errors.extend(check_syntax())
    errors.extend(check_capabilities_schema())
    if not errors:
        # Only try to create agent if syntax and schema pass
        errors.extend(check_agent_creates())
    return errors
