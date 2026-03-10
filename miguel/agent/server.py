"""FastAPI server that wraps Miguel's agent for Docker sandboxing.

Runs inside the container. Exposes the agent via HTTP with SSE streaming,
so the host-side CLI/runner can call agent.run() over the network.

Architecture:
- Batch mode (interactive=False): Uses plain Agent for focused improvement tasks
- Interactive mode (interactive=True): Uses Team with sub-agent delegation
"""

import importlib
import json
import sys

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Miguel Agent Server")

_agent = None           # Plain Agent for batch mode
_interactive_team = None # Team for interactive mode


class RunRequest(BaseModel):
    prompt: str
    session_id: str | None = None
    interactive: bool = False


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

    kwargs = dict(stream=True, stream_events=True)
    if req.session_id:
        kwargs["session_id"] = req.session_id

    stream = runner.run(req.prompt, **kwargs)

    def generate():
        for event in stream:
            try:
                data = json.dumps(event.to_dict(), default=str)
            except Exception:
                continue
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")