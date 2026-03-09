# Miguel Improvement Log

Each entry records: batch number, timestamp, what changed, and why.

---

### 2026-03-09 11:27:37 UTC
**Summary:** Batch #1: Implemented cap-001 (Respond to basic questions). Added a comprehensive 'Core Behavior: Answering Questions' section to the system prompt in prompts.py. This gives Miguel clear instructions for its primary function: answering user questions directly, honestly, using tools to verify facts, working step-by-step on technical problems, formatting with markdown, asking for clarification when needed, and scaling response length to question complexity.
**Files changed:** prompts.py

### 2026-03-09 11:46:50 UTC
**Summary:** Batch #2: Implemented cap-002 (Read and explain own source code). Created architecture.md — a structured self-describing map of Miguel's entire codebase, covering directory structure, key components, data flow, and security boundaries. Added a new `get_architecture()` tool in self_tools.py that returns this map on demand. Registered the tool in core.py. Enhanced the Self-Awareness section of prompts.py to instruct Miguel to use get_architecture first when asked about itself, and to explain both WHAT and WHY for each component, using analogies to make things accessible.
**Files changed:** architecture.md, tools/self_tools.py, core.py, prompts.py
