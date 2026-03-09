"""Error handling utilities for Miguel's tools.

Provides decorators and helpers for consistent, graceful error handling
across all tool functions. Instead of raw exceptions bubbling up, tools
return clean error messages the agent can understand and act on.
"""

import functools
import traceback
from typing import Callable


def safe_tool(func: Callable) -> Callable:
    """Decorator that wraps a tool function with error handling.
    
    Catches all exceptions and returns a formatted error string instead
    of letting the exception propagate. This ensures the agent always
    gets a usable response it can reason about.
    
    Usage:
        @safe_tool
        def my_tool(arg: str) -> str:
            '''My tool description.'''
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> str:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            return f"Error in {func.__name__}: File not found — {e}"
        except PermissionError as e:
            return f"Error in {func.__name__}: Permission denied — {e}"
        except json.JSONDecodeError as e:
            return f"Error in {func.__name__}: Invalid JSON — {e}"
        except (KeyError, IndexError) as e:
            return f"Error in {func.__name__}: Data access error — {type(e).__name__}: {e}"
        except SyntaxError as e:
            return f"Error in {func.__name__}: Python syntax error at line {e.lineno} — {e.msg}"
        except OSError as e:
            return f"Error in {func.__name__}: OS/filesystem error — {e}"
        except Exception as e:
            # Catch-all for unexpected errors — include traceback for debugging
            tb = traceback.format_exc()
            short_tb = "\n".join(tb.strip().split("\n")[-3:])
            return (
                f"Error in {func.__name__}: Unexpected {type(e).__name__} — {e}\n"
                f"Traceback (last 3 lines):\n{short_tb}"
            )
    return wrapper


import json  # imported here since it's used in the decorator


def format_error(tool_name: str, error: Exception, hint: str = "") -> str:
    """Format an error message consistently for tool responses.
    
    Args:
        tool_name: Name of the tool/function that failed.
        error: The exception that was caught.
        hint: Optional hint for recovery.
    
    Returns:
        Formatted error string.
    """
    msg = f"Error in {tool_name}: {type(error).__name__} — {error}"
    if hint:
        msg += f"\nHint: {hint}"
    return msg