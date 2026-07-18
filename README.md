# spirit-level

**Hold every model to the standard of your best one.**

A behavioral protocol for [Claude Code](https://claude.com/claude-code): the
working habits of a top-tier model, written down as explicit rules, injected
only into sessions where a lesser model is driving, with the failure modes
that rules alone can't stop blocked at the tool-call layer.

A spirit level is the instrument that tells you whether something is actually
true, or only looks it. Same job here.

---

## The problem

You settle into a rhythm with a good model. It finds bugs in its own work
before you do. It tells you when you are wrong, then solves the problem
anyway. It checks assumptions instead of riding them.

Then you switch models — for cost, for availability, for a long-context run —
and you are working with something that takes the shortest path that
technically satisfies the request, states guesses with total confidence, and
declares victory without running anything.

You should not have to relearn how to talk to your tools every few months.

## The approach

Take the behaviors you get for free from the good model. Write them down.
Inject them into every session where the good model is *not* driving. Then
guard the handful of failures that no amount of instruction reliably
prevents.

Three tiers:

**Guarded** — a PreToolUse hook denies the call before it runs. Destructive
git over uncommitted work, AI attribution in commit messages, plaintext
secrets headed for the wrong file. These do not depend on the model
cooperating, and they cost zero tokens. A human can override any of them with
a logged `GUARD_OK=1` prefix.

**Baseline** — eight rules injected each turn, *only* for models that need
them. Surface what was overlooked. Hunt bugs in your own diff. The user can
be wrong — say so, then hit the goal anyway. No lazy paths. Verify
assumptions instead of riding them. Drift-check before finishing.

**Advisory** — non-blocking nudges. Unpushed commits at end of turn. The same
file edited three times, which almost always means guessing rather than
debugging.

Everything that fires is appended to a JSONL log you can query with `jq`.

## The honest part

**A system prompt cannot make a model smarter.** It cannot add capability
that is not already in the weights, and nothing here claims otherwise.

What it does is *elicitation* — changing which behaviors the model reaches
for by default. That is a real and useful difference in output quality, and
it is a different thing from raising the ceiling. Anyone selling you a
pasted-in system prompt as an intelligence upgrade is overselling it.

This is also why the injection is model-gated: sending a model instructions
to behave like itself is pure token waste. Models you list as `native_models`
get nothing but your own house rules.

## How the model gating works

Claude Code's hook payloads do not include the active model. But the session
transcript records `"model"` on every assistant message, and hooks receive
`transcript_path`. Reading the tail of that file gives you the current model
in about a millisecond, and it tracks mid-session `/model` switches
correctly — which a value captured at session start would not.

An unrecognized model is treated as non-native and gets the full injection.
Failing toward more discipline is the safe direction.

## Install

```bash
git clone https://github.com/jared-the-automator/spirit-level.git
cd spirit-level
./install.sh
```

The installer copies the hooks to `~/.claude/spirit-level/hooks/`, writes a
default `config.json`, and prints the exact `settings.json` block to paste in
(it does not edit your settings for you — that file is yours).

Then put your own always-on rules in
`~/.claude/spirit-level/hooks/house-rules.md`. It ships empty and injects
nothing until you fill it.

Uninstall is `rm -rf ~/.claude/spirit-level` plus deleting the settings block.

## Configure

`~/.claude/spirit-level/config.json`:

```json
{
  "native_models": ["claude-fable"],
  "guards": {
    "destructive_git_over_wip": true,
    "ai_attribution_in_commits": true,
    "plaintext_secrets": true
  },
  "remote_pins": [],
  "advisories": {
    "unpushed_commits": true,
    "repeated_edit_threshold": 3,
    "turn_interval_reminder": 0,
    "turn_reminder_text": ""
  }
}
```

Set `native_models` to whichever models already behave the way you want.
Every guard and advisory can be switched off individually. See
[docs/CONFIGURING.md](docs/CONFIGURING.md).

## What's in here

| Path | What it is |
|---|---|
| `hooks/` | Five hook scripts. Python 3, standard library only. |
| `protocol/PROTOCOL.md` | The complete rule set and the reasoning behind each rule. |
| `skills/verification-gate/` | Standalone skill that stops the agent asserting unverified things. Works without the rest of this repo. |
| `docs/` | How it works, configuring, writing your own guards. |
| `tests/` | Fixture-based test suite. `./tests/run.sh` |

## Prior art and credit

The idea of distilling a strong model's system prompt into rules for other
models is not mine. It became a popular topic after a widely-circulated
system prompt leak, and a number of people published "lite" distillations.
This is my version of that idea, with three differences I have not seen
elsewhere:

1. It is **model-gated**, so the strong model does not pay for instructions
   describing its own behavior.
2. It is **enforced, not suggested** — the guard tier blocks tool calls
   rather than asking nicely.
3. It is **derived from observed behavior**, not from a leaked prompt. Every
   rule is the inverse of a failure watched in practice.

The verification-gate skill predates all of this and was built the slow way:
one patch per real incident, then compressed once the patching became the
problem.

## Requirements

Claude Code, Python 3.8+, git. Linux and macOS. No third-party packages.

## License

MIT. See [LICENSE](LICENSE).
