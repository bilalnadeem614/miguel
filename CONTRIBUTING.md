# Contributing to Miguel

Thanks for your interest in contributing! Miguel is an unusual project — the agent modifies its own code under `miguel/agent/`, while human contributors typically work on the host-side infrastructure.

## Development Setup

```bash
git clone https://github.com/soulfir/miguel.git
cd miguel
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Start the Docker container and test:

```bash
miguel          # Interactive mode
miguel improve 1  # Run one improvement batch
```

## How to Contribute

- **Bug reports** — Open an issue with reproduction steps and any relevant terminal output.
- **Feature requests** — Open an issue describing the feature and why it would be useful.
- **Pull requests** — Fork the repo, create a branch, make your changes, and submit a PR.
- **Safety improvements** — Especially welcome. Better validation checks, tighter Docker security, new test cases in `miguel/tests/`.

## What to Change (and What Not To)

**Human domain** (feel free to modify):
- `miguel/cli.py` — CLI and REPL
- `miguel/runner.py` — Improvement loop and git operations
- `miguel/display.py` — Terminal rendering
- `miguel/client.py` — HTTP client for the container
- `miguel/container.py` — Docker lifecycle
- `miguel/tests/` — Validation and health checks
- `Dockerfile`, `docker-compose.yml` — Container configuration

**Agent domain** (do not manually edit):
- `miguel/agent/` — This is Miguel's territory. The agent modifies these files during improvement batches. Manual edits here will conflict with the agent's self-improvement process.
- **Exception:** Fixing bugs that prevent the agent from running is fine.

## Code Style

- Python 3.11+ with type hints
- Docstrings on all public functions
- Follow existing patterns in the codebase

## License

By contributing, you agree that your contributions will be licensed under the same [CC BY-NC 4.0](LICENSE) license as the project.
