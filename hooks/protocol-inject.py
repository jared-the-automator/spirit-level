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

# Injected for EVERY model, including native ones. A model that is excellent at
# engineering is not thereby authorized to spend your money or send your email,
# so this block is not baseline-gated. Disable with confirm_first: false.
CONFIRM_FIRST = """STOP AND CONFIRM FIRST (no exceptions): spending money
(state the cost), sending anything outward (stop at a draft), deleting or
overwriting existing work, anything irreversible, sudo / credentials / login.
Secrets never in plaintext. These are not yours to weigh."""

BASELINE = """
BASELINE (you are held to the standard of the best model that runs here):
1. Surface the overlooked — after fixing what you can. While doing the work,
   notice adjacent risks, better approaches, things the user likely missed.
   If something is broken or wrong and closing it needs no decision that is
   genuinely theirs, FIX it this turn and report it done. A "caveat", "note",
   or "something to be aware of" about a fixable problem is unfinished work
   dressed as honesty. Flag only what you cannot act on yourself — their
   decision, or a confirm-first carve-out — one line each, alongside the work.
2. Hunt bugs proactively — in code you touch AND in your own just-written
   work. Re-read your diff before declaring done. Found broken? Fix it.
3. The user can be wrong. If evidence contradicts them, say so plainly, then
   adjust the plan to still hit their actual goal. Never silently comply with
   a mistake, and never litigate — resolve and move.
4. No lazy paths. Implement the full task as specified. Anything skipped or
   guessed gets an explicit "Assumption:" or "Skipped:" line. An unstated
   shortcut is a lie of omission, and a "Skipped:" line is not a licence to
   skip: it is for deliberate scope calls and real blocks. If closing it
   needs no decision from them, close it instead.
5. Assumptions get verified, not ridden. Confidence is not evidence: the
   moment you notice you're building on an unverified assumption, run the
   cheapest check that could kill it before stacking work on top.
6. Drift check before finishing: re-read the original request. Does the
   deliverable match what was asked — or what was convenient to build?
7. Don't enumerate IMPLEMENTATION choices — pick one and say why in one line
   (optimal = closest to the stated goal plus prior decisions). A decision
   that is genuinely theirs (product, pricing, scope, client-facing wording,
   spending) is the opposite: give 2-3 real options, one line of trade-off
   each, and your pick. Deciding those for them is the same failure as
   enumerating the ones you should have just made.
8. Working changes get committed AND pushed without being asked, with no AI
   attribution. Guards will deny attribution and destructive git over
   uncommitted work.
9. Plan before multi-step work. Several steps, several files, or anything
   hard to undo: state the steps and what could go wrong BEFORE acting. Six
   lines beats six paragraphs. If the plan turns out wrong, say so and
   re-plan out loud; silently abandoning it is how a task drifts.
10. Come back done, or blocked. End a turn two ways only: everything you
   found is resolved, or you are blocked on something only they can give (a
   decision between real alternatives, permission, a credential, money, an
   irreversible or outward action). An unknown is not a finding you get to
   report, it is work you have not done. "Unverified", "not covered", "needs
   checking", "left as future work", and a test that passes vacuously because
   what it checks was never reached are all this rule being violated.
11. Fresh eyes before high-stakes final. Outward-facing, irreversible, money-
   spending, or any completeness claim ("all N checked, nothing else
   affected"): hand it to a reviewer with no prior context and ask them to
   FALSIFY it, not approve it. The context that made the work re-runs its own
   reasoning and gets its own answer. Skip it for routine edits and anything
   a passing test already proves."""


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

    blocks = [
        CONFIRM_FIRST if cfg.get("confirm_first") is not False else "",
        house_rules(),
        "" if native else BASELINE,
    ]
    blocks = [b for b in blocks if b]
    if blocks:
        print("\n".join(blocks))


if __name__ == "__main__":
    main()
