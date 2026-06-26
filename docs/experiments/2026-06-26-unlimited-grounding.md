# Unlimited-OCR grounding mode — structured boxes, and the inline-emphasis gap

Follow-up to the Unlimited-OCR baseline. Two questions: (1) can we capture Unlimited's bounding
boxes as structured data (not just the drawn jpeg)? (2) does Unlimited preserve inline text markup
(italic/bold) the way Surya's HTML does?

## Setup
- Added a `--grounding` mode to `scripts/run_unlimited.py`. It uses the `<|grounding|>Given the
  layout of the image.` prompt with `infer(eval_mode=True)`, which returns the **raw tagged output**
  (no post-processing / box drawing). We parse `<|det|>label [box]<|/det|>text` (and the
  `<|ref|>label<|/ref|><|det|>...` form) into structured blocks: `{text, label, bbox(px), bbox_norm}`.
  Coordinates are 0-1000 normalized; we scale to pixels by the page size. Raw output is kept per page
  as `raw.txt` for audit.
- Run: `uv run scripts/run_unlimited.py --book mindblast --grounding --label grounding`.
  Run id `2026-06-26T11-52-38Z__unlimited__grounding` (gitignored under `books/output/`).
- Prompt probe (separate, scratch): same page through `document parsing.`, an explicit
  "convert to markdown" prompt, `Free OCR.`, and a "convert to HTML" prompt.

## Result — grounding capture works
- Per-page structured blocks with semantic labels and pixel bboxes, e.g. page 12:
  `title [723,127,1191,194] "SPACE COPS"`, then `text` blocks per paragraph. 5.41s/page (≈ default).
- **Figure regions are captured as `image`-labeled blocks** with a bbox (e.g. cover page 1:
  `image [0,1486,2032,3360]`, empty text) — usable for Stage 4 figure handling alongside the raster
  files the default mode extracts.
- This gives Unlimited bbox + labels comparable to Surya's layout output, enabling cross-model bbox
  comparison (a brainstorm Bag-of-Experts idea).
- **Anomaly:** on some pages the model emits a spurious refusal preamble before the real output
  ("The text is not clearly legible … Rule 4 … [No text detected]"), then parses correctly anyway.
  Parsing from the first tag drops it by construction; `raw.txt` preserves it for audit.

## Result — Unlimited loses inline emphasis (the important finding)
The source italicizes interior monologue, e.g. p12 "from him. *A little too close*, he thought"
(verified against the source crop — genuinely italic, not a Surya hallucination).
- **Surya** keeps it: `<i>A little too close</i>` in its block HTML.
- **Unlimited drops it in every mode and under every prompt tested** — grounding, default
  `document parsing.` (markdown), explicit "convert to markdown", `Free OCR.`, and "convert to HTML":
  **0 emphasis markers** in all of them, "A little too close" always plain.
- ⇒ This is a **model-level limitation, invariant to the prompt** — Unlimited-OCR was not trained to
  emit inline emphasis. No prompt recovers it; it isn't in the output to post-process.

## Conclusion
The `--grounding` mode delivers what was asked: Unlimited's layout as structured boxes
(text + label + bbox), not just a drawn jpeg — and figure regions as labeled boxes. But the prompt
probe settles a sharper question against Unlimited for the clean-EPUB goal: it **cannot preserve
inline emphasis**, which carries meaning in fiction (interior thought, stress, titles, foreign
words). Surya keeps it via HTML.

Updated Bag-of-Experts picture (docs/brainstorm.md Stage 1/2):
- **Surya:** bbox + semantic labels + **inline emphasis (HTML)** + cleaner text hygiene.
- **Unlimited:** bbox + labels + text, faster, extracts figure rasters, flat-KV long-document — but
  **no inline emphasis**.

For text fidelity toward EPUB, Surya now leads. Unlimited's edge stays in speed, figure raster
extraction, and one-pass long-document parsing. Next: a consensus/ROVER comparison over the two runs'
normalized output (complementary errors on stylized logos remain the strongest ensemble signal), and
a book with tables/footnotes — where structure markup differences may matter more than on plain prose.

Rationale: known.
