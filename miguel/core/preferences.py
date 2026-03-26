"""Markdown-based preference storage for Miguel.

This module manages user preferences under the repository-level preferences/
folder and provides helpers to load, update, and retrieve prompt-ready
preference snippets.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Dict

try:
    from miguel.agent.tools.memory_tools import recall, remember
except Exception:  # pragma: no cover - optional dependency protection
    recall = None
    remember = None

logger = logging.getLogger(__name__)

_PREF_LOCK = threading.RLock()
_BULLET_PREF_PATTERN = re.compile(r"^\s*-\s*([A-Za-z0-9_\-.]+)\s*:\s*(.+?)\s*$")


def _repo_root() -> Path:
    """Return the repository root based on module location."""
    return Path(__file__).resolve().parents[2]


def _preferences_dir() -> Path:
    """Return the preferences directory path in the project root."""
    return _repo_root() / "preferences"


def _normalize_domain(domain: str | None) -> str:
    """Normalize domain names and aliases into canonical domain ids."""
    if not domain or not domain.strip():
        return "main"

    cleaned = domain.strip().lower()
    alias_map = {
        "main": "main",
        "general": "main",
        "default": "main",
        "python": "python",
        "py": "python",
        "javascript": "js",
        "js": "js",
        "react": "js",
    }
    if cleaned in alias_map:
        return alias_map[cleaned]

    # Keep only safe filename characters for domain-specific files.
    return re.sub(r"[^a-z0-9_-]+", "", cleaned) or "main"


def _preference_file_name(domain: str) -> str:
    """Map a normalized domain to the expected markdown filename."""
    if domain == "main":
        return "mainPreferences.md"
    if domain == "python":
        return "pythonPref.md"
    if domain == "js":
        return "jsPref.md"
    return f"{domain}Pref.md"


def _preference_file_path(domain: str) -> Path:
    """Build the absolute preference markdown path for a domain."""
    normalized = _normalize_domain(domain)
    return _preferences_dir() / _preference_file_name(normalized)


def _domain_title(domain: str) -> str:
    """Human-friendly title text for markdown headers."""
    if domain == "main":
        return "Main Preferences"
    if domain == "python":
        return "Python Preferences"
    if domain == "js":
        return "JavaScript and React Preferences"
    return f"{domain.capitalize()} Preferences"


def _default_template(domain: str) -> str:
    """Return default markdown contents for a domain preference file."""
    title = _domain_title(domain)
    return (
        f"# {title}\n\n"
        "- key: value\n"
        "- another_preference: description\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically to avoid partially-written files."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _parse_preferences(md_text: str) -> Dict[str, str]:
    """Parse markdown bullet preferences into a dictionary."""
    parsed: Dict[str, str] = {}
    for line in md_text.splitlines():
        match = _BULLET_PREF_PATTERN.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key:
            parsed[key] = value
    return parsed


def _sync_preference_to_memory(domain: str, key: str, value: str, reason: str) -> None:
    """Best-effort sync to Miguel persistent memory, if available."""
    if remember is None:
        logger.debug("remember() tool not available; skipping memory sync")
        return

    memory_key = f"preference.{domain}.{key}"
    memory_value = f"{value} (reason: {reason})"
    try:
        remember(memory_key, memory_value, category="preference")
    except Exception as exc:
        logger.exception("Failed to sync preference to memory for %s: %s", memory_key, exc)


def create_preference_file(domain: str) -> bool:
    """Create a markdown preference file for a domain if it does not exist.

    Args:
        domain: Domain name such as "main", "python", "js", or "typescript".

    Returns:
        True if the file was created, False if it already existed or failed.
    """
    normalized = _normalize_domain(domain)
    pref_dir = _preferences_dir()
    target = _preference_file_path(normalized)

    with _PREF_LOCK:
        try:
            pref_dir.mkdir(parents=True, exist_ok=True)
            if target.exists():
                return False
            _atomic_write(target, _default_template(normalized))
            logger.info("Created preference file: %s", target)
            return True
        except Exception as exc:
            logger.exception("Failed creating preference file for domain '%s': %s", normalized, exc)
            return False


def load_preferences(domain: str = "main") -> dict:
    """Load preferences for a domain from markdown.

    Args:
        domain: Domain name. Defaults to "main".

    Returns:
        Dictionary of parsed key/value preferences. Returns empty dict on failure.
    """
    normalized = _normalize_domain(domain)
    target = _preference_file_path(normalized)

    with _PREF_LOCK:
        try:
            if not target.exists():
                created = create_preference_file(normalized)
                if not created and not target.exists():
                    logger.warning("Preference file unavailable for domain: %s", normalized)
                    return {}

            content = target.read_text(encoding="utf-8")
            parsed = _parse_preferences(content)
            logger.debug("Loaded %d preferences from %s", len(parsed), target)
            return parsed
        except Exception as exc:
            logger.exception("Failed loading preferences for domain '%s': %s", normalized, exc)
            return {}


def update_preference(domain: str, key: str, value: str, reason: str):
    """Create or update a preference key in a domain markdown file.

    The update is persisted to the markdown file and mirrored to persistent memory.

    Args:
        domain: Preference domain (e.g. "python", "js", "main").
        key: Preference key.
        value: Preference value.
        reason: Why this preference was added or changed.
    """
    normalized = _normalize_domain(domain)
    key = (key or "").strip()
    value = (value or "").strip()
    reason = (reason or "").strip()

    if not key:
        raise ValueError("Preference key must not be empty")
    if not value:
        raise ValueError("Preference value must not be empty")
    if not reason:
        raise ValueError("Reason must not be empty")

    target = _preference_file_path(normalized)

    with _PREF_LOCK:
        try:
            if not target.exists():
                create_preference_file(normalized)

            current_text = target.read_text(encoding="utf-8") if target.exists() else _default_template(normalized)
            lines = current_text.splitlines()

            updated = False
            key_prefix = f"- {key}:"
            for index, line in enumerate(lines):
                if line.strip().startswith(key_prefix):
                    lines[index] = f"- {key}: {value}"
                    updated = True
                    break

            if not updated:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(f"- {key}: {value}")

            new_text = "\n".join(lines).rstrip() + "\n"
            _atomic_write(target, new_text)
            _sync_preference_to_memory(normalized, key, value, reason)

            logger.info(
                "Updated preference domain=%s key=%s reason=%s",
                normalized,
                key,
                reason,
            )
        except Exception as exc:
            logger.exception(
                "Failed updating preference domain=%s key=%s: %s",
                normalized,
                key,
                exc,
            )
            raise


def get_relevant_preferences(task_description: str) -> str:
    """Return formatted relevant preferences for prompt injection.

    Relevance is inferred from keywords in task_description.

    Args:
        task_description: Natural language task text.

    Returns:
        A markdown-formatted preference block suitable for prompt injection.
    """
    text = (task_description or "").lower()
    domains = ["main"]

    if any(token in text for token in ["python", "py", "pandas", "fastapi", "django"]):
        domains.append("python")
    if any(token in text for token in ["javascript", "typescript", "react", "node", "frontend", "js", "tsx"]):
        domains.append("js")
        if "typescript" in text or "tsx" in text or "ts " in text:
            domains.append("typescript")

    seen = set()
    ordered_domains = []
    for domain in domains:
        if domain not in seen:
            ordered_domains.append(domain)
            seen.add(domain)

    sections = ["## Relevant Preferences"]
    for domain in ordered_domains:
        prefs = load_preferences(domain)
        if not prefs:
            continue
        sections.append(f"### {domain}")
        for key, value in sorted(prefs.items()):
            sections.append(f"- {key}: {value}")

    if recall is not None:
        try:
            remembered = recall("preference.", category="preference", limit=5)
            if remembered and not remembered.startswith("No memories") and not remembered.startswith("Error"):
                sections.append("### remembered")
                sections.append(remembered)
        except Exception as exc:
            logger.exception("Failed recalling preferences from memory: %s", exc)

    if len(sections) == 1:
        sections.append("- No preferences found.")

    return "\n".join(sections)
