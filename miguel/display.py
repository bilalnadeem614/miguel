"""Rich-based terminal renderer for Miguel's streaming output."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

try:
    from agno.agent import RunEvent
except ImportError:
    RunEvent = None


console = Console()


def _matches_event(event_value, run_event_member) -> bool:
    """Match event values across enum/string representations."""
    candidates = {
        run_event_member,
        getattr(run_event_member, "value", None),
        getattr(run_event_member, "name", None),
        str(run_event_member),
    }
    event_as_str = str(event_value)
    return event_value in candidates or event_as_str in {str(c) for c in candidates if c is not None}


def render_stream(stream) -> None:
    """Render an Agno streaming response to the terminal with Rich formatting."""
    for event in stream:
        event_value = getattr(event, "event", None)
        event_name = str(event_value) if event_value is not None else ""
        content = getattr(event, "content", None)

        if RunEvent is None:
            # Fallback: just print content if RunEvent isn't available
            if content:
                console.print(content, end="")
            continue

        if _matches_event(event_value, RunEvent.run_started):
            pass  # Silent start

        elif _matches_event(event_value, RunEvent.run_content):
            if content:
                console.print(content, end="")

        elif _matches_event(event_value, RunEvent.tool_call_started):
            if hasattr(event, "tool") and event.tool:
                tool_name = getattr(event.tool, "tool_name", "unknown")
                tool_args = getattr(event.tool, "tool_args", "")
                console.print()
                console.print(
                    Panel(
                        f"[bold]{tool_name}[/bold]({tool_args})",
                        title="Tool Call",
                        style="yellow",
                        expand=False,
                    )
                )

        elif _matches_event(event_value, RunEvent.tool_call_completed):
            if hasattr(event, "tool") and event.tool:
                result = getattr(event.tool, "result", "")
                if result:
                    display_result = str(result)[:500]
                    console.print(
                        Panel(
                            display_result,
                            title="Result",
                            style="green",
                            expand=False,
                        )
                    )

        elif _matches_event(event_value, RunEvent.run_completed):
            console.print()  # Final newline

        elif content:
            # Catch-all fallback for unknown/new event types that still carry text.
            # Team completion events can carry full final content, which duplicates
            # already-streamed text from TeamRunContent.
            if event_name.endswith("RunCompleted") or event_name.endswith("ContentCompleted"):
                continue
            console.print(content, end="")


def render_stream_simple(stream) -> str:
    """Render a stream and return the full content as a string (for validation)."""
    content_parts = []
    for event in stream:
        content = getattr(event, "content", None)
        if not content:
            continue

        if not RunEvent:
            content_parts.append(content)
            continue

        if _matches_event(getattr(event, "event", None), RunEvent.run_content):
            content_parts.append(content)
        elif getattr(event, "event", None) is None:
            content_parts.append(content)
    return "".join(content_parts)


def print_banner() -> None:
    """Print the Miguel ASCII art banner."""
    banner = Text()
    banner.append(
        r"""
  __  __ _                  _
 |  \/  (_) __ _ _   _  ___| |
 | |\/| | |/ _` | | | |/ _ \ |
 | |  | | | (_| | |_| |  __/ |
 |_|  |_|_|\__, |\__,_|\___|_|
            |___/
""",
        style="bold cyan",
    )
    console.print(banner)
    console.print("  Self-improving AI agent. Type [bold]/help[/bold] for commands.\n")


def print_batch_header(batch_num: int, total: int) -> None:
    """Print a batch header."""
    console.print()
    console.rule(f"[bold]IMPROVEMENT BATCH {batch_num}/{total}[/bold]", style="cyan")
    console.print()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]{message}[/bold green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]{message}[/bold red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]{message}[/bold yellow]")
