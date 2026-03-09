"""Structured task planning and decomposition tools for Miguel.

Enables breaking complex user requests into ordered sub-tasks, tracking
progress through them, and handling dependencies between tasks. Plans
persist in a SQLite database across conversations.

Schema:
    plans(id, title, description, status, created_at, updated_at)
    tasks(id, plan_id, title, description, status, order_index,
          depends_on, created_at, updated_at)

Plan statuses: active, completed, archived
Task statuses: pending, in_progress, done, blocked, skipped
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from miguel.agent.tools.error_utils import safe_tool

PLANNING_DB = Path(__file__).parent.parent / "planning.db"

VALID_PLAN_STATUSES = {"active", "completed", "archived"}
VALID_TASK_STATUSES = {"pending", "in_progress", "done", "blocked", "skipped"}


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the planning database, creating tables if needed."""
    conn = sqlite3.connect(str(PLANNING_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            order_index INTEGER NOT NULL DEFAULT 0,
            depends_on TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id)")
    conn.commit()
    return conn


def _now() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _format_status_icon(status: str) -> str:
    """Return a status icon for display."""
    icons = {
        "pending": "⬜",
        "in_progress": "🔄",
        "done": "✅",
        "blocked": "🚫",
        "skipped": "⏭️",
        "active": "📋",
        "completed": "✅",
        "archived": "📦",
    }
    return icons.get(status, "❓")


@safe_tool
def create_plan(title: str, description: str = "", tasks: str = "") -> str:
    """Create a new plan, optionally with an initial list of tasks.

    Use this to break a complex request into a structured plan with ordered steps.

    Args:
        title: Short name for the plan (e.g. "Build Flask API", "Research AI trends").
        description: Longer description of the goal and scope.
        tasks: Optional comma-separated list of task titles to create in order.
               Example: "Set up project, Design API routes, Implement endpoints, Write tests"

    Returns:
        Confirmation with the plan ID and created tasks.
    """
    if not title or not title.strip():
        return "Error: plan title cannot be empty."

    title = title.strip()
    description = description.strip() if description else ""
    now = _now()

    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO plans (title, description, status, created_at, updated_at) VALUES (?, ?, 'active', ?, ?)",
            (title, description, now, now),
        )
        plan_id = cursor.lastrowid

        task_count = 0
        if tasks and tasks.strip():
            task_titles = [t.strip() for t in tasks.split(",") if t.strip()]
            for i, task_title in enumerate(task_titles):
                conn.execute(
                    "INSERT INTO tasks (plan_id, title, status, order_index, depends_on, created_at, updated_at) VALUES (?, ?, 'pending', ?, '[]', ?, ?)",
                    (plan_id, task_title, i + 1, now, now),
                )
                task_count += 1

        conn.commit()

        result = f"📋 Created plan #{plan_id}: **{title}**"
        if description:
            result += f"\n_{description}_"
        if task_count:
            result += f"\nAdded {task_count} tasks."
        else:
            result += "\nNo tasks yet — use `add_task` to add steps."
        return result
    finally:
        conn.close()


@safe_tool
def add_task(plan_id: int, title: str, description: str = "", depends_on: str = "") -> str:
    """Add a task to an existing plan.

    Args:
        plan_id: The ID of the plan to add the task to.
        title: Short name for the task.
        description: Longer description of what this task involves.
        depends_on: Comma-separated list of task IDs this task depends on.
                    Task will be marked 'blocked' if dependencies aren't done.
                    Example: "1,3" means this task depends on tasks #1 and #3.

    Returns:
        Confirmation with the task ID.
    """
    if not title or not title.strip():
        return "Error: task title cannot be empty."

    title = title.strip()
    description = description.strip() if description else ""
    now = _now()

    # Parse dependencies
    dep_ids = []
    if depends_on and depends_on.strip():
        try:
            dep_ids = [int(d.strip()) for d in depends_on.split(",") if d.strip()]
        except ValueError:
            return "Error: depends_on must be comma-separated integers (e.g. '1,3')."

    conn = _get_conn()
    try:
        # Verify plan exists
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return f"Error: no plan found with ID #{plan_id}."

        # Get next order index
        max_order = conn.execute(
            "SELECT COALESCE(MAX(order_index), 0) FROM tasks WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()[0]

        # Verify dependency tasks exist in same plan
        if dep_ids:
            for dep_id in dep_ids:
                dep_task = conn.execute(
                    "SELECT id FROM tasks WHERE id = ? AND plan_id = ?",
                    (dep_id, plan_id),
                ).fetchone()
                if not dep_task:
                    return f"Error: dependency task #{dep_id} not found in plan #{plan_id}."

        # Determine initial status based on dependencies
        initial_status = "pending"
        if dep_ids:
            undone = conn.execute(
                f"SELECT COUNT(*) FROM tasks WHERE id IN ({','.join('?' * len(dep_ids))}) AND status NOT IN ('done', 'skipped')",
                dep_ids,
            ).fetchone()[0]
            if undone > 0:
                initial_status = "blocked"

        deps_json = json.dumps(dep_ids)
        cursor = conn.execute(
            "INSERT INTO tasks (plan_id, title, description, status, order_index, depends_on, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, title, description, initial_status, max_order + 1, deps_json, now, now),
        )
        conn.commit()

        result = f"Added task #{cursor.lastrowid} to plan #{plan_id}: **{title}**"
        if dep_ids:
            result += f" (depends on: {', '.join(f'#{d}' for d in dep_ids)}, status: {initial_status})"
        return result
    finally:
        conn.close()


@safe_tool
def update_task(task_id: int, status: str) -> str:
    """Update the status of a task.

    When a task is marked 'done' or 'skipped', any tasks that depended on it
    will be automatically unblocked if all their dependencies are now satisfied.

    Args:
        task_id: The ID of the task to update.
        status: New status — one of 'pending', 'in_progress', 'done', 'blocked', 'skipped'.

    Returns:
        Confirmation message, including any tasks that were unblocked.
    """
    status = status.lower().strip()
    if status not in VALID_TASK_STATUSES:
        return f"Error: status must be one of {VALID_TASK_STATUSES}, got '{status}'."

    now = _now()
    conn = _get_conn()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return f"Error: no task found with ID #{task_id}."

        old_status = task["status"]
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )

        # If task completed/skipped, check if any blocked tasks can be unblocked
        unblocked = []
        if status in ("done", "skipped"):
            plan_id = task["plan_id"]
            # Find all tasks in this plan that are blocked
            blocked_tasks = conn.execute(
                "SELECT * FROM tasks WHERE plan_id = ? AND status = 'blocked'",
                (plan_id,),
            ).fetchall()

            for bt in blocked_tasks:
                dep_ids = json.loads(bt["depends_on"])
                if not dep_ids:
                    continue
                # Check if all dependencies are now done/skipped
                undone = conn.execute(
                    f"SELECT COUNT(*) FROM tasks WHERE id IN ({','.join('?' * len(dep_ids))}) AND status NOT IN ('done', 'skipped')",
                    dep_ids,
                ).fetchone()[0]
                if undone == 0:
                    conn.execute(
                        "UPDATE tasks SET status = 'pending', updated_at = ? WHERE id = ?",
                        (now, bt["id"]),
                    )
                    unblocked.append(f"#{bt['id']} ({bt['title']})")

        # Check if all tasks in plan are done — auto-complete the plan
        plan_id = task["plan_id"]
        total = conn.execute("SELECT COUNT(*) FROM tasks WHERE plan_id = ?", (plan_id,)).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE plan_id = ? AND status IN ('done', 'skipped')",
            (plan_id,),
        ).fetchone()[0]
        if total > 0 and total == completed:
            conn.execute(
                "UPDATE plans SET status = 'completed', updated_at = ? WHERE id = ?",
                (now, plan_id),
            )

        conn.commit()

        icon = _format_status_icon(status)
        result = f"{icon} Task #{task_id} ({task['title']}): {old_status} → **{status}**"
        if unblocked:
            result += f"\n🔓 Unblocked: {', '.join(unblocked)}"
        if total > 0 and total == completed:
            result += f"\n🎉 Plan #{plan_id} is now complete! All {total} tasks done."
        return result
    finally:
        conn.close()


@safe_tool
def show_plan(plan_id: int) -> str:
    """Show a plan with all its tasks and current progress.

    Args:
        plan_id: The ID of the plan to display.

    Returns:
        Formatted plan overview with task list and progress bar.
    """
    conn = _get_conn()
    try:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return f"Error: no plan found with ID #{plan_id}."

        tasks = conn.execute(
            "SELECT * FROM tasks WHERE plan_id = ? ORDER BY order_index, id",
            (plan_id,),
        ).fetchall()

        icon = _format_status_icon(plan["status"])
        lines = [f"{icon} **Plan #{plan_id}: {plan['title']}** ({plan['status']})"]
        if plan["description"]:
            lines.append(f"_{plan['description']}_")

        if not tasks:
            lines.append("\nNo tasks yet.")
            return "\n".join(lines)

        # Progress stats
        total = len(tasks)
        done_count = sum(1 for t in tasks if t["status"] in ("done", "skipped"))
        in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
        blocked = sum(1 for t in tasks if t["status"] == "blocked")
        pending = sum(1 for t in tasks if t["status"] == "pending")

        # Progress bar
        pct = int((done_count / total) * 100) if total > 0 else 0
        filled = pct // 5
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"\nProgress: [{bar}] {pct}% ({done_count}/{total} done)")

        if in_progress:
            lines.append(f"  🔄 {in_progress} in progress")
        if blocked:
            lines.append(f"  🚫 {blocked} blocked")
        if pending:
            lines.append(f"  ⬜ {pending} pending")

        # Task list
        lines.append("\n**Tasks:**")
        for t in tasks:
            t_icon = _format_status_icon(t["status"])
            dep_ids = json.loads(t["depends_on"])
            dep_str = ""
            if dep_ids:
                dep_str = f" ← depends on {', '.join(f'#{d}' for d in dep_ids)}"
            desc_str = ""
            if t["description"]:
                desc_str = f"\n    _{t['description']}_"
            lines.append(f"  {t['order_index']}. {t_icon} [#{t['id']}] {t['title']} ({t['status']}){dep_str}{desc_str}")

        return "\n".join(lines)
    finally:
        conn.close()


@safe_tool
def list_plans(status: str = "active") -> str:
    """List all plans, optionally filtered by status.

    Args:
        status: Filter by status — 'active', 'completed', 'archived', or 'all'. Default: 'active'.

    Returns:
        Formatted list of plans with progress summaries.
    """
    status = status.lower().strip() if status else "active"
    if status != "all" and status not in VALID_PLAN_STATUSES:
        return f"Error: status must be one of {VALID_PLAN_STATUSES} or 'all', got '{status}'."

    conn = _get_conn()
    try:
        if status == "all":
            plans = conn.execute("SELECT * FROM plans ORDER BY updated_at DESC").fetchall()
        else:
            plans = conn.execute(
                "SELECT * FROM plans WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()

        if not plans:
            return f"No {status} plans found." if status != "all" else "No plans found."

        lines = [f"**Plans ({status}):** {len(plans)} found\n"]
        for plan in plans:
            icon = _format_status_icon(plan["status"])
            # Get task counts
            total = conn.execute("SELECT COUNT(*) FROM tasks WHERE plan_id = ?", (plan["id"],)).fetchone()[0]
            done = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE plan_id = ? AND status IN ('done', 'skipped')",
                (plan["id"],),
            ).fetchone()[0]
            pct = int((done / total) * 100) if total > 0 else 0

            lines.append(f"{icon} **#{plan['id']}: {plan['title']}** — {done}/{total} tasks ({pct}%)")
            if plan["description"]:
                lines.append(f"  _{plan['description']}_")

        return "\n".join(lines)
    finally:
        conn.close()


@safe_tool
def get_next_task(plan_id: int) -> str:
    """Get the next actionable task from a plan.

    Returns the first task that is 'pending' or 'in_progress' (by order_index).
    Skips blocked tasks.

    Args:
        plan_id: The ID of the plan to get the next task from.

    Returns:
        Details of the next task, or a message if the plan is complete.
    """
    conn = _get_conn()
    try:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return f"Error: no plan found with ID #{plan_id}."

        # First check for in-progress tasks
        in_progress = conn.execute(
            "SELECT * FROM tasks WHERE plan_id = ? AND status = 'in_progress' ORDER BY order_index LIMIT 1",
            (plan_id,),
        ).fetchone()

        if in_progress:
            icon = _format_status_icon("in_progress")
            result = f"{icon} **Currently in progress:**\n"
            result += f"  Task #{in_progress['id']}: {in_progress['title']}"
            if in_progress["description"]:
                result += f"\n  _{in_progress['description']}_"
            return result

        # Then check for pending tasks
        pending = conn.execute(
            "SELECT * FROM tasks WHERE plan_id = ? AND status = 'pending' ORDER BY order_index LIMIT 1",
            (plan_id,),
        ).fetchone()

        if pending:
            icon = _format_status_icon("pending")
            result = f"{icon} **Next task:**\n"
            result += f"  Task #{pending['id']}: {pending['title']}"
            if pending["description"]:
                result += f"\n  _{pending['description']}_"
            result += f"\n\nUse `update_task({pending['id']}, 'in_progress')` to start it."
            return result

        # Check for blocked tasks
        blocked = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE plan_id = ? AND status = 'blocked'",
            (plan_id,),
        ).fetchone()[0]

        if blocked:
            return f"🚫 {blocked} task(s) are blocked. Complete their dependencies first."

        return f"🎉 All tasks in plan #{plan_id} are done!"
    finally:
        conn.close()


@safe_tool
def remove_plan(plan_id: int) -> str:
    """Delete a plan and all its tasks permanently.

    Args:
        plan_id: The ID of the plan to delete.

    Returns:
        Confirmation of deletion.
    """
    conn = _get_conn()
    try:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return f"Error: no plan found with ID #{plan_id}."

        task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE plan_id = ?", (plan_id,)).fetchone()[0]
        conn.execute("DELETE FROM tasks WHERE plan_id = ?", (plan_id,))
        conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        conn.commit()

        return f"🗑️ Deleted plan #{plan_id} ({plan['title']}) and its {task_count} tasks."
    finally:
        conn.close()