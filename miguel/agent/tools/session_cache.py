"""Session-level preference caching to avoid redundant recomputation.

Caches the computed preference snapshot for each session_id, so preferences
are loaded once per session and reused for all subsequent messages in that session.
"""

import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_CACHE_LOCK = threading.RLock()
_SESSION_PREFERENCE_CACHE: Dict[str, str] = {}


def get_cached_preferences(session_id: Optional[str]) -> Optional[str]:
    """Retrieve cached preferences for a session, or None if not cached."""
    if not session_id:
        return None
    
    with _CACHE_LOCK:
        return _SESSION_PREFERENCE_CACHE.get(session_id)


def set_cached_preferences(session_id: Optional[str], preferences_str: str) -> None:
    """Store preferences snapshot for a session."""
    if not session_id:
        return
    
    with _CACHE_LOCK:
        _SESSION_PREFERENCE_CACHE[session_id] = preferences_str
        logger.debug("Cached preferences for session %s", session_id)


def clear_session_cache(session_id: Optional[str]) -> None:
    """Clear the cached preferences for a specific session."""
    if not session_id:
        return
    
    with _CACHE_LOCK:
        if session_id in _SESSION_PREFERENCE_CACHE:
            del _SESSION_PREFERENCE_CACHE[session_id]
            logger.debug("Cleared cached preferences for session %s", session_id)


def clear_all_preferences_cache() -> None:
    """Clear all cached preferences (use when preferences files change)."""
    with _CACHE_LOCK:
        _SESSION_PREFERENCE_CACHE.clear()
        logger.debug("Cleared all cached preferences")
