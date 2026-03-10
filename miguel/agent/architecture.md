# Miguel Architecture Map

## Overview
Miguel is a self-improving AI agent built on the **Agno** framework with **Claude** (Anthropic) as its LLM backbone. It can read, modify, and extend its own source code.

**Architecture: Agno Team in `coordinate` mode** — Miguel operates as a coordinator with three specialized sub-agents. The coordinator handles orchestration, planning, memory, and self-improvement directly, and delegates focused tasks (coding, research, data analysis) to sub-agents that get fresh context windows.

## Directory Structure

```
agent/
├── __init__.py          # Package entry point — exports create_agent() and create_team()
├── core.py              # Agent/Team factory — creates coordinator + sub-agents
├── team.py              # Sub-agent definitions — Coder, Researcher, Analyst
├── config.py            # Settings — model ID, version, constants
├── prompts.py           # System prompt builder — defines Miguel's personality & instructions
├── server.py            # FastAPI server — batch mode (Agent) + interactive mode (Team)
├── architecture.md      # This file — self-describing architecture map
├── capabilities.json    # Checklist of capabilities (checked/unchecked)
├── improvements.md      # Log of all self-improvements made
├── memory.db            # SQLite database for persistent memory across sessions
├── planning.db          # SQLite database for task plans and progress tracking
└── tools/
    ├── __init__.py              # Empty — makes tools/ a Python package
    ├── error_utils.py           # Error handling foundation — decorators, safe writes, validation
    ├── api_tools.py             # HTTP client and API integrations — REST calls, auth, quickstart services
    ├── capability_tools.py      # Tools for managing the capability checklist
    ├── dep_tools.py             # Dependency management tools
    ├── file_analysis_tools.py   # File analysis — PDF, CSV/Excel, images, structured data
    ├── memory_tools.py          # Persistent memory — store/recall facts, preferences, context
    ├── planning_tools.py        # Structured task planning — plans, tasks, dependencies, progress
    ├── prompt_tools.py          # Tools for safely inspecting and modifying the system prompt
    ├── recovery_tools.py        # Error recovery and diagnostic tools
    ├── self_tools.py            # Tools for self-inspection and logging improvements
    ├── tool_creator.py          # Tools for creating new tools and auto-registering them
    └── web_tools.py             # Web search and information retrieval via DuckDuckGo
```

## Team Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Miguel (Coordinator)                │
│              Agno Team — coordinate mode             │
│                                                      │
│  Tools: 44 (self-improvement, memory, planning,      │
│         web search, file analysis, API, filesystem)   │
│                                                      │
│  Decides: handle directly OR delegate to sub-agent    │
├──────────┬──────────────────┬────────────────────────┤
│          │                  │                        │
│  ┌───────▼──────┐  ┌───────▼──────┐  ┌─────────────▼─┐
│  │    Coder     │  │  Researcher  │  │    Analyst     │
│  │  (6 tools)   │  │  (7 tools)   │  │   (6 tools)   │
│  │              │  │              │  │               │
│  │ Python exec  │  │ Web search   │  │ CSV/Excel     │
│  │ Shell cmds   │  │ News search  │  │ PDF extract   │
│  │ File write   │  │ HTTP client  │  │ Image analyze │
│  │ Validation   │  │ API calls    │  │ Pandas query  │
│  └──────────────┘  └──────────────┘  └───────────────┘
```

**How it works:**
1. User message arrives at the coordinator (Miguel)
2. Coordinator decides: use own tools directly, or delegate to a sub-agent?
3. For delegation: coordinator uses `delegate_task_to_member` (auto-provided by Agno)
4. Sub-agent runs with fresh context, returns result to coordinator
5. Coordinator synthesizes and responds to user

**When to delegate:**
- **Coder**: Large code generation, project scaffolding, debugging sessions
- **Researcher**: Multi-source web research, thorough fact-checking
- **Analyst**: Complex data analysis, multi-step CSV processing, report generation

**When coordinator handles directly:**
- Quick answers, self-improvement, memory operations, planning, simple tool calls

## Key Components

### core.py — The Heart
- `create_agent()` — Factory for a plain `Agent` (used in batch mode for self-improvement)
- `create_team()` — Factory for the `Team` with coordinator + 3 sub-agents (used in interactive mode)
- Both share the same `COORDINATOR_TOOLS` list (44 tools)
- Wires together: model, instructions, tools, sub-agents, and history/DB configuration

### team.py — Sub-Agent Definitions
- `create_coder_agent()` — Code generation, execution, file writing, debugging
- `create_researcher_agent()` — Web search, API calls, information gathering
- `create_analyst_agent()` — Data analysis, CSV/PDF/image processing, statistics
- Each sub-agent has focused tool subsets and specialized instructions
- Sub-agents share the same Claude model but get fresh context windows
- `_make_model()` — Shared model config factory

### server.py — The Server
- FastAPI application for Docker sandboxing
- Batch mode (`interactive=False`): Uses plain `Agent` — simpler, faster
- Interactive mode (`interactive=True`): Uses `Team` — delegation-capable
- Both expose the same SSE streaming interface
- `_create_agents()` — Hot-reload support with module cache clearing

### prompts.py — The Brain
- `get_system_prompt()` returns a list of instruction strings
- Defines Miguel's identity, behavior rules, and improvement process
- Includes delegation guidance for team architecture
- This file is the primary target for self-improvement
- Can be safely modified using the prompt_tools

### config.py — Settings
- `MODEL_ID` — Which Claude model to use
- `AGENT_VERSION` — Current version string
- `MAX_TOOL_RETRIES` — Error handling config

### tools/error_utils.py — Error Handling Foundation
- `@safe_tool` decorator — Wraps all tool functions with exception handling
- `format_error()` — Consistent error formatting helper
- `safe_write()` — Atomic file writing with automatic .bak backups
- `validate_python()` — Syntax validation for Python code
- `list_backups()` — Find all .bak backup files

### tools/capability_tools.py — Growth Engine
- Manages the capability checklist (get, check, add capabilities)
- Data stored in `capabilities.json`

### tools/self_tools.py — Self-Awareness
- `read_own_file(path)` — Read any file in agent/
- `list_own_files()` — List all files in agent/
- `get_architecture()` — Return this architecture map
- `log_improvement(summary, files)` — Append to improvements.md

### tools/prompt_tools.py — Prompt Self-Modification
- `get_prompt_sections()` — Parse and list all sections in system prompt
- `modify_prompt_section()` — Safely modify prompt sections (replace/append/add_new)

### tools/recovery_tools.py — Error Recovery & Diagnostics
- `recover_backup()` — Restore files from .bak backups
- `list_recovery_points()` — Show available backups
- `validate_agent_file()` — Syntax check Python files
- `health_check()` — Full codebase diagnostic

### tools/tool_creator.py — Tool Factory
- `create_tool()` — Create new tool file + auto-register in core.py
- `add_functions_to_tool()` — Extend existing tool files

### tools/memory_tools.py — Persistent Memory
- `remember()` / `recall()` / `forget()` / `list_memories()`
- Data stored in `memory.db` (SQLite)

### tools/planning_tools.py — Task Planning & Decomposition
- `create_plan()` / `add_task()` / `update_task()` / `show_plan()` / `get_next_task()`
- Task dependencies with auto-unblocking
- Data stored in `planning.db` (SQLite)

### tools/file_analysis_tools.py — File Analysis & Data Processing
- `analyze_csv()` — Tabular data (CSV, Excel, JSON, Parquet)
- `analyze_pdf()` — PDF text extraction with metadata
- `analyze_image()` — Image metadata, colors, EXIF
- `csv_query()` — Arbitrary pandas expressions

### tools/api_tools.py — HTTP Client & API Integrations
- `http_request()` — Full-featured HTTP client with auth
- `api_get()` / `api_post()` — Quick request helpers
- `api_quickstart()` — 10 pre-built free API integrations

### tools/web_tools.py — Web Search & Research
- `web_search()` / `web_news()` / `web_search_detailed()`
- DuckDuckGo-powered, region-aware

### tools/dep_tools.py — Dependency Management
- `add_dependency()` — Install + record packages
- `list_dependencies()` — List from pyproject.toml

## Data Flow
1. User message → `create_team()` builds Team → coordinator processes with system prompt
2. Coordinator decides: use own tools OR delegate to sub-agent (Coder/Researcher/Analyst)
3. Sub-agents run with fresh context, return results to coordinator
4. Coordinator synthesizes results and responds to user
5. For self-improvement: read checklist → implement change → write files → mark done → log
6. For prompt modification: parse sections → modify → validate syntax → write → confirm
7. For tool creation: write tool file → validate syntax → update core.py → register
8. For error recovery: health_check → diagnose → recover_backup or fix
9. For web search: web_search/web_news → format and present
10. For memory: remember() to store → recall() in future → persists in SQLite
11. For planning: create_plan → add tasks → work through → update_task cascades
12. For file analysis: analyze_csv/pdf/image → rich output → csv_query for follow-up
13. For API calls: http_request or api_quickstart → auto-parsed responses

## Error Handling Strategy
- **Prevention:** All file-modifying tools validate syntax before writing
- **Backups:** .bak files created automatically before any modification
- **Atomic writes:** temp file + rename pattern prevents partial writes
- **Safe decorator:** `@safe_tool` catches all exceptions, returns usable error messages
- **Recovery:** `recover_backup()` restores files; `health_check()` diagnoses full codebase
- **Security:** Path validation ensures all operations stay within agent/

## Security Boundaries
- `read_own_file` refuses to read outside agent/
- `safe_write` refuses to write outside agent/
- `LocalFileSystemTools` scoped to agent/ directory
- `modify_prompt_section` validates syntax before writing
- `create_tool` validates syntax and docstrings, validates core.py after modification
- `csv_query` uses restricted namespace for eval safety
- System prompt forbids modifying files outside agent/