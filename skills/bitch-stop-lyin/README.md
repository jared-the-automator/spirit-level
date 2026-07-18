# bitch-stop-lyin

A skill that stops an agent from stating things it has not checked.

This is the oldest and most heavily tuned piece of this repo. It was built by
patching a real failure every time one occurred — over 15 rounds — and then
compressed once the patching itself became the problem.

## What it does

It defines two protocols that fire on **what you are about to output**, not on
what the user typed. That distinction is the entire design. A gate keyed to
input keywords misses the claim a model volunteers in a closing paragraph; a
gate keyed to output content does not.

- **Protocol A — Scope & Estimates.** Six steps producing a risk-stratified
  estimate with an explicit assumption ledger. No point estimates while any
  assumption is unverified.
- **Protocol B — Technical Claims.** Any claim about any named external
  system requires verification against current documentation first. No
  exempt document types, no "I know this one" list, no home-turf exemption
  (the assistant's own product surface is explicitly in scope).

## The six rationalization families

The interesting part is not the rules, it is the **taxonomy of excuses**. In
practice a model does not skip verification by deciding to lie; it skips by
telling itself something reasonable. Every one of those reasonable-sounding
thoughts collapses into one of six families:

1. **No exempt frame** — "this is conversational / a proposal / just a
   summary / I volunteered it." Position, register, and document type are
   irrelevant. The trigger is the claim in the output.
2. **A hedge is a confession** — "usually," "(or similar)," "click X or Y."
   The moment you soften a claim you have admitted you are guessing, which is
   the moment to verify rather than publish.
3. **Inference is not observation** — "the call failed, so the service is
   down." A mechanism deduced from symptoms is a hypothesis. Trace it or
   label it.
4. **Familiarity is the alarm, not the clearance** — the platforms you know
   best are where your training data is stalest, and you will not think to
   check.
5. **Borrowed verification isn't yours** — a subagent's citations, or two
   verified numbers combined into a third claim, are not verified.
6. **No number without a source** — a statistic that supports your argument
   is evidence you constructed it.

Naming the families is what makes this enforceable on smaller models. A list
of 34 individual war stories is not retrievable mid-response; six named
patterns are.

## Why it was compressed

The file grew to 33KB (~8,000 tokens on every load) because each new caught
failure was appended as a fresh red flag containing the full narrative of the
incident that produced it. Five of them restated entire sections verbatim.

Compressing to ~15KB cut the per-load cost by more than half **with zero
rules lost** — verified by probing the new text for every distinct concept in
the old one. The incident narratives now live in git history, where they
belong. The `Maintaining This Skill` section at the bottom of `SKILL.md`
exists to keep future editors from re-inflating it.

That maintenance rule is the transferable lesson: **a behavioral skill that
grows by appending one story per incident will always decay into something
too long to follow.** Fold new failures into existing families; put the story
in the commit message.

## Install

Copy the directory into your skills folder:

```bash
cp -r skills/bitch-stop-lyin ~/.claude/skills/
```

Rename it to whatever you like — the directory name is the invocation name.
It works standalone and has no dependency on the rest of this repo.
