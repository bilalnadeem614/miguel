"""Tools for managing Miguel's capability checklist."""

import json
from datetime import datetime, timezone
from pathlib import Path

CAPABILITIES_PATH = Path(__file__).parent.parent / "capabilities.json"


def _load() -> dict:
    return json.loads(CAPABILITIES_PATH.read_text())


def _save(data: dict) -> None:
    CAPABILITIES_PATH.write_text(json.dumps(data, indent=2) + "\n")


def get_capabilities() -> str:
    """Read the full capabilities checklist and return it as formatted JSON."""
    return json.dumps(_load(), indent=2)


def get_next_capability() -> str:
    """Get the highest-priority unchecked capability. Returns its JSON or a message if all are checked."""
    data = _load()
    unchecked = [c for c in data["capabilities"] if c["status"] == "unchecked"]
    if not unchecked:
        return "ALL_CHECKED: All capabilities are checked. You should generate new capabilities using add_capability."
    unchecked.sort(key=lambda c: c["priority"])
    return json.dumps(unchecked[0], indent=2)


def check_capability(capability_id: str) -> str:
    """Mark a capability as completed by its ID (e.g. 'cap-001')."""
    data = _load()
    for item in data["capabilities"]:
        if item["id"] == capability_id:
            item["status"] = "checked"
            item["completed_at"] = datetime.now(timezone.utc).isoformat()
            _save(data)
            return f"Capability '{capability_id}' ({item['title']}) marked as completed."
    return f"Error: capability '{capability_id}' not found."


def add_capability(title: str, description: str, priority: int) -> str:
    """Add a new capability to the checklist. Priority determines order (lower = higher priority)."""
    data = _load()
    existing_ids = [c["id"] for c in data["capabilities"]]
    max_num = max(int(cid.split("-")[1]) for cid in existing_ids) if existing_ids else 0
    new_id = f"cap-{max_num + 1:03d}"

    new_cap = {
        "id": new_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "unchecked",
        "category": "self-generated",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    data["capabilities"].append(new_cap)
    _save(data)
    return f"Added capability '{new_id}': {title}"
