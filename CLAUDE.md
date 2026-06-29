# Scriptorium

## Language policy
- Converse with the user in whatever language they use.
- All documentation, code comments, commit messages, and docstrings must be written strictly in English, regardless of conversation language.

## Project
Scriptorium is a research / self-learning project: build a pipeline that converts a scanned PDF book
into a clean EPUB, focused on OCR/VLM recognition approaches. Goal: compare classic OCR and neural
(VLM) approaches, evaluate accuracy/cleanliness of results, and assemble a staged plan of increasing
complexity. The name reflects the actual focus — not just conversion, but verified, monk-scriptorium-grade
transcription of a scanned page into trustworthy text.

Full brief, accumulated ideas, model shortlist, and staged plan live in `docs/brainstorm.md`. Re-read it
before making architectural decisions — it records open questions and rejected ideas; don't repeat
rejected paths (e.g. a classic-OCR-first pipeline).

## Orientation — where to look to recover context (read before working)
These are the project's durable memory; a cold start should reconstruct everything from them:
- `docs/brainstorm.md` — the plan and **every design decision** (staged plan; consensus/ROVER; the
  image/graphic gate; cross-page stitching; scene-break; EPUB via Pandoc; metadata). Source of truth.
- `docs/model-comparison.md` — model capability matrix. 4 **working** models: Surya 2, Unlimited-OCR,
  Qwen3-VL-8B, GLM-OCR (0.9B). Gemma 4 E4B **excluded**; PaddleOCR-VL **deferred**; plus a shortlist.
- `docs/experiments/` — per-experiment findings (`README.md` is the index). What we learned and why.
- **GitHub issues** (`gh issue list`) — the next-steps roadmap (currently #16–#24). Check before
  asking "what's next".
- `scripts/*.py` docstrings — how each model/tool is run (incl. transformers-version isolation via
  `uv run --with`, and the `llama-server` requirement for Surya/Qwen).

Topic → where to look:
- Consensus / ROVER / voting / alignment → `docs/experiments/2026-06-27-consensus-rover.md` + `scripts/consensus.py`.
- Running a model / a runtime quirk → that model's `scripts/run_*.py` docstring + `docs/model-comparison.md`.
- **Which models have a capability** (emphasis, bboxes, labels, grounding, speed, etc.) → **always check `docs/model-comparison.md` first** — never answer from memory or training data.
- Why a model is excluded/deferred (Gemma, PaddleOCR-VL) → its experiment entry.
- Local environment (llama.cpp build, transformers 5.x isolation, Python 3.14) → memory + script docstrings.

Model-specific notes:
- **Unlimited-OCR**: always run in grounding mode (`run_unlimited.py` defaults to grounding). Grounding gives structured blocks (text + label + bbox) comparable to Surya's output. The old `--grounding` flag is gone; use `--no-grounding` only to fall back to Markdown mode.

## Git discipline — MANDATORY
- **NEVER commit, merge, or push without explicit user permission.**
- Permission is only granted AFTER the user has reviewed the changes and said so explicitly.
- After making code changes: run tests AND run the actual script on real book data, show the results, then WAIT.
- "Tests pass" is not sufficient — the user must see the script work on real data and explicitly approve before any git operation.

## Skills
- When creating a commit — invoke the `commits` skill.
- After a meaningful experimental run (evaluating a model, comparing approaches) that reaches or
  changes a conclusion — invoke the `experiments` skill to record it.
- When writing code that encodes a conclusion from a past experiment (a model choice, a metric, a
  threshold) — invoke the `experiments` skill to add a backlink instead of re-deriving the reasoning.
- When it's unclear why some code or decision is the way it is — invoke the `experiments` skill
  before guessing.
- When evaluating, comparing, or adding an OCR/VLM model — read and update `docs/model-comparison.md`
  (the capability matrix: VRAM fit, inline emphasis, bounding boxes, layout labels, figure
  extraction, text hygiene, speed, runtime). Keep it current so the tracking survives a context reset.
- Before starting any non-trivial change, or when asked to create a branch — invoke the
  `git-workflow` skill.
- When creating/reviewing a GitHub issue or PR, or checking CI/PR status — invoke the `github` skill.

## Layout
- `books/input/` — source scanned PDFs (do not commit — large binaries)
- `books/output/` — generated EPUBs/intermediate artifacts (do not commit)
- `docs/brainstorm.md` — single source of truth for research ideas/plan
- `docs/model-comparison.md` — capability matrix across evaluated OCR/VLM models
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
