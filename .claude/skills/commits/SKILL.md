---
name: commits
description: Commit message conventions for this project. Use when creating or reviewing git commits.
user-invocable: false
---

## Commit message format

```
<type>(<scope>): <subject>

<body>
```

- `<scope>` is optional
- This project has no issue tracker — do not add an `(#<issue>)` reference

## Types

| Type | When to use |
|---|---|
| `feat` | New feature for the user (not a CI/CD script feature) |
| `fix` | Bug fix for the user or a CI/CD script |
| `docs` | Changes to documentation only |
| `style` | Formatting, missing semicolons, whitespace — no logic change |
| `refactor` | Refactoring production code (e.g. renaming a variable) |
| `test` | Adding or refactoring tests |
| `chore` | CI/CD scripts, build tasks, dependency updates |

## Subject line rules

- Imperative mood, present tense: "add feature", not "added feature" or "adds feature"
- Max 72 characters
- No period at the end

## Body (optional)

Separate from the subject with a blank line. Use bullet points to explain **what** changed and **why** — not a prose summary of the diff. No strict line length limit.

Example:
```
feat(experiments): add Consensus Entropy scoring across model outputs

- Compute per-token agreement across all Bag of Experts model runs
- Flag pages below an agreement threshold for manual review
- Training-free signal — needed before a ground-truth eval set exists
```

## Breaking changes

If a commit introduces a breaking change, add a `BREAKING CHANGE:` line in the body:

```
refactor(pipeline): rename page classification entrypoint

- Rename classify_page to classify_page_keep_discard to match the
  keep/discard convention used elsewhere in the cleanup layer

BREAKING CHANGE: classify_page removed; callers must use classify_page_keep_discard
```

## Examples

```
feat(experiments): add ROVER-style word voting across model outputs
fix(pipeline): handle empty bbox list in grounding verification
docs: add Stage 1 model shortlist to brainstorm.md
chore: bump uv lockfile after adding pandoc dependency
```
