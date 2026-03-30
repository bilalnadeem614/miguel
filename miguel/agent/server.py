"""FastAPI server that wraps Miguel's agent for Docker sandboxing.

Runs inside the container. Exposes the agent via HTTP with SSE streaming,
so the host-side CLI/runner can call agent.run() over the network.

Architecture:
- Batch mode (interactive=False): Uses plain Agent for focused improvement tasks
- Interactive mode (interactive=True): Uses Team with sub-agent delegation
"""

import importlib
import json
import logging
import re
import sys

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from miguel.core.preferences import create_preference_file, get_relevant_preferences

app = FastAPI(title="Miguel Agent Server")

logger = logging.getLogger(__name__)

_agent = None           # Plain Agent for batch mode
_interactive_team = None # Team for interactive mode


class RunRequest(BaseModel):
    prompt: str
    session_id: str | None = None
    interactive: bool = False


_KNOWN_DOMAIN_KEYWORDS = {
    "python": "python",
    "javascript": "js",
    "js": "js",
    "react": "js",
    "typescript": "typescript",
    "ts": "typescript",
    "node": "js",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "java": "java",
    "kotlin": "kotlin",
    "swift": "swift",
    "php": "php",
    "ruby": "ruby",
    "csharp": "csharp",
    "c#": "csharp",
    "devops": "devops",
    "terraform": "terraform",
    "kubernetes": "kubernetes",
    "docker": "docker",
    "sql": "sql",
}


def _extract_domains_from_prompt(prompt: str) -> list[str]:
    """Infer likely preference domains from user task text."""
    text = (prompt or "").lower()
    found: list[str] = []

    def _contains_keyword(haystack: str, keyword: str) -> bool:
        # Match whole-token style keywords to avoid false positives like js in json.
        pattern = rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])"
        return re.search(pattern, haystack) is not None

    for keyword, domain in _KNOWN_DOMAIN_KEYWORDS.items():
        if _contains_keyword(text, keyword) and domain not in found:
            found.append(domain)

    # Allow explicit pattern like "domain: <name>" or "preferences for <name>"
    for pattern in [r"domain\s*:\s*([a-z0-9_-]+)", r"preferences\s+for\s+([a-z0-9_-]+)"]:
        for match in re.findall(pattern, text):
            safe = re.sub(r"[^a-z0-9_-]+", "", match)
            if safe and safe not in found:
                found.append(safe)

    return found


def _build_preference_augmented_prompt(prompt: str, session_id: str | None = None) -> str:
    """Load relevant preferences (cached per session) and prepend them to task context.

    Also auto-creates missing domain preference files when new domains are
    inferred from the task prompt.
    
    Preferences are cached per session_id to avoid redundant recomputation.
    """
    from miguel.agent.tools.session_cache import get_cached_preferences, set_cached_preferences
    
    # Check if preferences are already cached for this session
    if session_id:
        cached = get_cached_preferences(session_id)
        if cached is not None:
            return (
                "[PREFERENCE CONTEXT - APPLY FIRST]\n"
                f"{cached}\n\n"
                "[USER TASK]\n"
                f"{prompt}"
            )
    
    # Not cached yet — compute preferences once
    domains = _extract_domains_from_prompt(prompt)
    for domain in domains:
        if domain in {"main", "python", "js"}:
            continue
        try:
            created = create_preference_file(domain)
            if created:
                logger.info("Auto-created preference domain file for inferred domain: %s", domain)
        except Exception as exc:
            logger.exception("Failed auto-creating preference domain '%s': %s", domain, exc)

    preferences = get_relevant_preferences(prompt)
    
    # Cache the computed preferences for this session
    if session_id:
        set_cached_preferences(session_id, preferences)
    
    return (
        "[PREFERENCE CONTEXT - APPLY FIRST]\n"
        f"{preferences}\n\n"
        "[USER TASK]\n"
        f"{prompt}"
    )


def _create_agents():
    """Clear cached modules and create fresh agent/team instances."""
    global _agent, _interactive_team

    modules_to_clear = [k for k in sys.modules if k.startswith("miguel.agent") and k != "miguel.agent.server"]
    for mod in modules_to_clear:
        del sys.modules[mod]

    import miguel.agent.core
    importlib.reload(miguel.agent.core)

    # Batch mode: plain Agent (simpler, faster, less overhead)
    _agent = miguel.agent.core.create_agent(interactive=False)
    # Interactive mode: Team with sub-agent delegation
    _interactive_team = miguel.agent.core.create_team(interactive=True)


@app.on_event("startup")
def startup():
    _create_agents()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reload")
def reload_agent():
    _create_agents()
    return {"status": "reloaded"}


@app.post("/run")
def run(req: RunRequest):
    # Use Team for interactive, plain Agent for batch
    runner = _interactive_team if req.interactive else _agent
    effective_prompt = _build_preference_augmented_prompt(req.prompt, session_id=req.session_id)

    kwargs = dict(stream=True, stream_events=True)
    if req.session_id:
        kwargs["session_id"] = req.session_id

    stream = runner.run(effective_prompt, **kwargs)

    def generate():
        for event in stream:
            try:
                data = json.dumps(event.to_dict(), default=str)
            except Exception as e:
                data = json.dumps(
                    {
                        "event": "server_stream_error",
                        "content": f"[server] Failed to serialize event: {type(e).__name__}: {e}",
                    }
                )
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")