# How it works

Five hook scripts, one shared library, one append-only log. No daemons, no
network calls, no third-party packages.

## The hook events

Claude Code fires hooks at defined points and pipes a JSON payload to each on
stdin. spirit-level uses four events:

| Event | Script | What it does |
|---|---|---|
| `UserPromptSubmit` | `protocol-inject.py` | Prints the baseline; stdout is injected into the model's context |
| `PreToolUse` | `guard.py` | Returns a `deny` decision to block a tool call |
| `PostToolUse` | `protocol-edit-audit.py` | Counts repeated edits, returns `additionalContext` |
| `Stop` | `protocol-stop.py` | End-of-turn advisories via a one-shot `decision: block` |

Only `UserPromptSubmit` (and `SessionStart`) inject plain stdout as context.
`PostToolUse` has to route its message through
`hookSpecificOutput.additionalContext` instead — a detail that is easy to get
wrong and produces a silently non-functional hook.

## Model detection

This is the piece with no documented API, so it is worth explaining.

Hook payloads carry `session_id`, `transcript_path`, `cwd`,
`permission_mode`, and event-specific fields. **They do not carry the model.**
`SessionStart` has an optional `model` field, but it is not guaranteed
present and it goes stale the moment the user switches models mid-session.

The session transcript is a JSONL file, and every assistant message in it
records the model that produced it. So:

```python
with open(transcript_path, "rb") as f:
    f.seek(max(0, size - 262144))      # 256KB tail
    tail = f.read().decode("utf-8", errors="replace")
idx = tail.rfind('"model":"')          # last = current
```

Reading a fixed-size tail keeps this constant-time regardless of session
length — about a millisecond on a multi-megabyte transcript. Because it reads
the *last* recorded model rather than a value captured at session start, it
follows `/model` switches correctly.

If the transcript is missing or contains no model line, the result is
`"unknown"`, which is treated as non-native: the model gets the full
injection. Failing toward more discipline is the safe direction.

**This depends on an undocumented transcript format.** If a future Claude
Code release changes it, detection degrades to `"unknown"` and every model
receives the baseline. That is a graceful failure, not a broken one, but it
is the most likely thing in this repo to need maintenance.

## The deny contract

`PreToolUse` blocks a call by printing JSON and exiting 0:

```json
{"hookSpecificOutput": {
   "hookEventName": "PreToolUse",
   "permissionDecision": "deny",
   "permissionDecisionReason": "[G1] Destructive git over uncommitted work..."}}
```

The reason string is shown to the model, so it should say what to do instead,
not just what was refused. Printing nothing defers to normal permission
handling.

## Advisories without loops

The `Stop` hook can re-engage the model by returning
`{"decision": "block", "reason": "..."}`. Used naively this loops forever:
the model finishes, the hook blocks, the model finishes again, the hook
blocks again.

Two mechanisms prevent that:

1. **`stop_hook_active`** is set on the payload when a Stop hook already
   blocked this turn. The script exits immediately when it sees the flag.
2. **Once-per-session flag files.** Each advisory writes a state file with
   `open(path, "x")` — exclusive creation, so concurrent hooks cannot both
   win the race. Subsequent turns see the file and stay quiet.

## Session state

State lives in `~/.claude/spirit-level/state/`, keyed by the real
`session_id` from the payload. Filenames are sanitized against path traversal
before use.

State files are small and disposable. Delete the directory any time; the
worst outcome is that a once-per-session advisory fires once more.

## The log

Append-only JSONL at `~/.claude/spirit-level/log.jsonl`, written under
`flock` so concurrent hooks cannot interleave partial lines. Nothing rotates
it — a busy month is a few hundred KB. Truncate it whenever you like.

## Composition with existing hooks

Hooks compose: multiple entries on the same event all run. If you already
have a `PreToolUse` Bash hook, add `guard.py` to the existing array rather
than replacing it. Any hook returning `deny` blocks the call, so guards from
different tools stack rather than conflict.

## Performance

Every hook is a short-lived Python process: a few milliseconds of interpreter
startup, one small file read, occasionally a `git` subprocess with a 5-second
timeout. The git calls in `guard.py` only run when a command already matched
a destructive pattern, so the common path does not shell out at all.

## Failure behavior

The guards are designed to fail open rather than block your work:

- Unreadable config → defaults are used and a warning goes to stderr.
  Guards stay **on**, because a typo in a config file should not silently
  disable your safety net.
- `git` missing, or cwd not a repo → the git-dependent guards do not fire.
- Malformed payload → the hook exits quietly without blocking.
