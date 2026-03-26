"""HTTP client for communicating with the Docker-sandboxed agent server."""

import json
import os
import sys
from types import SimpleNamespace

import httpx
from agno.run.agent import run_output_event_from_dict

CONTAINER_URL = "http://localhost:8420"
DEBUG_STREAM = os.getenv("MIGUEL_DEBUG_STREAM", "").lower() in {"1", "true", "yes", "on"}


def stream_from_container(prompt: str, session_id: str | None = None,
                          interactive: bool = False):
    """POST to the container's /run endpoint and yield reconstructed RunEvent objects.

    The yielded events are identical Agno dataclass instances, so render_stream()
    works without any changes.
    """
    with httpx.stream(
        "POST",
        f"{CONTAINER_URL}/run",
        json={"prompt": prompt, "session_id": session_id, "interactive": interactive},
        timeout=None,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                return

            try:
                data = json.loads(payload)
            except json.JSONDecodeError as e:
                print(f"[client] Skipping malformed SSE payload: {e}", file=sys.stderr)
                continue

            try:
                yield run_output_event_from_dict(data)
            except Exception as e:
                # Keep the stream usable across Agno event schema/version changes.
                if isinstance(data, dict):
                    event_name = str(data.get("event", ""))
                    content = data.get("content") or data.get("message") or ""
                    if isinstance(content, (dict, list)):
                        content = json.dumps(content, default=str)

                    if content:
                        # Team completion events often repeat full final content.
                        if event_name.endswith("RunCompleted") or event_name.endswith("ContentCompleted"):
                            continue
                        yield SimpleNamespace(
                            event=event_name or "raw_event",
                            content=content,
                            tool=data.get("tool"),
                        )
                        continue

                    # Agno Team events may not map to run_output_event_from_dict; this is expected.
                    if isinstance(e, ValueError) and "Unknown event type" in str(e):
                        if DEBUG_STREAM:
                            print(
                                f"[client] Ignoring unmapped event type: {event_name}",
                                file=sys.stderr,
                            )
                        continue

                if DEBUG_STREAM:
                    print(
                        f"[client] Failed to decode stream event: {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )


def reload_agent():
    """Tell the container to reload its agent modules."""
    resp = httpx.post(f"{CONTAINER_URL}/reload", timeout=30)
    resp.raise_for_status()
    return resp.json()


def container_healthy() -> bool:
    """Check if the container is running and responsive."""
    try:
        resp = httpx.get(f"{CONTAINER_URL}/health", timeout=5)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError):
        return False
