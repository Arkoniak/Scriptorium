# Unlimited-OCR baseline + head-to-head with Surya (Mindblast, 9 pages)

Second Bag-of-Experts model. Same 9 Mindblast pages as the Surya baseline, so the two are directly
comparable. Question: how does Baidu Unlimited-OCR compare to Surya 2 on a real pulp scan, and what
does their (dis)agreement tell us?

## Setup
- **Model:** Baidu Unlimited-OCR (`baidu/Unlimited-OCR`), a DeepSeek-OCR successor, run via
  **transformers + `trust_remote_code`** (`AutoModel`, bf16), **in-process** — no external server, no
  GGUF (contrast with Surya, which spawns a llama-server). `model.infer()` is the model's own harness
  (crop preprocessing, no-repeat-ngram logit processor, ref/det post-processing, figure extraction).
- **Mode:** per-page "gundam" (`base_size=1024, image_size=640, crop_mode=True`), default prompt
  `<image>document parsing.` → Markdown. Single-image per page (not the multi-page one-pass mode —
  that's a separate experiment) for parity with Surya's per-page output.
- **Deps added:** torchvision, einops, addict, easydict, psutil, matplotlib.
- **VRAM note:** gundam mode OOM'd on 12GB until `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
  (set in the script) reclaimed ~2GB of fragmented reserved memory. The SAM vision encoder's peak on
  high-res tiles is the tight spot — it fits, but barely.
- **Run:** `uv run scripts/run_unlimited.py --book mindblast --label baseline`.
  Run id `2026-06-25T19-26-26Z__unlimited__baseline` (gitignored under `books/output/`).

## Result (Unlimited-OCR)
- **Throughput:** 9 pages in 46.4s = **5.16s/page** amortized (1.25s sparse epigraph → 8.5s dense
  prose; scales with content). Slightly faster than Surya's 6.4s/page.
- **Body text essentially flawless**, agrees with Surya almost verbatim on prose/dialogue/copyright.
- **Figure extraction works:** the cover illustration was segmented and written as a real raster
  (`page_001/images/0.jpg`, 942K) with a Markdown `![](images/0.jpg)` ref. Surya labels Picture
  regions but doesn't extract the raster — Unlimited gives the file directly (a Stage 4 win).
- **Grounding boxes exist even in default mode:** every page got a `result_with_boxes.jpg` and the log
  showed det matches per page. The boxes are drawn/consumed by post-processing and stripped from the
  Markdown, so we currently discard them — capturable later (this corrects brainstorm.md, below).
- **Captured content Surya missed:** the back-cover barcode ISBN line (`ISBN 0-380-75852-0`).

## Head-to-head with Surya (the Bag-of-Experts point)
- **Complementary errors on stylized logos** — the headline finding. Each model nails the word the
  other misses:
  - Front cover title "MINDBLAST": **Unlimited correct**, Surya wrong ("MINEBLAST").
  - Series logo "Space Cops": **Surya correct**, Unlimited wrong ("Sparkaps" / "Stakeups").
  - ⇒ Disagreement localizes exactly to the hard display-font regions, and a ROVER-style vote across
    the two would recover *both* correct words. This is direct evidence the Bag-of-Experts /
    Consensus approach has real signal here, with no ground truth.
- **Surya cleaner on text hygiene:** consistent curly quotes; de-hyphenates words broken across line
  breaks ("bemused", "microwave"). Unlimited is more literal — inconsistent quotes (curly on some
  pages, straight on others) and keeps soft-hyphens ("be-mused", "micro-wave"). For a clean EPUB,
  Surya's output needs less normalization.
- **Occlusion:** the back cover has a physical "DOUBLEDAY" bookstore sticker over the blurb. Both read
  the sticker. Under it, Surya *inferred* the occluded word ("a dangerous drug"); Unlimited left it
  broken ("A dang ... drug") — Unlimited more literal/honest, Surya more readable but inferring.
- **Layout semantics:** Surya emits explicit labels (PageHeader / PageFooter / SectionHeader /
  Picture) in structured output; Unlimited emits Markdown + (discarded) boxes, with running heads
  transcribed inline rather than labeled.

## Correction to brainstorm.md
brainstorm.md claims Unlimited-OCR has **no grounding** ("per the README"). That is wrong — verified
from the model's remote code (`modeling_unlimitedocr.py`): it parses `<|ref|>label<|/ref|><|det|>[box]
<|/det|>` tokens and has a `<|grounding|>Given the layout of the image.` prompt (same family as
DeepSeek-OCR, which it explicitly extends). The Stage 2 engine tension "Unlimited-OCR SOTA but no
grounding vs DeepSeek-OCR has grounding" largely dissolves. brainstorm.md updated accordingly.

## Conclusion
Two strong baselines with complementary profiles: **Unlimited** is faster, extracts figure rasters,
captures more marginal content, and has grounding; **Surya** is cleaner on text hygiene and gives
richer semantic layout labels. Neither dominates. Most importantly, their errors are complementary on
exactly the hard regions — which validates the Bag-of-Experts / consensus direction (docs/brainstorm.md
Stage 1) before we have any ground truth. Next: a consensus/ROVER comparison tool over the two runs'
normalized output, and a book with tables/footnotes to close the still-open test-set gap.

Rationale: known.
