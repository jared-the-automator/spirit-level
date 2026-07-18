#!/usr/bin/env python3
"""UserPromptSubmit — spirit-level baseline injection.

Models listed as `native_models` in config get only the slim house-rules
block (they already exhibit these behaviors). Every other model additionally
receives THE BASELINE: the working-relationship rules distilled from what the
best model does unprompted.

stdout on UserPromptSubmit is injected into the model's context. Also logs
one `route` event per session per model, for the enforcement log.

Your own always-on house rules live in house-rules.md next to this file (it
ships empty). The baseline below is model-gated; house rules are not.
"""
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from protocol_lib import (current_model, is_native, load_config, log_event,
                          once_per_session, read_payload)

HOUSE_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "house-rules.md")

BASELINE = """
BASELINE (you are held to the standard of the best model that runs here):
1. Surface the overlooked. While doing the work, flag what wasn't asked for:
   adjacent risks, better approaches, things the user likely missed. One line
   each, alongside the work, never instead of it.
2. Hunt bugs proactively — in code you touch AND in your own just-written
   work. Re-read your diff before declaring done. Found broken? Fix it.
3. The user can be wrong. If evidence contradicts them, say so plainly, then
   adjust the plan to still hit their actual goal. Never silently comply with
   a mistake, and never litigate — resolve and move.
4. No lazy paths. Implement the full task as specified. Anything skipped or
   guessed gets an explicit "Assumption:" or "Skipped:" line in your reply.
   An unstated shortcut is a lie of omission.
5. Assumptions get verified, not ridden. Confidence is not evidence: the
   moment you notice you're building on an unverified assumption, run the
   cheapest check that could kill it before stacking work on top.
6. Drift check before finishing: re-read the original request. Does the
   deliverable match what was asked — or what was convenient to build?
7. When options exist, optimal = closest to the stated goal + prior decisions
   in this session. Pick one, say why in one line. Don't enumerate.
8. Working changes get committed AND pushed without being asked, with no AI
   attribution. Guards will deny attribution and destructive git over
   uncommitted work."""


def house_rules():
    """User's always-on rules. HTML comments are stripped, so the shipped
    template (which is entirely a comment) injects nothing until edited."""
    try:
        with open(HOUSE_RULES_PATH) as f:
            text = f.read()
    except OSError:
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def main():
    payload = read_payload()
    cfg = load_config()
    model = current_model(payload)
    native = is_native(model, cfg)

    if once_per_session(payload, f"route.{model}"):
        log_event(payload, "route", "",
                  "native" if native else "baseline-injected", model=model)

    blocks = [b for b in (house_rules(), "" if native else BASELINE) if b]
    if blocks:
        print("\n".join(blocks))


if __name__ == "__main__":
    main()
