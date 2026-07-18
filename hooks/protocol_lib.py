"""Shared library for spirit-level protocol hooks.

Every hook receives a JSON payload on stdin carrying session_id,
transcript_path, cwd, and event-specific fields. This module parses it,
resolves the active model from the transcript (mid-session model switches
included), loads user config, and appends events to the enforcement log.
"""
import fcntl
import json
import os
import re
import sys
import time

PROTOCOL_DIR = os.path.expanduser(
    os.environ.get("SPIRIT_LEVEL_DIR", "~/.claude/spirit-level"))
LOG_PATH = os.path.join(PROTOCOL_DIR, "log.jsonl")
STATE_DIR = os.path.join(PROTOCOL_DIR, "state")
CONFIG_PATH = os.path.join(PROTOCOL_DIR, "config.json")

DEFAULT_CONFIG = {
    # Models whose ID starts with any of these are treated as already
    # exhibiting the baseline; they get the slim block, not the full inject.
    "native_models": ["claude-fable"],
    "guards": {
        "destructive_git_over_wip": True,
        "ai_attribution_in_commits": True,
        "plaintext_secrets": True,
    },
    # Optional repo-to-remote pinning. Each entry blocks `git push` and
    # `git remote add|set-url` naming a forbidden remote while inside a repo
    # whose toplevel equals `repo`. Example:
    #   {"repo": "/home/me/workspace",
    #    "forbid_remote": "me/other-project",
    #    "reason": "unrelated histories",
    #    "exempt_path_contains": "other-project"}
    "remote_pins": [],
    "advisories": {
        "unpushed_commits": True,
        "repeated_edit_threshold": 3,
        "turn_interval_reminder": 0,   # 0 disables; N reminds every N turns
        "turn_reminder_text": "",
    },
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    try:
        with open(CONFIG_PATH) as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        # A broken config must never silently disable the guards.
        print(f"spirit-level: config unreadable ({e}); using defaults",
              file=sys.stderr)
    return cfg


def read_payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def current_model(payload):
    """Last assistant model recorded in the transcript. Unknown -> 'unknown',
    which downstream treats as non-native: injecting into an unrecognized
    model is the safe failure direction."""
    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return "unknown"
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            # Model lines appear on every assistant message; a 256KB tail is
            # hundreds of messages of headroom.
            f.seek(max(0, size - 262144))
            tail = f.read().decode("utf-8", errors="replace")
        idx = tail.rfind('"model":"')
        if idx == -1:
            return "unknown"
        start = idx + len('"model":"')
        end = tail.find('"', start)
        return tail[start:end] if end != -1 else "unknown"
    except OSError:
        return "unknown"


def is_native(model, cfg=None):
    cfg = cfg or load_config()
    return any(model.startswith(p) for p in cfg.get("native_models", []))


def log_event(payload, event, rule="", detail="", model=None):
    os.makedirs(PROTOCOL_DIR, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": (payload.get("session_id") or "unknown")[:12],
        "model": model if model is not None else current_model(payload),
        "event": event,
        "rule": rule,
        "detail": detail[:400],
        "cwd": payload.get("cwd") or "",
    }
    with open(LOG_PATH, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    return entry


def _state_file(payload, key):
    os.makedirs(STATE_DIR, exist_ok=True)
    session = (payload.get("session_id") or "unknown")[:12]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{session}.{key}")
    return os.path.join(STATE_DIR, safe)


def once_per_session(payload, key):
    """True the first time `key` is seen this session, False after. Backed by
    exclusive file creation so concurrent hooks stay correct."""
    try:
        with open(_state_file(payload, key), "x"):
            pass
        return True
    except FileExistsError:
        return False


def counter_bump(payload, key):
    """Increment and return a session-scoped counter."""
    with open(_state_file(payload, key + ".count"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read().strip()
        count = (int(raw) if raw.isdigit() else 0) + 1
        f.seek(0)
        f.truncate()
        f.write(str(count))
        fcntl.flock(f, fcntl.LOCK_UN)
    return count


def append_line(payload, key, line):
    """Append a line to a session-scoped list; return how many times that
    exact line now appears (repeated-edit detection)."""
    with open(_state_file(payload, key + ".list"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line + "\n")
        f.seek(0)
        count = sum(1 for line_ in f if line_.rstrip("\n") == line)
        fcntl.flock(f, fcntl.LOCK_UN)
    return count
