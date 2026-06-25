---
name: commits
description: Commit message conventions for this project. Use when creating or reviewing git commits.
user-invocable: false
---

## Commit message format

```
<type>(<scope>): <subject> (#<issue>)

<body>
```

- `<scope>` is optional
- `(#<issue>)` is the GitLab issue number — **required** unless the commit clearly falls outside the scope of any open issue (e.g. a CI/CD fix committed while working on an unrelated feature issue)

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
feat(enricher): add exponential backoff for Enfusion API retries (#8)

- Add retry logic with up to 10 attempts on 5xx responses
- Preserve original ticker on enrichment failure for partial pipeline runs
- Needed to handle intermittent Enfusion API instability in production
```

## Breaking changes

If a commit introduces a breaking change, add a `BREAKING CHANGE:` line in the body:

```
refactor(loader): rename raw table finalization function (#11)

- Rename dbRawFinalization to dbReplaceFinalization to reflect drop+rename strategy

BREAKING CHANGE: dbRawFinalization removed; callers must use dbReplaceFinalization
```

## Examples

```
feat(extractor): add CSV-based ticker extraction (#5)
fix(loader): handle duplicate tickers in filtered upsert (#3)
docs: add environment variable table to README (#2)
chore: configure Cloud Run job deployment script
```
