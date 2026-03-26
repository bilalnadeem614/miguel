"""Sub-agent definitions for Miguel's team architecture.

Miguel uses Agno's Team construct in 'coordinate' mode:
- The main Team (Miguel) acts as coordinator/orchestrator
- Specialized sub-agents handle focused tasks with fresh context
- The coordinator decides when to use its own tools vs. delegate

Sub-agents are lightweight — they share the same LLM model but get
focused tool subsets and instructions. This prevents context exhaustion
on complex tasks.
"""

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools
from agno.tools.local_file_system import LocalFileSystemTools
from pathlib import Path

from miguel.agent.config import MODEL_ID, USER_FILES_DIR

AGENT_DIR = Path(__file__).parent

def _make_model() -> Gemini:
    """Create a shared model config for sub-agents."""
    return Gemini(id=MODEL_ID)
# def _make_model() -> Claude:
#     """Create a shared model config for sub-agents."""
#     return Claude(id=MODEL_ID, retries=3, delay_between_retries=30, exponential_backoff=True)



def create_coder_agent() -> Agent:
    """Sub-agent specialized in writing, executing, and validating code.

    Handles: code generation, file writing, shell commands, debugging,
    project scaffolding, and code review tasks.
    """
    from miguel.agent.tools.recovery_tools import validate_agent_file, health_check

    return Agent(
        name="Coder",
        role="Code generation, execution, file writing, and debugging specialist",
        description=(
            "Delegate to Coder when the task involves writing code, creating files, "
            "executing Python or shell commands, debugging errors, generating project "
            "scaffolding, or any task that requires code output. Coder has access to "
            "Python execution, shell commands, and the local filesystem."
        ),
        model=_make_model(),
        instructions=[
            "You are Coder, a sub-agent of Miguel specialized in code tasks.",
            "Write clean, well-documented code. Execute and validate before returning.",
            "When writing files, use write_file with absolute paths.",
            f"Agent directory: {AGENT_DIR}",
            f"User files directory: {USER_FILES_DIR}",
            "Return your results clearly — the coordinator will relay them to the user.",
            "If you encounter errors, debug them and fix the root cause.",
        ],
        tools=[
            PythonTools(base_dir=AGENT_DIR),
            ShellTools(base_dir=AGENT_DIR),
            LocalFileSystemTools(target_directory=str(AGENT_DIR)),
            LocalFileSystemTools(target_directory=USER_FILES_DIR),
            validate_agent_file,
            health_check,
        ],
        markdown=True,
    )


def create_researcher_agent() -> Agent:
    """Sub-agent specialized in web research and information gathering.

    Handles: web searches, news lookup, API calls, fact-checking,
    reading webpage content, and synthesizing information from multiple sources.
    """
    from miguel.agent.tools.web_tools import web_search, web_news, web_search_detailed, web_read
    from miguel.agent.tools.api_tools import http_request, api_get, api_post, api_quickstart

    return Agent(
        name="Researcher",
        role="Web research, information retrieval, and API integration specialist",
        description=(
            "Delegate to Researcher when the task involves searching the web, "
            "looking up current information, researching topics, reading webpage content, "
            "calling external APIs, fact-checking, or gathering data from multiple online "
            "sources. Researcher has web search, page reading, and HTTP client tools."
        ),
        model=_make_model(),
        instructions=[
            "You are Researcher, a sub-agent of Miguel specialized in finding information.",
            "Use web search for general queries, news search for current events.",
            "Use web_read to fetch and read full webpage content after finding URLs via search.",
            "Use API tools for structured data from web services.",
            "Always cite sources. Synthesize information clearly.",
            "Return organized, well-structured findings to the coordinator.",
            "If first search doesn't work, rephrase and try again.",
        ],
        tools=[
            web_search,
            web_news,
            web_search_detailed,
            web_read,
            http_request,
            api_get,
            api_post,
            api_quickstart,
        ],
        markdown=True,
    )


def create_analyst_agent() -> Agent:
    """Sub-agent specialized in data and file analysis.

    Handles: CSV/Excel analysis, PDF extraction, image analysis,
    data querying, statistical summaries, and report generation.
    """
    from miguel.agent.tools.file_analysis_tools import (
        analyze_csv, analyze_pdf, analyze_image, csv_query,
    )

    return Agent(
        name="Analyst",
        role="Data analysis, file processing, and statistical analysis specialist",
        description=(
            "Delegate to Analyst when the task involves analyzing CSV/Excel files, "
            "extracting text from PDFs, examining images, running data queries, "
            "computing statistics, or generating reports from data. Analyst has "
            "pandas-powered data tools and file analysis capabilities."
        ),
        model=_make_model(),
        instructions=[
            "You are Analyst, a sub-agent of Miguel specialized in data and file analysis.",
            "Start with overview analysis, then drill into specifics.",
            "Use analyze_csv for initial overview, csv_query for specific questions.",
            "Present findings with clear tables, statistics, and insights.",
            "Return well-formatted analysis results to the coordinator.",
            f"User files directory: {USER_FILES_DIR}",
        ],
        tools=[
            analyze_csv,
            analyze_pdf,
            analyze_image,
            csv_query,
            PythonTools(base_dir=AGENT_DIR),
            LocalFileSystemTools(target_directory=USER_FILES_DIR),
        ],
        markdown=True,
    )