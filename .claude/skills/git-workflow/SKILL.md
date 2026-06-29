---
name: git-workflow
description: Branching conventions for Scriptorium's single repo — when to create a branch, naming, and the branch-to-merge lifecycle. Use before starting any non-trivial change, or when asked to create a branch/PR. See the github skill for the gh-specific parts (issue/PR creation, CI checks).
user-invocable: false
---

# Git workflow (single repo, solo project)

## Branch or not?

This project uses a branch + PR for every substantive piece of work, even solo — it keeps `master`
clean and gives the `code-review`/ultrareview flow something to point at later. Exceptions where
committing straight to `master` is fine:
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

## Research tasks — discuss first

If the task has any research or design component (algorithm choice, threshold, data-structure
trade-off), **do not open a branch yet**. First:
1. Read the issue and all relevant context.
2. Discuss design options and trade-offs with the user.
3. Post the agreed design as a comment on the GitHub issue.
4. Only then branch and implement.

See CLAUDE.md §"Research tasks" for the full rule.

## Lifecycle

1. Branch from current `master`: `git checkout -b <type>/<slug> master` (pull first if `master` might be
   behind `origin`).
2. Commit per the `commits` skill conventions.
3. Push: `git push -u origin <type>/<slug>`.
4. Open a PR — see the `github` skill.
5. After the PR is merged (merge commit, not squash/rebase — see `github` skill), delete the local
   and remote branch:
   ```bash
   git checkout master && git pull
   git branch -d <type>/<slug>
   git push origin --delete <type>/<slug>
   ```

## Don't

- Don't force-push a shared branch without asking, even though it's a solo project — treat pushed
  branches as shared state once a PR is open.
- Don't merge your own PR without the user's explicit go-ahead, even if CI is green and it's a
  one-person repo — the PR step exists for review, not ceremony.
- Don't rebase or squash commits on a branch after opening a PR unless asked.
