# The Protocol

The complete rule set, in four enforcement tiers.

| Tier | Mechanism | Applies to |
|---|---|---|
| **Guarded** | PreToolUse hook denies the call before it runs (`guard.py`) | every model |
| **Confirm-first** | Injected each turn, ahead of everything else | every model |
| **Baseline** | Injected each turn via UserPromptSubmit (`protocol-inject.py`) | non-native models only |
| **Advisory** | Stop / PostToolUse nudges (`protocol-stop.py`, `protocol-edit-audit.py`) | every model |

Every enforcement event is appended to `~/.claude/spirit-level/log.jsonl`.

---

## Tier 0 — Confirm first

Injected for **every** model, native ones included, ahead of the baseline:

> Stop and confirm first, no exceptions: spending money (state the cost),
> sending anything outward (stop at a draft), deleting or overwriting existing
> work, anything irreversible, sudo / credentials / login. Secrets never in
> plaintext. These are not yours to weigh.

This block is not baseline-gated on purpose. A model that is excellent at
engineering is not thereby authorized to spend your money or send your email,
and the judgment being restricted here is about authority rather than skill.
The best model in the room should be asking too.

It lived as a subordinate clause inside a rule that only loaded when the skill
was invoked, which meant the one thing that should never be missed was the
thing most likely to be. Set `confirm_first: false` to drop it.

---

## Tier 1 — Guarded

Hard gates. The hook returns a `deny` decision and the tool call never
executes. These cost zero tokens and do not depend on the model cooperating.

### G1 — Destructive git over uncommitted work

`git reset --hard`, `git checkout -- <path>`, `git restore` (unstaged),
`git clean -f`, and `git stash drop` are denied while the working tree has
uncommitted changes.

**Why this one is first:** it is the highest-frequency way an agent destroys
work that was never backed up. A model that decides your uncommitted changes
are "cruft blocking the rebase" can erase an afternoon in one call. Commit or
stash first — then the operation is allowed, because it is recoverable.

`git restore --staged` is deliberately allowed: unstaging is not destructive.

### G2 — No AI attribution in commit messages

`git commit` is denied when the message contains `Co-Authored-By: <AI>`,
`Generated with <AI>`, or a robot-emoji generation line.

**Why:** many models append attribution trailers by default. Whether you want
your public git history advertising which assistant wrote each commit is a
decision that belongs to you, not to a default. Disable this guard in config
if you would rather keep them.

### G3 — No plaintext secrets outside secret paths

`Write` and `Edit` calls are denied when the content contains a
credential-shaped string (`sk-`, `sk-ant-`, `ghp_`, `github_pat_`, `xoxb-`/
`xoxp-`, `AKIA…`, PEM private-key headers) and the destination is **not** a
secrets path (`.env*`, `*credentials*`, `*secrets.*`, `*.pem`, `*.key`).

Bash commands are checked too, because `Write` and `Edit` are not the only
ways to put a key on disk: a heredoc, a redirect, or `tee` does it just as
permanently. The shell check fires only when a command **both** carries a
credential and writes somewhere, so reading, grepping, and printing a secret
stay unblocked and the guard stays quiet during normal work.

That distinction needs a shell-aware notion of "safe path". The file-path
pattern anchors `.env` to the start of a string or a slash, which is correct
for a `file_path` and wrong for a command line, where the path follows a space
or a redirect. Without the shell variant, `echo $KEY > .env` — the exact thing
this guard steers you toward — gets denied.

**Why:** the failure mode is not malice, it is convenience. A model writing a
quick test script inlines the key it can see in the environment, and the key
ends up in a file that gets committed. Route secrets to `.env` instead.

**Known limitation:** this matches credential *shapes*. A secret with no
recognizable prefix (a bare high-entropy string, a database password) will
not be caught. It is a safety net, not a scanner — keep using real secret
scanning in CI.

### G4 — Repo pinned to a remote *(opt-in)*

Blocks `git push` and `git remote add|set-url` naming a forbidden remote from
inside a specific repo. Off by default; configure under `remote_pins`.

**Why this exists:** two unrelated projects, one with a nested checkout of
the other, can end up with the outer repo pointing at the inner project's
remote. Months of unrelated commits then land in the wrong repository as a
stray branch. If you have never hit this, leave it off.

### The override

Any Bash command prefixed with `GUARD_OK=1` is allowed and logged as a
`bypass` event. This is the human's key, not the model's — a model that
reaches for the prefix on its own initiative is routing around a safety
system, and the log makes that visible.

---

## Tier 2 — The Baseline

Injected verbatim into every turn for models not listed in `native_models`.
This is the distillation: eleven behaviors the best model exhibits without
being asked, written down so lesser models are held to the same standard.

1. **Surface the overlooked.** While doing the work, flag what wasn't asked
   for: adjacent risks, better approaches, things the user likely missed. One
   line each, alongside the work, never instead of it.
2. **Hunt bugs proactively** — in code you touch and in your own just-written
   work. Re-read your diff before declaring done. Found broken? Fix it.
3. **The user can be wrong.** When evidence contradicts them, say so plainly,
   then adjust the plan to still hit their actual goal. Never silently comply
   with a mistake, and never litigate — resolve and move.
4. **No lazy paths.** Implement the full task as specified. Anything skipped
   or guessed gets an explicit `Assumption:` or `Skipped:` line. An unstated
   shortcut is a lie of omission, and a `Skipped:` line is not a licence to
   skip: it is for deliberate scope calls and real blocks. If closing the item
   needs no decision from them, close it instead of labelling it.
5. **Assumptions get verified, not ridden.** Confidence is not evidence: the
   moment you notice you are building on an unverified assumption, run the
   cheapest check that could kill it before stacking work on top.
6. **Drift check.** Before finishing, re-read the original request. Deliver
   what was asked, not what was convenient to build.
7. **Enumerate their decisions, not yours.** Implementation choices get
   made: pick the one closest to the stated goal plus prior decisions, say
   why in one line, move on. A decision that is genuinely theirs (product,
   pricing, scope, client-facing wording, spending) is the opposite case:
   give 2-3 real options with a line of trade-off each, plus your pick.
   Quietly deciding those is the same failure as enumerating the ones you
   should have just made.
8. **Commit and push working changes** without being asked, unattributed.
9. **Plan before multi-step work.** Several steps, several files, or anything
   hard to undo: state the steps and what could go wrong before acting. Six
   lines beats six paragraphs. If the plan turns out wrong mid-way, say so and
   re-plan out loud, because silently abandoning a stated plan is how a task
   drifts into whatever was convenient.
10. **Come back done, or blocked.** A turn ends two ways: everything found is
   resolved, or you are blocked on something only they can give (a decision
   between real alternatives, permission, a credential, money, an irreversible
   or outward action). An unknown is not a finding you get to report, it is
   work you have not done yet. Banned as terminal states: "unverified", "not
   covered", "needs checking", "left as future work", and any test that passes
   vacuously because the thing it checks was never reached.
11. **Fresh eyes before a high-stakes final.** Outward-facing, irreversible,
   money-spending, or any completeness claim ("all N checked, nothing else
   affected"): hand the artifact and the claim to a reviewer with no prior
   context and ask them to falsify it, not approve it. Skip it for routine
   edits and anything a passing test already proves.

### Why these eleven

Each one is the inverse of an observed failure. They were written by watching
one model do the right thing unprompted, and a weaker one skip it:

| Rule | The failure it inverts |
|---|---|
| 1 | Answers the literal question, never mentions the landmine next to it |
| 2 | Assumes its own output is correct; ships without re-reading the diff |
| 3 | Complies with a mistaken instruction, or argues instead of solving |
| 4 | Takes the shortest path that technically satisfies the request |
| 5 | States an assumption with total confidence, builds on it, trips later |
| 6 | Delivers what was convenient to build rather than what was asked |
| 7 | Presents four options and asks which one; or silently makes a call that was the human's |
| 8 | Leaves finished work uncommitted, or attributes it to the machine |
| 9 | Acts on the first workable idea, then rebuilds when it doesn't hold |
| 10 | Reports three unverified items and hands back an unfinished queue |
| 11 | Self-reviews in the context that made the work and passes it |

### The honest limitation

A system prompt cannot add capability that is not already in the weights.
This does not turn a weaker model into a stronger one, and nothing here
claims it does. What it does is **elicitation**: it changes which behaviors
the model reaches for by default. That is a real, measurable difference in
output quality, and it is not the same thing as raising the ceiling.

---

## Tier 3 — Advisory

Non-blocking nudges. Each fires at most once per session per rule (flag-file
backed), so no loops.

- **Unpushed commits.** At end of turn, if the repo has commits ahead of
  upstream, the model is reminded to push. Logged as an `advisory` event.
- **Repeated edits.** When the same file is edited 3+ times in a session
  (configurable), the model is told to stop guessing and debug
  systematically. This one is quietly the most valuable: an agent editing the
  same file five times is almost always guessing at a fix rather than
  diagnosing it.
- **Turn-interval reminder.** Off by default. Set
  `turn_interval_reminder` and `turn_reminder_text` to surface a custom
  reminder every N turns (context checks, checkpoint prompts, whatever your
  workflow needs).

---

## The log

Every event lands in `~/.claude/spirit-level/log.jsonl`, one JSON object per
line:

```json
{"ts":"2026-07-14T19:02:11Z","session":"a1b2c3d4e5f6",
 "model":"claude-opus-4-8","event":"deny","rule":"G1",
 "detail":"git reset --hard HEAD~1","cwd":"/home/you/project"}
```

Event types: `route` (one per session per model), `deny`, `bypass`,
`advisory`, `edit-loop`.

This is deliberately a flat JSONL file with no schema migration story. It is
an append-only audit trail meant to be read with `jq`, grepped, or fed to
whatever you like:

```bash
# what got blocked, by rule
jq -r 'select(.event=="deny") | .rule' ~/.claude/spirit-level/log.jsonl | sort | uniq -c

# which models have driven this machine
jq -r 'select(.event=="route") | .model' ~/.claude/spirit-level/log.jsonl | sort | uniq -c

# every human override, with context
jq -r 'select(.event=="bypass") | "\(.ts) \(.detail)"' ~/.claude/spirit-level/log.jsonl
```

---

## Maintaining this protocol

A rule file that lives in a working context decays in one specific way: an
incident happens, a paragraph gets appended describing it, and every single
addition looks justified on its own. Repeat fifteen times and the file is too
long to follow in the middle of a response, which is the only moment it
matters. The companion skill in this project went through exactly that and had
to be compressed from 33KB to 15KB.

Four rules keep this file from needing the same operation.

**A new caught failure folds into the rule that already covers it.** Sharpen
the existing gate or add one line to it. A new numbered rule requires a
mechanism no existing rule addresses, which is rarer than it feels — a new
incident is not a new mechanism.

**The incident goes in the commit message, never in the file.** State the rule
and the reasoning that transfers to somebody who was not there. "On the 18th a
session did X" is provenance, and provenance lives in `git log`. A rule that
only makes sense with its origin story attached is not written generally
enough yet.

**Never tell the same story twice.** When two rules want the same evidence,
the evidence belongs to one of them and the other cross-references it. Two
copies drift, and the drift is silent.

**No byte budget.** Apply a per-line test instead: does the model need this
line *before* it knows the task? Trimming to hit a number cuts load-bearing
content, while deduplicating and generalizing never does. The constraint that
actually binds is the injected baseline in `protocol-inject.py`, which is paid
for on every turn of every non-native session — that one should grow by
sentences, not paragraphs.
