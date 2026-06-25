# Surya 2 — Stage 1 baseline on Mindblast (9 pages)

First Bag-of-Experts run: does Surya 2 produce clean text on a real scanned pulp paperback,
on 12GB VRAM without docker, and how fast?

## Setup
- **Model:** Surya 2 (`surya-ocr==0.20.0`), full-page OCR mode (one VLM call per page, returns
  layout + content together).
- **Backend:** `llamacpp` — native `llama-server` (CUDA build, on PATH via a `~/.local/bin` symlink),
  no docker. GGUF weights auto-downloaded from `datalab-to/surya-ocr-2-gguf` (`surya-2.gguf` +
  `surya-2-mmproj.gguf`). The default `vllm` backend was rejected: it spawns a docker container
  needing the nvidia container runtime, which isn't configured here.
- **Hardware:** RTX 4070 Super, 12GB. Fits without CPU offload.
- **Install note:** Python 3.14 needed `pillow>=12` (cp314 wheels); surya pins `pillow<11`, lifted via
  `[tool.uv] override-dependencies = ["pillow>=10.2.0"]`. surya is pure Python, so no rebuild.
- **Input:** 9 pages from *Spacecops: Mindblast* (Diane Duane & Peter Morwood, Avon 1991), rendered at
  300 DPI by `scripts/extract_pages.py`. Pages chosen for variety: 1 (front cover, illustrated),
  5 (title), 6 (copyright, dense small print), 8 (epigraph, sparse), 12 (action + dialogue/slang),
  20 & 140 (prose), 256 (prose), 260 (back-cover blurb, stylized).
- **Run:** `uv run scripts/run_surya.py --book mindblast --label baseline`.
  Run id `2026-06-25T16-59-36Z__surya__baseline` (artifacts gitignored under `books/output/`,
  reproducible by re-running the command above).

## Result
- **Throughput:** 9 pages in 57.5s = **6.4s/page** amortized (includes one-time server spawn + model
  load, paid once per run). The first-ever run also paid a ~6 min one-time GGUF download — that is not
  inference cost. ⇒ a 260-page book is ~28 min. No optimization needed.
- **Body text — essentially flawless** (confidence 0.98–1.00): prose, dialogue, the slang shout
  "Get'm, get'm, y'furgs!", curly quotes, the copyright page's printer's key line
  "RA 10 9 8 7 6 5 4 3 2 1", ISBN/LCCN, the epigraph — all correct.
- **Only real recognition errors are stylized display logos** (confidence lower, 0.87–0.97):
  front-cover "MINDBLAST" → "MINEBLAST", back-cover "Space Cops" → "SpaceLogs".
- **No hallucinations.** The back cover carries a physical used-bookstore "DOUBLEDAY" sticker; Surya
  transcribed it *correctly*. That is correct OCR of unwanted content (a Stage 3 cleanup concern),
  not an accuracy failure — the model read only ink actually on the page.
- **Layout labels (bonus, high quality)** — directly useful downstream:
  - Front cover: the illustration is segmented as 2 `Picture` blocks ⇒ Stage 4 can extract it as a
    raster instead of OCR-ing it.
  - Running heads / page numbers are tagged `PageHeader` / `PageFooter` ⇒ Stage 3 can discard by
    label instead of guessing.
  - Titles / chapter heads tagged `SectionHeader`.
  - Confidence correlates with page difficulty (low on stylized/sparse pages, 1.0 on prose) ⇒ a usable
    verification signal.

## Test-set gap (explicit, not silent)
This book has **no tables and no footnotes**, so Surya's behavior on those is untested here — must be
covered on another book before any Stage 1 conclusion about them. Also: an earlier thumbnail guess that
page 256 was a "series ad list" was wrong — at 300 DPI it is prose.

## Conclusion
Surya 2 is a strong Stage 1 baseline: clean body-text transcription at 6.4s/page on 12GB with no
docker, plus high-quality layout labels that partially pre-solve Stage 3 (cleanup) and Stage 4 (figure
extraction). Its error mode is narrow and predictable — stylized display fonts on cover pages —
matching the brainstorm's expectation that illustrated/stylized pages yield more errors. This informs
`docs/brainstorm.md` Stage 1 (Bag of Experts) and the engine-choice tension in Stage 2: Surya is a
serious contender, not just a comparison baseline.

Open next steps: a second model (Unlimited-OCR) to enable ROVER / Consensus Entropy cross-checks
(no ground truth yet), and a book with tables/footnotes to close the test-set gap above.

Rationale: known.
