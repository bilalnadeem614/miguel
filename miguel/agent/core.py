"""Miguel agent factory. This file is the heart of what Miguel modifies.

Architecture: Miguel is an Agno Team in 'coordinate' mode.
- The Team (coordinator) has all self-improvement, memory, and planning tools
- Specialized sub-agents (Coder, Researcher, Analyst) handle focused tasks
- The coordinator decides when to use its own tools vs. delegate to sub-agents
- Sub-agents get fresh context windows, preventing context exhaustion
"""

from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team, TeamMode
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from pathlib import Path

from agno.db.sqlite import SqliteDb
from agno.tools.local_file_system import LocalFileSystemTools

from miguel.agent.config import MODEL_ID, USER_FILES_DIR
from miguel.agent.prompts import get_system_prompt
from miguel.agent.team import (
    create_coder_agent,
    create_researcher_agent,
    create_analyst_agent,
)
from miguel.agent.tools.capability_tools import (
    get_capabilities,
    get_next_capability,
    check_capability,
    add_capability,
)
from miguel.agent.tools.self_tools import (
    read_own_file,
    list_own_files,
    get_architecture,
    log_improvement,
)
from miguel.agent.tools.prompt_tools import (
    get_prompt_sections,
    modify_prompt_section,
)
from miguel.agent.tools.tool_creator import (
    create_tool,
    add_functions_to_tool,
)
from miguel.agent.tools.recovery_tools import (
    recover_backup,
    list_recovery_points,
    validate_agent_file,
    health_check,
)
from miguel.agent.tools.dep_tools import (
    add_dependency,
    list_dependencies,
)
from miguel.agent.tools.web_tools import (
    web_search,
    web_news,
    web_search_detailed,
    web_read,
)
from miguel.agent.tools.memory_tools import (
    remember,
    recall,
    forget,
    list_memories,
)
from miguel.agent.tools.planning_tools import (
    create_plan,
    add_task,
    update_task,
    show_plan,
    list_plans,
    get_next_task,
    remove_plan,
)
from miguel.agent.tools.file_analysis_tools import (
    analyze_csv,
    analyze_pdf,
    analyze_image,
    csv_query,
)
from miguel.agent.tools.api_tools import (
    http_request,
    api_get,
    api_post,
    api_quickstart,
)
from miguel.agent.tools.context_tools import (
    check_context,
    auto_compact,
)
from miguel.agent.tools.reddit_tools import (
    reddit_browse,
    reddit_read,
    reddit_search,
    reddit_post,
    reddit_comment,
    reddit_user,
)


# --- Coordinator tools: everything the main Miguel agent can use directly ---
COORDINATOR_TOOLS = [
    # Code execution & filesystem (coordinator can still do quick tasks directly)
    PythonTools(base_dir=Path(__file__).parent),
    ShellTools(base_dir=Path(__file__).parent),
    LocalFileSystemTools(target_directory=str(Path(__file__).parent)),
    LocalFileSystemTools(target_directory=USER_FILES_DIR),
    # Self-improvement & awareness
    get_capabilities, get_next_capability, check_capability, add_capability,
    read_own_file, list_own_files, get_architecture, log_improvement,
    get_prompt_sections, modify_prompt_section,
    create_tool, add_functions_to_tool,
    # Recovery & validation
    recover_backup, list_recovery_points, validate_agent_file, health_check,
    # Dependencies
    add_dependency, list_dependencies,
    # Web search & content reading
    web_search, web_news, web_search_detailed, web_read,
    # Memory (coordinator-only — persistent state)
    remember, recall, forget, list_memories,
    # Planning (coordinator-only — orchestration)
    create_plan, add_task, update_task, show_plan, list_plans, get_next_task, remove_plan,
    # File analysis (coordinator keeps for quick checks)
    analyze_csv, analyze_pdf, analyze_image, csv_query,
    # API tools (coordinator keeps for quick calls)
    http_request, api_get, api_post, api_quickstart,
    # Context awareness (coordinator-only — monitors context usage)
    check_context, auto_compact,
    # Reddit integration (browse, post, comment, search)
    reddit_browse, reddit_read, reddit_search, reddit_post, reddit_comment, reddit_user,
]


def create_agent(interactive: bool = False) -> Agent:
    """Create and return a plain Miguel Agent (no team delegation).

    Used as fallback or for simple batch operations where team overhead
    isn't needed. Returns a standard Agent, not a Team.
    """
    return Agent(
        name="Miguel",
        model=Gemini(
            id=MODEL_ID,
        ),
        instructions=get_system_prompt(),
        tools=COORDINATOR_TOOLS,
        markdown=True,
        **(
            {
                "db": SqliteDb(db_file=str(Path(__file__).parent / "miguel.db")),
                "add_history_to_context": True,
                "num_history_runs": 20,
            }
            if interactive
            else {}
        ),
    )


def create_team(interactive: bool = False) -> Team:
    """Create and return Miguel as an Agno Team with sub-agent delegation.

    The Team uses 'coordinate' mode:
    - Miguel (coordinator) receives user messages and decides how to respond
    - For simple tasks, Miguel uses its own tools directly
    - For complex/focused tasks, Miguel delegates to specialized sub-agents:
      * Coder: code generation, execution, file writing, debugging
      * Researcher: web search, API calls, information gathering
      * Analyst: data analysis, CSV/PDF/image processing, statistics

    Sub-agents get fresh context windows, preventing context exhaustion
    on complex multi-step tasks.

    Args:
        interactive: If True, enable conversation history for chat sessions.
                     If False (default), no history — used for improvement batches.
    """
    return Team(
        name="Miguel",
        model=Gemini(
            id=MODEL_ID,
        ),
        members=[
            create_coder_agent(),
            create_researcher_agent(),
            create_analyst_agent(),
        ],
        instructions=get_system_prompt(),
        tools=COORDINATOR_TOOLS,
        markdown=True,
        share_member_interactions=True,
        # Let coordinator determine what input each sub-agent receives
        determine_input_for_members=True,
        # Responses come back through the coordinator, not directly from sub-agents
        respond_directly=False,
        **(
            {
                "db": SqliteDb(db_file=str(Path(__file__).parent / "miguel.db")),
                "add_history_to_context": True,
                "num_history_runs": 20,
            }
            if interactive
            else {}
        ),
    )