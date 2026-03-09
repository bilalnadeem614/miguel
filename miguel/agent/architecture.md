# Miguel Architecture Map

## Overview
Miguel is a self-improving AI agent built on the **Agno** framework with **Claude** (Anthropic) as its LLM backbone. It can read, modify, and extend its own source code.

## Directory Structure

```
agent/
├── __init__.py          # Package entry point — exports create_agent()
├── core.py              # Agent factory — creates and configures the Agent instance
├── config.py            # Settings — model ID, version, constants
├── prompts.py           # System prompt builder — defines Miguel's personality & instructions
├── architecture.md      # This file — self-describing architecture map
├── capabilities.json    # Checklist of capabilities (checked/unchecked)
├── improvements.md      # Log of all self-improvements made
├── memory.db            # SQLite database for persistent memory across sessions
└── tools/
    ├── __init__.py          # Empty — makes tools/ a Python package
    ├── error_utils.py       # Error handling foundation — decorators, safe writes, validation
    ├── capability_tools.py  # Tools for managing the capability checklist
    ├── dep_tools.py         # Dependency management tools
    ├── memory_tools.py      # Persistent memory — store/recall facts, preferences, context
    ├── prompt_tools.py      # Tools for safely inspecting and modifying the system prompt
    ├── recovery_tools.py    # Error recovery and diagnostic tools
    ├── self_tools.py        # Tools for self-inspection and logging improvements
    ├── tool_creator.py      # Tools for creating new tools and auto-registering them
    └── web_tools.py         # Web search and information retrieval via DuckDuckGo
```

## Key Components

### core.py — The Heart
- `create_agent()` — Factory function that instantiates an `agno.agent.Agent`
- Wires together: model, instructions, and all tools
- External tools: `PythonTools` (run code), `ShellTools` (run commands), `LocalFileSystemTools` (read/write files)
- Custom tools: capability management + self-inspection + prompt modification + tool creation + recovery + web search + memory

### prompts.py — The Brain
- `get_system_prompt()` returns a list of instruction strings
- Defines Miguel's identity, behavior rules, and improvement process
- This file is the primary target for self-improvement
- Can be safely modified using the prompt_tools

### config.py — Settings
- `MODEL_ID` — Which Claude model to use
- `AGENT_VERSION` — Current version string
- `MAX_TOOL_RETRIES` — Error handling config

### tools/error_utils.py — Error Handling Foundation
- `@safe_tool` decorator — Wraps all tool functions with exception handling, returning clean error messages instead of raw tracebacks
- `format_error()` — Consistent error formatting helper
- `safe_write()` — Atomic file writing with automatic .bak backups and security checks
- `validate_python()` — Syntax validation for Python code
- `list_backups()` — Find all .bak backup files in the agent directory
- All tool files import from here — this is the error handling foundation

### tools/capability_tools.py — Growth Engine
- `get_capabilities()` — Read full checklist
- `get_next_capability()` — Find highest-priority unchecked item
- `check_capability(id)` — Mark item as done
- `add_capability(title, desc, priority)` — Add new items
- Data stored in `capabilities.json`
- Uses atomic writes (tmp + rename) for data safety

### tools/self_tools.py — Self-Awareness
- `read_own_file(path)` — Read any file in agent/ (with security check)
- `list_own_files()` — List all files in agent/
- `get_architecture()` — Return this architecture map
- `log_improvement(summary, files)` — Append to improvements.md

### tools/prompt_tools.py — Prompt Self-Modification
- `get_prompt_sections()` — Parse and list all sections in the system prompt with line counts
- `modify_prompt_section(section_name, new_content, action)` — Safely modify prompt sections
  - Actions: `replace` (overwrite), `append` (add lines), `add_new` (create section)
  - Uses AST parsing to extract current prompt lines
  - Validates generated Python syntax before writing — prevents breaking prompts.py
  - Handles f-strings containing `{AGENT_DIR}` correctly
  - Creates .bak backup before every write

### tools/recovery_tools.py — Error Recovery & Diagnostics
- `recover_backup(file_path)` — Restore any file from its .bak backup
  - Validates backup syntax (for .py files) before restoring
  - Verifies restore was successful
  - Preserves the backup file for safety
- `list_recovery_points()` — Show all available .bak backups with sizes
- `validate_agent_file(file_path)` — Check a Python file for syntax errors + docstring warnings
- `health_check()` — Comprehensive codebase diagnostic:
  - Checks all critical files exist
  - Validates syntax of every Python file
  - Verifies capabilities.json structure
  - Lists orphan backup files

### tools/tool_creator.py — Tool Factory
- `create_tool(file_name, code, register)` — Create a new tool file in tools/ and auto-register in core.py
  - Validates Python syntax before writing
  - Ensures all public functions have docstrings (required by Agno)
  - Automatically adds import statement and tool registration to core.py
  - Validates core.py syntax after modification — rolls back if broken
- `add_functions_to_tool(file_name, new_code)` — Append new functions to an existing tool file
  - Checks for naming conflicts with existing functions
  - Validates combined file syntax
  - Auto-registers new functions in core.py

### tools/memory_tools.py — Persistent Memory
- `remember(key, value, category)` — Store a fact, preference, context, or summary
  - Categories: `fact`, `preference`, `context`, `summary`
  - Auto-updates existing memories with the same key+category (upsert)
  - Returns confirmation with memory ID
- `recall(query, category, limit)` — Search memories by keyword (case-insensitive)
  - Searches both keys and values using LIKE matching
  - Optional category filter and result limit
  - Returns formatted list with IDs, categories, and timestamps
- `forget(memory_id)` — Delete a specific memory by its numeric ID
  - Returns confirmation with what was deleted
- `list_memories(category, limit)` — Browse all stored memories
  - Groups results by category for readability
  - Optional category filter
- Data stored in `memory.db` (SQLite) — persists across conversations and restarts
- Schema: `memories(id, key, value, category, created_at, updated_at)`
- Uses `@safe_tool` decorator for graceful error handling
- No external dependencies — uses Python's built-in `sqlite3`

### tools/web_tools.py — Web Search & Research
- `web_search(query, max_results)` — General web search via DuckDuckGo
  - Returns formatted results with titles, URLs, and snippets
  - Default 5 results, max 20
- `web_news(query, max_results)` — Search recent news articles
  - Returns results with titles, URLs, dates, sources, and snippets
- `web_search_detailed(query, region, max_results)` — Detailed search with region filtering
  - Returns structured JSON output for programmatic parsing
  - Supports region codes: 'us-en', 'uk-en', 'de-de', 'fr-fr', etc.
- All functions use `@safe_tool` decorator for graceful error handling
- Uses lazy imports of `duckduckgo_search` to avoid startup overhead
- Dependency: `duckduckgo-search` (PyPI)

### tools/dep_tools.py — Dependency Management
- `add_dependency(package_name)` — Install a Python package and record it
- `list_dependencies()` — List current dependencies from pyproject.toml

## Data Flow
1. User message → `create_agent()` builds Agent → Claude processes with system prompt
2. Claude decides which tools to call → tools execute → results fed back
3. For self-improvement: read checklist → implement change → write files → mark done → log
4. For prompt modification: parse sections → modify → validate syntax → write → confirm
5. For tool creation: write tool file → validate syntax → update core.py imports → register tools
6. For error recovery: health_check → diagnose → recover_backup or fix manually
7. For web search: user asks question → agent calls web_search/web_news → formats and presents results
8. For memory: agent calls remember() to store info → recall() in future sessions to retrieve it → memory persists in SQLite

## Error Handling Strategy
- **Prevention:** All file-modifying tools validate syntax before writing
- **Backups:** .bak files created automatically before any modification
- **Atomic writes:** temp file + rename pattern prevents partial writes
- **Safe decorator:** `@safe_tool` catches all exceptions and returns usable error messages
- **Recovery:** `recover_backup()` can restore any file; `health_check()` diagnoses the full codebase
- **Security:** Path validation ensures all operations stay within agent/

## Security Boundaries
- `read_own_file` refuses to read outside agent/
- `safe_write` refuses to write outside agent/
- `LocalFileSystemTools` is scoped to agent/ directory
- `modify_prompt_section` validates syntax before writing (prevents self-corruption)
- `create_tool` validates syntax and docstrings before writing, validates core.py after modification
- System prompt explicitly forbids modifying files outside agent/