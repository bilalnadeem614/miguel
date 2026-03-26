"""Configuration for Miguel agent. Central place for all settings."""

import os
from pathlib import Path

AGENT_VERSION = "0.2.0"
MODEL_ID = "gemini-2.5-flash"

# User files directory — set by Docker env var, or defaults to <project>/user_files
USER_FILES_DIR = os.environ.get(
    "USER_FILES_DIR",
    str(Path(__file__).parent.parent.parent / "user_files"),
)

# Context window limits per model (tokens)
MODEL_CONTEXT_LIMITS = {
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
    "default": 1_000_000,
}