# Pdf2Epub

## Language policy
- Converse with the user in whatever language they use.
- All documentation, code comments, commit messages, and docstrings must be written strictly in English, regardless of conversation language.

## Project
Research / self-learning project: build a pipeline that converts a scanned PDF book into a clean EPUB,
focused on OCR/VLM recognition approaches. Goal: compare classic OCR and neural (VLM) approaches,
evaluate accuracy/cleanliness of results, and assemble a staged plan of increasing complexity.

Full brief, accumulated ideas, model shortlist, and staged plan live in `docs/brainstorm.md`. Re-read it
before making architectural decisions — it records open questions and rejected ideas; don't repeat
rejected paths (e.g. a classic-OCR-first pipeline).

## Skills
- When creating a commit — invoke the `commits` skill.
- After a meaningful experimental run (evaluating a model, comparing approaches) that reaches or
  changes a conclusion — invoke the `experiments` skill to record it.
- When writing code that encodes a conclusion from a past experiment (a model choice, a metric, a
  threshold) — invoke the `experiments` skill to add a backlink instead of re-deriving the reasoning.
- When it's unclear why some code or decision is the way it is — invoke the `experiments` skill
  before guessing.

## Layout
- `books/input/` — source scanned PDFs (do not commit — large binaries)
- `books/output/` — generated EPUBs/intermediate artifacts (do not commit)
- `docs/brainstorm.md` — single source of truth for research ideas/plan
- `docs/experiments/` — research log: one file per experiment, see `.claude/skills/experiments/SKILL.md`

## Machine context (Manjaro Linux)
- Package manager: `yay` — never suggest `pacman`/`apt`
- Editor: `nvim`; prefer TUI/CLI over GUI
- CLI: `rg` instead of `grep`, `bat` instead of `cat`, `eza` instead of `ls`, `fd` instead of `find`, `delta` as git pager, `lazygit` (`lg`) as git TUI
- Docker: `docker compose`, do not suggest podman/nerdctl
- Do not suggest creating aliases — the user types commands by hand
- Destructive actions require explicit confirmation

## Python stack (this project diverges from the general machine preference)
- Python version management: `pyenv` (never the system Python)
- Environment/package management: **`uv`** (primary tool for this project, not poetry)
- Linter/formatter: `ruff`
- Line length: 120 characters
- pre-commit framework — standard

## VRAM constraint
Target machine has 12GB VRAM (RTX 4070 Super). The Stage 1 model shortlist is chosen for this
constraint without CPU offload (see `docs/brainstorm.md`).
