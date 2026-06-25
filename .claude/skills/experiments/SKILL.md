---
name: experiments
description: Research log conventions for Pdf2Epub — one file per empirical experiment, an index, and code backlinks. Use when recording experiment results, writing code that encodes a conclusion from a past experiment, or when it's unclear why some code/decision is the way it is.
user-invocable: true
---

# Experiment log

## Why this exists, and how it differs from `docs/brainstorm.md`

`docs/brainstorm.md` holds the *strategic* layer: the staged plan, open tensions, rejected
approaches. This skill governs the *empirical* layer: concrete experiment runs — what was tried,
on what input, with what result, and what was concluded. Don't mix the two: brainstorm.md would
become unreadable if every model run were appended to it, and a single growing log file doesn't
backlink cleanly from code (a link to "the log" isn't a link to one specific result).

## Where entries live

One file per experiment/question, under `docs/experiments/`:

```
docs/experiments/YYYY-MM-DD-short-slug.md
```

Use `docs/experiments/TEMPLATE.md` as the starting structure for a new entry.

Every new entry must be added to the index table in `docs/experiments/README.md` (date, question,
outcome, link). The index is the only place meant for skimming all experiments at once — don't grow
it into a second narrative layer, keep rows to one line each.

## What goes in an entry vs what doesn't

- **In the markdown entry**: the question being tested, setup (model, params, prompt, which test
  pages/book), the result in prose, and the conclusion — including a link back to the relevant
  section of `docs/brainstorm.md` (a Stage, a Key Tension, a Rejected Idea) that the result informs
  or resolves.
- **Not in the markdown entry**: raw model output, diffs, per-page metrics. Those are data, not
  narrative — keep them as files (e.g. under `books/output/` or a results directory next to the
  experiment) and reference them by path. If a result can't be reproduced from the path anymore,
  say so in the entry rather than leaving a silent gap.

## When to write an entry

Lazily, at the point a conclusion is actually reached — not retrospectively, and not for every
single run. A routine re-run that confirms an existing conclusion doesn't need a new file; a run
that changes or sharpens a conclusion does. If part of the "why" is genuinely unknown or lost,
mark it explicitly (`rationale: unknown`) rather than leaving it implicit — a silent gap reads as
"nothing important happened here," which is worse than an admitted unknown.

## Backlinking from code

When code encodes a conclusion that came from a specific experiment (a model choice, a metric
implementation, a threshold), add a one-line comment or docstring reference to that experiment
file — e.g. `# see docs/experiments/2026-06-25-bag-of-experts-baseline.md`. This is the cheap half
of the link: it lets anyone reading the code later find the "why" without already knowing to look
for it, and it travels with the code through refactors.

## When you're not sure why something is the way it is

Before guessing, check `docs/experiments/README.md` for a relevant entry, and check
`docs/brainstorm.md`'s Key Tensions / Rejected Ideas sections. Only fall back to `git log`/`git
blame` if neither has an answer.
