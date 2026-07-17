"""Send messages to Copilot CLI sessions via TTY or CLI.

This module first tries to deliver the message to a running Copilot
process by writing to its controlling TTY (if present). If no active
process with a TTY is found or writing to the TTY fails (permissions),
it falls back to launching a short-lived `copilot -p` process to submit
the prompt. The subprocess path is run with a short timeout so the API
remains responsive.
"""

import logging
import subprocess
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _find_copilot_processes(session_id: str) -> list[dict]:
    """Find copilot-related processes whose argv contains (prefix of) session id."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        procs = []
        for line in result.stdout.splitlines():
            if "copilot" not in line.lower():
                continue
            if session_id[:8] not in line:
                continue
            if "copilot_status" in line:
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            pid = int(parts[1])
            tty = parts[6]
            procs.append({"pid": pid, "tty": tty, "line": line})
        return procs
    except Exception:
        return []


def _find_interactive_pid(session_id: str) -> Optional[int]:
    """Return PID of a copilot process that has a real TTY (not '??')."""
    procs = _find_copilot_processes(session_id)
    for p in procs:
        tty = p.get("tty")
        if tty and tty != "??" and not tty.startswith("??"):
            return p.get("pid")
    return None


def _get_tty_path(tty_name: str) -> str:
    if tty_name.startswith("/dev/"):
        return tty_name
    if not tty_name.startswith("tty"):
        return f"/dev/tty{tty_name}"
    return f"/dev/{tty_name}"


def _write_to_tty(tty_path: str, message: str) -> dict:
    try:
        with open(tty_path, "wb", buffering=0) as f:
            f.write((message + "\n").encode("utf-8", errors="replace"))
            time.sleep(0.1)
        return {"success": True, "output": "", "error": ""}
    except PermissionError as e:
        return {"success": False, "output": "", "error": f"permission denied: {e}"}
    except FileNotFoundError:
        return {"success": False, "output": "", "error": f"TTY {tty_path} not found"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def send_message(session_id: str, message: str, cwd: str = None, timeout: int = 8) -> dict:
    """Try TTY delivery first, then fall back to `copilot -p`.

    Returns dict {success, output, error}.
    """
    pid = _find_interactive_pid(session_id)
    if pid:
        # find tty name
        try:
            out = subprocess.check_output(["ps", "-p", str(pid), "-o", "tty="], text=True)
            tty_name = out.strip()
            if tty_name and tty_name != "??":
                tty_path = _get_tty_path(tty_name)
                logger.info("Attempting TTY delivery to %s (pid=%s)", tty_path, pid)
                res = _write_to_tty(tty_path, message)
                if res.get("success"):
                    return res
                logger.info("TTY delivery failed: %s", res.get("error"))
        except Exception as e:
            logger.debug("Unable to determine TTY for pid %s: %s", pid, e)

    # Fallback: run copilot -p with short timeout
    copilot = shutil.which("copilot")
    if not copilot:
        return {"success": False, "output": "", "error": "copilot CLI not found"}

    cmd = [copilot, f"--session-id={session_id}", "-p", message, "--allow-all-tools", "--no-auto-update", "--output-format", "json"]
    logger.info("Running fallback copilot -p for session %s", session_id[:8])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        success = proc.returncode == 0
        return {"success": success, "output": out, "error": err}
    except subprocess.TimeoutExpired as e:
        out = (getattr(e, 'stdout', None) or "").strip()
        err = (getattr(e, 'stderr', None) or "").strip()
        return {"success": False, "output": out, "error": "timeout" + ("; " + err if err else "")}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def check_session_waiting(session_dir: str) -> bool:
    events_path = Path(session_dir) / "events.jsonl"
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
                    import json
                    obj = json.loads(line)
                    etype = obj.get("type", "")
                    if etype in ("user.message", "assistant.message", "assistant.turn_end", "system.message"):
                        last_type = etype
                except Exception:
                    continue
    except Exception:
        return False
    return last_type in ("assistant.message", "assistant.turn_end", "system.message")