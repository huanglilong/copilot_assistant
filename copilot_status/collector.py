"""Copilot CLI status collector - reads session data from filesystem."""

import glob
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

COPILOT_STATE_DIR = Path.home() / ".copilot" / "session-state"


def get_active_sessions():
    """Find all active Copilot CLI sessions (those with lock files)."""
    sessions = []
    lock_pattern = str(COPILOT_STATE_DIR / "*" / "inuse.*.lock")
    for lock_file in glob.glob(lock_pattern):
        session_dir = Path(lock_file).parent
        session_id = session_dir.name
        pid = Path(lock_file).stem.replace("inuse.", "")

        workspace = _read_workspace(session_dir)
        events_summary = _read_events_summary(session_dir)
        todos = _read_todos(session_dir)
        waiting = _check_waiting(session_dir)

        sessions.append({
            "session_id": session_id,
            "pid": int(pid),
            "workspace": workspace,
            "events_summary": events_summary,
            "todos": todos,
            "waiting": waiting,
            "session_dir": str(session_dir),
        })

    sessions.sort(key=lambda s: s["workspace"].get("updated_at", ""), reverse=True)
    return sessions


def get_all_sessions(limit=20):
    """Get recent sessions (active + inactive)."""
    sessions = []
    if not COPILOT_STATE_DIR.exists():
        return sessions

    active_ids = set()
    for lock_file in glob.glob(str(COPILOT_STATE_DIR / "*" / "inuse.*.lock")):
        active_ids.add(Path(lock_file).parent.name)

    dirs = sorted(COPILOT_STATE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs[:limit]:
        if not d.is_dir() or d.name.startswith("."):
            continue
        workspace = _read_workspace(d)
        if not workspace:
            continue
        sessions.append({
            "session_id": d.name,
            "active": d.name in active_ids,
            "workspace": workspace,
        })
    return sessions


def _read_workspace(session_dir):
    """Read workspace.yaml and parse into dict."""
    ws_path = session_dir / "workspace.yaml"
    if not ws_path.exists():
        return {}
    try:
        content = ws_path.read_text(encoding="utf-8")
        data = {}
        for line in content.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                data[key] = value
        return data
    except Exception:
        return {}


def _read_events_summary(session_dir):
    """Parse events.jsonl to extract key events summary."""
    events_path = session_dir / "events.jsonl"
    if not events_path.exists():
        return {}

    summary = {
        "start_time": None,
        "last_activity": None,
        "model": None,
        "copilot_version": None,
        "user_messages": 0,
        "assistant_messages": 0,
        "tool_calls": 0,
        "errors": 0,
        "total_events": 0,
        "last_message": None,
        "last_message_type": None,
        "last_tool": None,
        "status": "idle",
    }

    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    etype = event.get("type", "")
                    ts = event.get("timestamp", "")
                    data = event.get("data", {})
                    summary["total_events"] += 1

                    if etype == "session.start":
                        summary["start_time"] = ts
                        summary["copilot_version"] = data.get("copilotVersion")
                    elif etype == "session.model_change":
                        summary["model"] = data.get("model", summary.get("model"))
                    elif etype == "user.message":
                        summary["user_messages"] += 1
                        content = data.get("content", "")
                        if content:
                            summary["last_message"] = content[:500]
                            summary["last_message_type"] = "user"
                            summary["status"] = "working"
                    elif etype == "assistant.message":
                        summary["assistant_messages"] += 1
                        content = data.get("content", "")
                        if content:
                            summary["last_message"] = content[:500]
                            summary["last_message_type"] = "assistant"
                    elif etype == "assistant.turn_start":
                        summary["status"] = "working"
                    elif etype == "assistant.turn_end":
                        summary["status"] = "waiting"
                    elif etype == "tool.execution_start":
                        tool_name = data.get("toolName", data.get("name", ""))
                        if tool_name:
                            summary["last_tool"] = tool_name
                            summary["status"] = "working"
                    elif etype == "tool.execution_complete":
                        summary["tool_calls"] += 1
                        result = data.get("result", {})
                        result_content = result.get("content", "") if isinstance(result, dict) else ""
                        if result_content and not summary.get("last_message"):
                            summary["last_message"] = result_content[:500]
                            summary["last_message_type"] = "tool"
                    elif etype == "error":
                        summary["errors"] += 1
                        summary["status"] = "error"

                    if ts:
                        summary["last_activity"] = ts
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return summary


def _read_todos(session_dir):
    """Read todos from session.db."""
    db_path = session_dir / "session.db"
    if not db_path.exists():
        return []

    todos = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT id, title, status, updated_at FROM todos ORDER BY updated_at DESC")
        for row in cursor:
            todos.append({
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "updated_at": row["updated_at"],
            })
        conn.close()
    except Exception:
        pass
    return todos


def _check_waiting(session_dir):
    """Check if session is waiting for user input."""
    events_path = session_dir / "events.jsonl"
    if not events_path.exists():
        return False

    last_type = None
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    etype = obj.get("type", "")
                    if etype in ("user.message", "assistant.message", "assistant.turn_end", "system.message"):
                        last_type = etype
                except Exception:
                    continue
    except Exception:
        return False

    return last_type in ("assistant.message", "assistant.turn_end", "system.message")


def get_system_info():
    """Get general Copilot CLI system info."""
    info = {
        "copilot_state_dir": str(COPILOT_STATE_DIR),
        "active_session_count": len(glob.glob(str(COPILOT_STATE_DIR / "*" / "inuse.*.lock"))),
        "total_session_count": len([d for d in COPILOT_STATE_DIR.iterdir() if d.is_dir()]) if COPILOT_STATE_DIR.exists() else 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    return info
