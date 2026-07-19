# Configuring

All settings live in `~/.claude/spirit-level/config.json`. Missing keys fall
back to defaults, so a partial config is valid. Set
`SPIRIT_LEVEL_DIR` to relocate everything.

## `native_models`

```json
"native_models": ["claude-fable"]
```

A list of model-ID **prefixes**. A model whose ID starts with any of these is
considered to already exhibit the baseline, and gets only the confirm-first
block plus your house rules, not the eleven injected rules.

Set this to whichever model you are happiest with. If you are unsure, set it
to `[]`: every model then gets the baseline, which costs roughly 800 tokens
per turn and is never harmful, only occasionally redundant.

Find current model IDs in `~/.claude/settings.json` or by checking a recent
session transcript.

## `confirm_first`

```json
"confirm_first": true
```

Injects the stop-and-confirm block (money, outward sends, deletion,
irreversible actions, sudo) for **every** model, including ones listed in
`native_models`. On by default.

Being the best model in the room is not authorization to spend money or send
mail on someone's behalf, so this block is deliberately not gated the way the
baseline is. Set it to `false` if your agent has no outward reach at all and
the reminder is noise.

## `guards`

```json
"guards": {
  "destructive_git_over_wip": true,
  "ai_attribution_in_commits": true,
  "plaintext_secrets": true
}
```

Each is independently switchable. Turn off `ai_attribution_in_commits` if you
*want* attribution trailers in your history. `plaintext_secrets` covers both the
Write/Edit path and shell writes (redirects, heredocs, `tee`). The other two
are worth keeping on: they block irreversible outcomes, and the `GUARD_OK=1` prefix is always
available when you genuinely mean it.

## `remote_pins`

Off by default. Blocks pushing a specific repo to a specific remote:

```json
"remote_pins": [
  {
    "repo": "/home/you/workspace",
    "forbid_remote": "you/other-project",
    "reason": "unrelated histories",
    "exempt_path_contains": "other-project"
  }
]
```

- `repo` — absolute path, matched against `git rev-parse --show-toplevel`.
  The guard only fires inside exactly this repo.
- `forbid_remote` — substring matched case-insensitively against the command.
- `reason` — optional, included in the denial message.
- `exempt_path_contains` — optional. Commands that explicitly target a nested
  path containing this string (via `git -C <path>` or `cd <path>`) are
  allowed, so a nested checkout of the other project still works normally.

Useful when one repo contains a checkout of another and the two must never
cross-contaminate. If that has never happened to you, leave this empty.

## `advisories`

```json
"advisories": {
  "unpushed_commits": true,
  "repeated_edit_threshold": 3,
  "turn_interval_reminder": 0,
  "turn_reminder_text": ""
}
```

- `unpushed_commits` — once per session, at end of turn, if the repo is ahead
  of upstream.
- `repeated_edit_threshold` — fire after this many edits to one file in a
  session. `0` disables. Lower it to 2 if you want an earlier signal.
- `turn_interval_reminder` / `turn_reminder_text` — off by default. Set the
  first to N and the second to any string to surface a reminder every N
  turns. Useful for context checks or checkpoint prompts.

## House rules

`~/.claude/spirit-level/hooks/house-rules.md` is injected into **every**
session regardless of model, like the confirm-first block. Use it for rules about your setup rather than
about model behavior — which docs tool to check first, where project context
lives, which skills are mandatory for which task types.

Keep it short. It is paid for on every turn. An empty file injects nothing.

## Editing the baseline

The eleven rules are a string constant in `protocol-inject.py`. Edit it
directly. Two things to keep in mind:

1. `install.sh` overwrites the hooks. Keep your edits in a fork, or re-apply
   after upgrading.
2. Length is the real constraint. This text is paid for on every turn of
   every non-native session. Adding a twelfth rule is cheap; adding a twelfth
   paragraph is not. If a rule needs explaining, put the explanation in a
   skill the model can load on demand and keep the injected line to one
   sentence.

## Verifying it works

Start a new session and check the log:

```bash
tail -1 ~/.claude/spirit-level/log.jsonl
```

You should see a `route` event naming the current model, with detail
`baseline-injected` or `native`. If nothing appears, the hooks are not wired
into `settings.json` — re-run `install.sh` and paste the printed block.

To confirm a guard fires, in a repo with uncommitted changes ask the agent to
run `git reset --hard HEAD~1`. It should be denied with a `[G1]` reason, and
a `deny` event should appear in the log.
