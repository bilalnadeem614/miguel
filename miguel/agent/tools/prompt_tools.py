"""Tools for Miguel to inspect and modify its own system prompts safely."""

import ast
import re
from pathlib import Path

from miguel.agent.tools.error_utils import safe_tool

AGENT_DIR = Path(__file__).parent.parent
PROMPTS_PATH = AGENT_DIR / "prompts.py"


def _read_prompts_source() -> str:
    """Read the raw source of prompts.py."""
    if not PROMPTS_PATH.exists():
        raise FileNotFoundError(f"prompts.py not found at {PROMPTS_PATH}")
    return PROMPTS_PATH.read_text()


def _parse_prompt_sections(lines: list[str]) -> dict[str, list[str]]:
    """Parse prompt lines into named sections.
    
    Everything before the first '## ' heading goes into '_preamble'.
    Each '## Heading' starts a new section keyed by the heading text.
    """
    sections: dict[str, list[str]] = {}
    current = "_preamble"
    sections[current] = []

    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        else:
            sections[current].append(line)

    # Trim trailing empty strings from each section
    for key in sections:
        while sections[key] and sections[key][-1] == "":
            sections[key].pop()

    return sections


def _sections_to_lines(sections: dict[str, list[str]]) -> list[str]:
    """Convert sections dict back to a flat list of prompt lines."""
    lines: list[str] = []
    
    # Preamble first (no heading)
    if "_preamble" in sections:
        lines.extend(sections["_preamble"])
    
    # Then all other sections in insertion order
    for key, content in sections.items():
        if key == "_preamble":
            continue
        lines.append("")
        lines.append(f"## {key}")
        lines.extend(content)
    
    return lines


def _rebuild_prompts_py(lines: list[str]) -> str:
    """Rebuild the full prompts.py source with the given prompt lines."""
    # Build the list literal with proper indentation
    items = []
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace('"', '\\"')
        items.append(f'        "{escaped}",')
    
    # Handle f-strings: lines containing {AGENT_DIR} need to be f-strings
    final_items = []
    for item in items:
        if "{AGENT_DIR}" in item:
            # Convert regular string to f-string
            item = item.replace('        "', '        f"', 1)
        final_items.append(item)
    
    list_body = "\n".join(final_items)
    
    source = f'''"""System prompts for Miguel. The agent can modify this file to improve its own instructions."""

from pathlib import Path

AGENT_DIR = str(Path(__file__).parent.resolve())


def get_system_prompt() -> list[str]:
    """Return the system prompt as a list of instruction strings."""
    return [
{list_body}
    ]
'''
    return source


def _extract_prompt_lines(source: str) -> list[str]:
    """Extract prompt lines from prompts.py source using AST parsing.
    
    Returns list of strings, or raises ValueError if parsing fails.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"prompts.py has a syntax error: {e}")
    
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_system_prompt":
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.List):
                    for elt in child.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            lines.append(elt.value)
                        elif isinstance(elt, ast.JoinedStr):
                            # f-string: reconstruct approximate value
                            parts = []
                            for val in elt.values:
                                if isinstance(val, ast.Constant):
                                    parts.append(str(val.value))
                                elif isinstance(val, ast.FormattedValue):
                                    parts.append("{AGENT_DIR}")
                            lines.append("".join(parts))
    
    if not lines:
        raise ValueError("Could not parse prompt lines from prompts.py — no return list found in get_system_prompt()")
    
    return lines


@safe_tool
def get_prompt_sections() -> str:
    """List all sections in the current system prompt with their line counts.
    
    Returns a formatted overview of prompt sections so you can decide what to modify.
    """
    source = _read_prompts_source()
    lines = _extract_prompt_lines(source)
    sections = _parse_prompt_sections(lines)
    
    result = "## Current Prompt Sections\n\n"
    for key, content in sections.items():
        label = key if key != "_preamble" else "(Preamble — before any heading)"
        result += f"- **{label}**: {len(content)} lines\n"
    
    result += f"\n**Total lines:** {len(lines)}"
    return result


@safe_tool
def modify_prompt_section(section_name: str, new_content: str, action: str = "replace") -> str:
    """Modify a section of Miguel's system prompt.
    
    Args:
        section_name: The heading text (e.g. 'Core Behavior: Answering Questions') or '_preamble' for the intro.
        new_content: The new lines for this section, separated by newlines.
        action: One of 'replace' (overwrite section), 'append' (add lines to end), or 'add_new' (create new section).
    
    Returns:
        Success or error message.
    """
    if action not in ("replace", "append", "add_new"):
        return "Error: action must be 'replace', 'append', or 'add_new'"
    
    if not section_name or not section_name.strip():
        return "Error: section_name must not be empty."
    
    source = _read_prompts_source()
    lines = _extract_prompt_lines(source)
    sections = _parse_prompt_sections(lines)
    new_lines = new_content.split("\n")
    
    if action == "add_new":
        if section_name in sections:
            return f"Error: Section '{section_name}' already exists. Use action='replace' to overwrite it."
        sections[section_name] = new_lines
    elif action == "replace":
        if section_name not in sections:
            return f"Error: Section '{section_name}' not found. Available sections: {', '.join(sections.keys())}. Use action='add_new' to create a new section."
        sections[section_name] = new_lines
    elif action == "append":
        if section_name not in sections:
            return f"Error: Section '{section_name}' not found. Available sections: {', '.join(sections.keys())}"
        sections[section_name].extend(new_lines)
    
    # Rebuild
    rebuilt_lines = _sections_to_lines(sections)
    new_source = _rebuild_prompts_py(rebuilt_lines)
    
    # Validate syntax before writing
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return f"Error: Generated prompts.py has syntax error (aborting write): {e}"
    
    # Backup current file before writing
    backup_path = PROMPTS_PATH.with_suffix(".py.bak")
    backup_path.write_text(source)
    
    # Write the file
    PROMPTS_PATH.write_text(new_source)
    
    return f"Successfully {action}d section '{section_name}' in prompts.py ({len(new_lines)} lines)"