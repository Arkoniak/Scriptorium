# GLM-OCR (0.9B) baseline — does a tiny specialist compete?

Fourth Bag-of-Experts model, and a new angle: a **0.9B** OCR model (Zhipu GLM-OCR) that claims to top
OmniDocBench despite its size. Same 9 Mindblast pages. Does tiny compete with the 3–8B models, and
where does it land on the emphasis axis?

## Setup
- **Model:** GLM-OCR (`zai-org/GLM-OCR`), 0.9B, CogViT vision + GLM decoder. transformers in-process
  via `AutoModelForImageTextToText`. Prompt `Text Recognition:`.
- **Runtime friction (worth recording):** the `glm_ocr` architecture landed only in **transformers 5.x**,
  newer than this project's pinned **4.57.6** (kept for Surya/Unlimited/Qwen). Rather than upgrade the
  whole env and risk the other three, the run is **isolated** via
  `uv run --with "transformers==5.12.1" scripts/run_glm_ocr.py …` — the project lock stays at 4.57.6.
- **Fits 12GB** trivially (~2GB at bf16).
- **Run:** `uv run --with "transformers==5.12.1" scripts/run_glm_ocr.py --book mindblast --label baseline`.
  Run id `2026-06-26T15-46-58Z__glm-ocr__baseline` (gitignored under `books/output/`).

## Result
- **Fastest of the four: 3.91 s/page** (vs Surya 6.4, Unlimited 5.2, Qwen3-VL 8.5). The 0.9B size
  pays off in throughput — supporting the efficiency claim.
- **Accurate body text** with good hygiene: de-hyphenates words split across line breaks ("bemused",
  "microwave" — like Surya, unlike Unlimited) and keeps curly quotes.
- **Stylized cover logos — strong for 0.9B:** front cover "SpaceCops" + "MINDBLAST" both ~right (where
  the bigger Surya gave "MINEBLAST" and Unlimited "Sparkaps"); the back-cover logo came out "Space Lops"
  (wrong) — so it's *inconsistent* across the two covers, like every other model. Still, getting the
  front cover right at 0.9B lends real weight to the "small model competes / beats bigger" claim on a
  real scan, at least for accuracy.
- **Inline emphasis: dropped entirely** (0 spans across all 9 pages) — like Unlimited-OCR.

## The emphasis pattern is now clear (4 models)
| Preserves inline emphasis | Drops it |
|---|---|
| **Surya 2** (HTML `<i>`), **Qwen3-VL** (Markdown `*…*`) | **Unlimited-OCR**, **GLM-OCR** |

⇒ The **OCR-specialist VLMs** (Unlimited, GLM-OCR) drop inline emphasis; the **general VLM** (Qwen3-VL)
and the **HTML-emitting layout model** (Surya) preserve it. A generalizable hypothesis, not a one-off.

## Conclusion
A 0.9B model is the **fastest** here and **competitive on accuracy** — including the stylized front-cover
logo that two larger models missed. That makes GLM-OCR an attractive cheap ensemble member and validates
the "tiny competes" claim on this scan. Its limitation is shared with the other OCR-specialist
(no inline emphasis), and it carries a runtime cost (needs transformers 5.x, isolated here via
`uv run --with`). It adds a **4th independent lineage** (Zhipu) to the Bag of Experts, with errors that
keep complementing the others on the hard stylized regions.

Caveat: only the plain `Text Recognition:` prompt was tested; GLM-OCR also advertises Table/Formula
recognition and JSON information-extraction modes (and possibly grounding) — untested here.

Rationale: known.
