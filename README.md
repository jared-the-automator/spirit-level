# spirit-level

Your best model catches its own bugs before you do. Your cheap model ships them and reports success.

spirit-level takes the working habits of the good one, writes them down as explicit rules, and injects them only into the sessions where a lesser model is driving. The failures that no amount of instruction prevents get blocked at the tool-call layer instead.

A spirit level tells you whether something is true or only looks it. Same job.

## The problem

You settle into a rhythm with a model that works. It re-reads its own diff. It tells you when you're wrong and then hits your goal anyway instead of arguing about it. It checks an assumption before building three files on top of it.

Then you switch. Cost, availability, a long-context run, whatever the reason. Now you're working with something that takes the shortest path technically satisfying the request, states guesses with total confidence, and declares victory without running anything.

Relearning how to talk to your tools every few months is not a workflow.

## What it does

Four tiers, running off four hook events.

**Guarded.** A PreToolUse hook denies the call before it runs. Destructive git over uncommitted work, AI attribution in commit messages, credential-shaped strings headed for a file that isn't `.env` (whether written by the Write tool or shoved there by a heredoc, a redirect, or `tee`). These don't depend on the model cooperating and they cost zero tokens. You override any of them with a `GUARD_OK=1` prefix, which gets logged as a bypass.

**Confirm first.** One block injected for every model, the good one included: money, outward sends, deletion, anything irreversible, sudo. Capability is not authorization, so this one isn't gated on which model is driving.

**Baseline.** Eleven rules, roughly 800 tokens, injected each turn for the models that need them. Surface what got overlooked. Hunt bugs in your own diff. Verify assumptions instead of riding them. Plan before multi-step work. Come back done or blocked, because an unknown is work you haven't done rather than a finding you get to report.

**Advisory.** Unpushed commits at end of turn. The same file edited three times, which usually means guessing rather than debugging.

Everything that fires lands in a JSONL log you can query with `jq`.

## The honest part

A system prompt cannot make a model smarter. It can't add capability that isn't already in the weights, and anyone selling you a pasted-in system prompt as an intelligence upgrade is selling you nothing.

It does elicitation. It changes which behaviors the model reaches for by default, which is a real difference in output quality and a different thing from raising the ceiling.

That's also why the injection is gated. Telling a model to behave like itself costs about 800 tokens a turn and buys you nothing back. Models you list in `native_models` still get the confirm-first block and your house rules, and skip the rest.

## How the gating works

Claude Code's hook payloads don't include the active model. The session transcript records `"model"` on every assistant message and hooks receive `transcript_path`, so reading a 256KB tail of that file returns the current model in about a millisecond. It follows mid-session `/model` switches, which a value captured at session start doesn't.

An unrecognized model counts as non-native and receives the full injection. Failing toward more discipline is the safe direction.

This rides on an undocumented transcript format. If a future release changes it, detection degrades to "unknown" and every model gets the baseline. Graceful, but it's the piece in here most likely to need maintenance.

## Install

```bash
git clone https://github.com/jared-the-automator/spirit-level.git
cd spirit-level
./install.sh
```

The installer copies hooks to `~/.claude/spirit-level/hooks/`, writes a default `config.json`, and prints the `settings.json` block to paste. It doesn't edit your settings, because that file is yours.

Your own always-on rules go in `~/.claude/spirit-level/hooks/house-rules.md`. It ships empty and injects nothing until you fill it.

Uninstall is `rm -rf ~/.claude/spirit-level` and deleting the settings block.

## Configure

`~/.claude/spirit-level/config.json`:

```json
{
  "native_models": ["claude-fable"],
  "confirm_first": true,
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

Set `native_models` to whichever models already behave the way you want. Every guard and advisory switches off individually. Details in [docs/CONFIGURING.md](docs/CONFIGURING.md).

## What's in here

| Path | What it is |
|---|---|
| `hooks/` | Four hooks plus a shared library. Python 3, standard library only. |
| `protocol/PROTOCOL.md` | Every rule, the failure each one inverts, and how to maintain it. |
| `docs/` | How it works, configuring, writing your own guards. |
| `tests/` | 101 fixture assertions. `./tests/run.sh` |

## Companion: bitch-stop-lyin

Baseline rule 5 says assumptions get verified rather than ridden. The enforcement arm of that idea lives in its own repo.

[bitch-stop-lyin](https://github.com/jared-the-automator/bitch-stop-lyin) stops the agent asserting things it never checked, built around a taxonomy of the six excuses a model uses to skip a check. It works standalone and needs nothing from here. (The name is an Ice Cube line and it's addressed to the agent. Rename the directory if it won't fly at your job.)

```bash
git clone https://github.com/jared-the-automator/bitch-stop-lyin.git
cp -r bitch-stop-lyin ~/.claude/skills/
```

## Prior art

Distilling a strong model's system prompt into rules for weaker ones isn't my idea. It got popular after a system prompt leak, and plenty of people published "lite" versions. This is my take, with three differences I haven't seen elsewhere.

It's model-gated, so your best model doesn't pay tokens to be told how to be itself. It's enforced, so the guard tier blocks tool calls instead of asking nicely. And it's derived from watching a model work rather than from a leaked prompt, so every rule is the inverse of a failure I watched happen.

## Requirements

Claude Code, Python 3.8+, git. Linux and macOS. No third-party packages.

## License

MIT. See [LICENSE](LICENSE).
