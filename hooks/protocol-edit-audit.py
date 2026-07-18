#!/usr/bin/env python3
"""PostToolUse (Edit|Write) — repeated-edit detection.

Same file edited N+ times in one session (default 3) surfaces a nudge to stop
guessing and debug systematically, delivered via
hookSpecificOutput.additionalContext (PostToolUse stdout is not otherwise
injected). Logs one `edit-loop` event the first time a file crosses the
threshold.
"""
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from protocol_lib import (append_line, load_config, log_event,
                          once_per_session, read_payload)


def main():
    payload = read_payload()
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path:
        sys.exit(0)

    threshold = load_config().get("advisories", {}).get(
        "repeated_edit_threshold", 3)
    if not threshold:
        sys.exit(0)

    count = append_line(payload, "edits", path)
    if count >= threshold:
        base = os.path.basename(path)
        if once_per_session(payload, f"editloop.{base}"):
            log_event(payload, "edit-loop", "repeated-edit",
                      f"{base} edited {count}x")
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[REPEATED EDIT: {base} edited {count}x this session. If "
                    "this is another attempt at the same fix, stop and debug "
                    "systematically instead of guessing again.]"),
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
