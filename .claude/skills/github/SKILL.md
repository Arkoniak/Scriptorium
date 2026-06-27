---
name: github
description: GitHub operations for Scriptorium via the gh CLI — creating issues, opening/reviewing PRs, checking CI status. Use for any GitHub-specific operation (not local git — see the git-workflow skill for branches/commits).
user-invocable: true
---

# GitHub operations

## Project

- Repo: `Arkoniak/Scriptorium` (remote `origin`, SSH protocol)
- **GitHub issues hold the next-steps roadmap** (filed 2026-06-27, #16–#24). Run `gh issue list` to see
  what's planned/open before deciding what to do next. Still: don't *create* new issues unless the user
  asks; PRs don't need a linked issue (commits follow the `commits` skill, which has no `(#issue)` ref).
- Auth: `gh auth status` to verify; already logged in as `Arkoniak` over SSH.

## Creating an issue

Only when the user explicitly asks for one (e.g. to track a longer-running piece of work GitHub-side,
or to file something for later). Use `gh issue create`:

```bash
gh issue create --title "<title>" --body "<body>"
```

Keep the title imperative and short; put context/acceptance criteria in the body. Don't invent labels
or assignees unless asked.

## Opening a pull request

Branches are created per the `git-workflow` skill before this step. Once a branch is pushed:

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points>

## Test plan
<checklist, or "n/a" if not applicable>
EOF
)"
```

- Keep the PR title under ~70 characters
- Base branch is always `main`
- Merge strategy for this repo is **merge commit** (not squash, not rebase) — when merging via
  `gh pr merge`, use `gh pr merge --merge`, and don't override this without asking

## Checking CI / PR status

```bash
gh pr checks <number>          # CI status for a PR
gh run list --branch <branch>  # recent workflow runs on a branch
gh run view <run-id> --log     # logs for a specific run
```

## Reviewing comments on a PR

```bash
gh api repos/Arkoniak/Scriptorium/pulls/<number>/comments
```

## Don't

- Don't push to `main` directly via `gh`/`git push` without the user's go-ahead — see `git-workflow`.
- Don't merge a PR without explicit confirmation, even if CI is green.
- Don't change the merge strategy (merge commit) or repo settings without asking first.
