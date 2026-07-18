#!/usr/bin/env python3
"""Stop hook — spirit-level advisories.

1. Unpushed-commits advisory: if the cwd repo has commits ahead of upstream
   at end of turn, surface it once per session.
2. Optional turn-interval reminder (configure `turn_interval_reminder` and
   `turn_reminder_text`); disabled by default.

Advisory tier: it blocks the stop ONCE per session per rule to put the notice
in front of the model, then never again that session, so no loops. The
`stop_hook_active` flag is respected so a blocked stop never re-blocks.
"""
import json
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from protocol_lib import (counter_bump, load_config, log_event,
                          once_per_session, read_payload)


def unpushed(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd or ".", "rev-list", "--count", "@{u}..HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return int(out.stdout.strip()) if out.returncode == 0 else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def main():
    payload = read_payload()
    if payload.get("stop_hook_active"):
        sys.exit(0)

    adv = load_config().get("advisories", {})
    reasons = []

    interval = adv.get("turn_interval_reminder") or 0
    if interval > 0:
        count = counter_bump(payload, "turns")
        if count % interval == 0 and adv.get("turn_reminder_text"):
            reasons.append(f"[TURN {count}] {adv['turn_reminder_text']}")

    if adv.get("unpushed_commits"):
        n = unpushed(payload.get("cwd"))
        if n and once_per_session(payload, "unpushed-nag"):
            log_event(payload, "advisory", "push-after-commit",
                      f"{n} unpushed commit(s) at end of turn")
            reasons.append(
                f"[ADVISORY — {n} unpushed commit(s) in this repo. Push now, "
                "or state the one-line reason not to, then finish your reply.]")

    if reasons:
        print(json.dumps({"decision": "block", "reason": "\n".join(reasons)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
