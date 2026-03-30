"""Agno-compatible tools for markdown user preferences.

These tools expose the preferences system to Miguel's coordinator so it can
load, update, and create domain-specific preference files as part of normal
task execution.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from miguel.agent.tools.error_utils import safe_tool
from miguel.agent.tools.self_tools import log_improvement
from miguel.agent.tools.session_cache import clear_all_preferences_cache
from miguel.core.preferences import (
    create_preference_file,
    get_relevant_preferences,
    load_preferences,
    update_preference,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PREFERENCES_DIR = REPO_ROOT / "preferences"


def _infer_preference_from_feedback(feedback: str, domain_hint: str = "main") -> tuple[str, str, str] | None:
    """Infer a preference candidate from natural-language feedback.

    Returns:
        (domain, key, value) when a clear preference is detected, else None.
    """
    text = (feedback or "").strip().lower()
    if not text:
        return None

    if "camelcase" in text:
        domain = "python" if "python" in text or domain_hint == "python" else domain_hint
        return (domain, "variable_style", "camelCase")
    if "snake_case" in text or "snake case" in text:
        domain = "python" if "python" in text or domain_hint == "python" else domain_hint
        return (domain, "variable_style", "snake_case")
    if "react" in text:
        return ("js", "framework", "React.js")
    if "vue" in text:
        return ("js", "framework", "Vue.js")
    if "angular" in text:
        return ("js", "framework", "Angular")

    framework_match = re.search(r"use\s+([a-z0-9_.-]+)\s+(?:for|as)\s+framework", text)
    if framework_match:
        return ("js", "framework", framework_match.group(1))

    naming_match = re.search(r"prefer\s+([a-z_]+)\s+(?:for\s+)?(?:variable|variables|naming)", text)
    if naming_match:
        style = naming_match.group(1)
        domain = "python" if "python" in text or domain_hint == "python" else domain_hint
        return (domain, "variable_style", style)

    return None


def _is_repeated_preference(domain: str, key: str, value: str) -> bool:
    """Check if feedback repeats an already stored preference value."""
    existing = load_preferences(domain)
    existing_value = existing.get(key)
    if existing_value is None:
        return False
    return existing_value.strip().lower() == value.strip().lower()


def _commit_preference_change(domain: str, key: str, value: str, reason: str) -> str:
    """Best-effort git add/commit for preference updates.

    Returns a short status message suitable for tool output.
    """
    normalized_domain = domain.strip().lower() if domain else "main"
    if normalized_domain in {"main", "general", "default"}:
        file_name = "mainPreferences.md"
    elif normalized_domain in {"python", "py"}:
        file_name = "pythonPref.md"
    elif normalized_domain in {"javascript", "js", "react"}:
        file_name = "jsPref.md"
    else:
        safe = "".join(ch for ch in normalized_domain if ch.isalnum() or ch in {"_", "-"}) or "main"
        file_name = f"{safe}Pref.md"

    pref_file = PREFERENCES_DIR / file_name
    rel_pref_file = pref_file.relative_to(REPO_ROOT)

    try:
        add_cmd = ["git", "-C", str(REPO_ROOT), "add", str(rel_pref_file)]
        add_result = subprocess.run(add_cmd, capture_output=True, text=True)
        if add_result.returncode != 0:
            return f"Git add skipped: {add_result.stderr.strip() or add_result.stdout.strip() or 'unknown error'}"

        status_cmd = ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", str(rel_pref_file)]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)
        if status_result.returncode != 0:
            return f"Git status check failed: {status_result.stderr.strip() or status_result.stdout.strip() or 'unknown error'}"
        if not status_result.stdout.strip():
            return "Git commit skipped: no file changes to commit."

        message = f"prefs({normalized_domain}): set {key}={value} | why: {reason}"
        commit_cmd = ["git", "-C", str(REPO_ROOT), "commit", "-m", message]
        commit_result = subprocess.run(commit_cmd, capture_output=True, text=True)
        if commit_result.returncode != 0:
            stderr = commit_result.stderr.strip() or commit_result.stdout.strip()
            if "nothing to commit" in stderr.lower():
                return "Git commit skipped: nothing to commit."
            return f"Git commit failed: {stderr or 'unknown error'}"

        first_line = commit_result.stdout.strip().splitlines()[0] if commit_result.stdout.strip() else "commit created"
        return f"Git commit created: {first_line}"
    except Exception as exc:
        logger.exception("Git commit step failed for preference update: %s", exc)
        return f"Git commit skipped: {type(exc).__name__}: {exc}"


@safe_tool
def load_user_preferences_tool(domain: str = "main") -> str:
    """Load user preferences and return prompt-ready formatted output.

    Use this at the start of tasks so Miguel applies user preferences before
    planning or answering. If domain is "main", all relevant preferences are
    inferred and returned using the domain text as context.

    Args:
        domain: Optional preference domain such as "main", "python", "js",
            or any custom domain.

    Returns:
        Formatted markdown with preference entries for prompt injection.
    """
    domain = (domain or "main").strip()

    if domain.lower() in {"main", "general", "default"}:
        formatted = get_relevant_preferences("main")
    else:
        prefs = load_preferences(domain)
        if not prefs:
            return f"No preferences found for domain '{domain}'."
        lines = [f"## Preferences: {domain}"]
        for key, value in sorted(prefs.items()):
            lines.append(f"- {key}: {value}")
        formatted = "\n".join(lines)

    logger.info("Preferences loaded for domain=%s", domain)
    return formatted


@safe_tool
def update_user_preferences_tool(domain: str, key: str, value: str, reason: str) -> str:
    """Update a user preference and persist it to markdown, memory, and git.

    This tool updates the selected domain file inside preferences/, mirrors the
    update to persistent memory via the core preference system, logs a
    self-reflection improvement entry (what + why), and attempts a best-effort
    git commit for traceability.

    Args:
        domain: Preference domain (e.g. "main", "python", "js", "typescript").
        key: Preference key to create or update.
        value: New preference value.
        reason: Why the preference was changed.

    Returns:
        Multi-line status output with update, reflection log, and git commit status.
    """
    update_preference(domain=domain, key=key, value=value, reason=reason)
    clear_all_preferences_cache()  # Invalidate session cache when preferences change

    what = f"Updated preference '{key}' in domain '{domain}' to '{value}'"
    why = f"Reason: {reason}"
    reflection = log_improvement(summary=f"{what}. {why}", files_changed="preferences/*.md, miguel/core/preferences.py")
    commit_status = _commit_preference_change(domain=domain, key=key, value=value, reason=reason)

    logger.info("Preference updated domain=%s key=%s why=%s", domain, key, reason)
    return "\n".join([
        f"Preference updated: domain={domain}, key={key}, value={value}",
        f"Reflection log: {reflection}",
        f"Git: {commit_status}",
        f"What: {what}",
        f"Why: {why}",
    ])


@safe_tool
def create_new_preference_domain_tool(domain: str) -> str:
    """Create a new domain preference markdown file under preferences/.

    Use this when the user introduces a new domain (for example: "typescript",
    "devops", or "data-science") and wants dedicated preferences tracked.

    Args:
        domain: New preference domain name.

    Returns:
        Success/failure message and reflection details with what/why.
    """
    created = create_preference_file(domain)
    clear_all_preferences_cache()  # Invalidate cache when new domain is created
    domain_clean = (domain or "").strip().lower()
    if domain_clean in {"main", "general", "default"}:
        file_name = "mainPreferences.md"
    elif domain_clean in {"python", "py"}:
        file_name = "pythonPref.md"
    elif domain_clean in {"javascript", "js", "react"}:
        file_name = "jsPref.md"
    else:
        safe = "".join(ch for ch in domain_clean if ch.isalnum() or ch in {"_", "-"}) or "main"
        file_name = f"{safe}Pref.md"

    if created:
        what = f"Created new preference domain file for '{domain}'"
        why = "To support domain-specific user behavior and prompt control"
        reflection = log_improvement(summary=f"{what}. Reason: {why}", files_changed=f"preferences/{file_name}")
        logger.info("Created new preference domain: %s", domain)
        return "\n".join([
            f"Created preference domain '{domain}'.",
            f"File: preferences/{file_name}",
            f"Reflection log: {reflection}",
            f"What: {what}",
            f"Why: {why}",
        ])

    logger.info("Preference domain already exists or failed creation: %s", domain)
    return f"Preference domain '{domain}' already exists or could not be created."


@safe_tool
def reflect_on_interaction_preferences_tool(
    interaction_summary: str,
    user_feedback: str = "",
    domain_hint: str = "main",
    auto_apply: bool = False,
) -> str:
    """Reflect on an interaction and detect new or updated user preferences.

    This tool is designed for Miguel's feedback loop. It asks the explicit
    reflection question and detects preference signals from interaction summary
    and user feedback. When a repeated or clear preference is detected, it can
    suggest an update or apply it automatically.

    Reflection question:
        "Did this interaction reveal any new or updated user preference?"

    Args:
        interaction_summary: Short summary of what happened in the interaction.
        user_feedback: Optional direct feedback from the user.
        domain_hint: Preferred domain to use if detection is ambiguous.
        auto_apply: If True, apply the inferred preference via
            update_user_preferences_tool. If False, return a suggestion.

    Returns:
        A reflection report with detected preference signal and suggested/applied action.
    """
    reflection_question = "Did this interaction reveal any new or updated user preference?"
    signal_text = "\n".join(x for x in [interaction_summary.strip(), user_feedback.strip()] if x).strip()
    if not signal_text:
        return "\n".join([
            f"Reflection question: {reflection_question}",
            "Answer: No clear signal (missing interaction summary/feedback).",
        ])

    inferred = _infer_preference_from_feedback(signal_text, domain_hint=domain_hint)
    if not inferred:
        return "\n".join([
            f"Reflection question: {reflection_question}",
            "Answer: No clear preference signal detected.",
        ])

    domain, key, value = inferred
    repeated = _is_repeated_preference(domain=domain, key=key, value=value)
    reason = (
        "Detected repeated preference signal from interaction/user feedback"
        if repeated
        else "Detected new or updated preference signal from interaction/user feedback"
    )

    what = f"Preference signal detected: domain={domain}, key={key}, value={value}"
    why = reason

    if auto_apply:
        result = update_user_preferences_tool(domain=domain, key=key, value=value, reason=reason)
        return "\n".join([
            f"Reflection question: {reflection_question}",
            f"Answer: Yes ({'repeated' if repeated else 'new/updated'} signal).",
            f"What: {what}",
            f"Why: {why}",
            "Action: Applied preference update.",
            result,
        ])

    return "\n".join([
        f"Reflection question: {reflection_question}",
        f"Answer: Yes ({'repeated' if repeated else 'new/updated'} signal).",
        f"What: {what}",
        f"Why: {why}",
        "Action: Suggest applying update_user_preferences_tool with detected values.",
        f"Suggested call: update_user_preferences_tool(domain='{domain}', key='{key}', value='{value}', reason='{reason}')",
    ])
