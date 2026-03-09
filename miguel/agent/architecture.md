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
└── tools/
    ├── __init__.py      # Empty — makes tools/ a Python package
    ├── capability_tools.py  # Tools for managing the capability checklist
    └── self_tools.py    # Tools for self-inspection and logging improvements
```

## Key Components

### core.py — The Heart
- `create_agent()` — Factory function that instantiates an `agno.agent.Agent`
- Wires together: model, instructions, and all tools
- External tools: `PythonTools` (run code), `ShellTools` (run commands), `LocalFileSystemTools` (read/write files)
- Custom tools: capability management + self-inspection

### prompts.py — The Brain
- `get_system_prompt()` returns a list of instruction strings
- Defines Miguel's identity, behavior rules, and improvement process
- This file is the primary target for self-improvement

### config.py — Settings
- `MODEL_ID` — Which Claude model to use
- `AGENT_VERSION` — Current version string
- `MAX_TOOL_RETRIES` — Error handling config

### tools/capability_tools.py — Growth Engine
- `get_capabilities()` — Read full checklist
- `get_next_capability()` — Find highest-priority unchecked item
- `check_capability(id)` — Mark item as done
- `add_capability(title, desc, priority)` — Add new items
- Data stored in `capabilities.json`

### tools/self_tools.py — Self-Awareness
- `read_own_file(path)` — Read any file in agent/ (with security check)
- `list_own_files()` — List all files in agent/
- `log_improvement(summary, files)` — Append to improvements.md

## Data Flow
1. User message → `create_agent()` builds Agent → Claude processes with system prompt
2. Claude decides which tools to call → tools execute → results fed back
3. For self-improvement: read checklist → implement change → write files → mark done → log

## Security Boundaries
- `read_own_file` refuses to read outside agent/
- `LocalFileSystemTools` is scoped to agent/ directory
- System prompt explicitly forbids modifying files outside agent/