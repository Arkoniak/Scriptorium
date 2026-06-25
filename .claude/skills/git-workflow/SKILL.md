---
name: git-workflow
description: Branching conventions for Scriptorium's single repo — when to create a branch, naming, and the branch-to-merge lifecycle. Use before starting any non-trivial change, or when asked to create a branch/PR. See the github skill for the gh-specific parts (issue/PR creation, CI checks).
user-invocable: false
---

# Git workflow (single repo, solo project)

## Branch or not?

This project uses a branch + PR for every substantive piece of work, even solo — it keeps `main`
clean and gives the `code-review`/ultrareview flow something to point at later. Exceptions where
committing straight to `main` is fine:
- A typo fix or one-line doc correction
- Something the user explicitly says to commit directly

Otherwise: branch first.

## Naming

`<type>/<slug>`, reusing the same `<type>` vocabulary as the `commits` skill (`feat`, `fix`, `docs`,
`style`, `refactor`, `test`, `chore`). Slug is short, kebab-case, descriptive of the change — not the
date, not a ticket number (there is no tracker, see the `github` skill).

```
feat/bag-of-experts-baseline
fix/grounding-empty-bbox
docs/stage1-model-shortlist
```

## Lifecycle

1. Branch from current `main`: `git checkout -b <type>/<slug> main` (pull first if `main` might be
   behind `origin`).
2. Commit per the `commits` skill conventions.
3. Push: `git push -u origin <type>/<slug>`.
4. Open a PR — see the `github` skill.
5. After the PR is merged (merge commit, not squash/rebase — see `github` skill), delete the local
   and remote branch:
   ```bash
   git checkout main && git pull
   git branch -d <type>/<slug>
   git push origin --delete <type>/<slug>
   ```

## Don't

- Don't force-push a shared branch without asking, even though it's a solo project — treat pushed
  branches as shared state once a PR is open.
- Don't merge your own PR without the user's explicit go-ahead, even if CI is green and it's a
  one-person repo — the PR step exists for review, not ceremony.
- Don't rebase or squash commits on a branch after opening a PR unless asked.
