# Scriptorium — scanned PDF → clean EPUB (OCR + neural refinement)

## Status
Active

## Summary
Research / self-learning project: build a go/python pipeline that converts a scanned PDF book into an EPUB as cleanly as possible. The goal is to sweep combinations of classic OCR and neural (VLM) approaches, evaluate accuracy/cleanliness of the result, and ultimately assemble a staged plan of increasing complexity/accuracy.

## Context
Standalone resource project, not tied to an existing project/area in tasks.db.

## Accepted Ideas

### Layer 1 — scan preprocessing
- Geometry: deskew, page dewarping (curvature near the spine), crop/auto-detect page bounds, splitting a two-page spread into single pages.
- Image quality: denoising, binarization (Otsu/adaptive), contrast/brightness normalization, bleed-through removal (text showing through from the reverse side), sharpening/upscaling.
- Structural cleanup: removing stains/staples/hole-punch holes, despeckle.
- **Tension:** the need for preprocessing depends on the engine (Layer 2). Classic OCR (Tesseract) is sensitive to noise/skew — preprocessing is almost mandatory. Modern VLMs (trained on "dirty" document photos) may not need aggressive preprocessing, or may even lose quality from over-binarization. Layers 1 and 2 must be tested in pairs, not separately.

### Layer 2/3 — choosing the recognition engine
Three parallel paradigms in the industry:
1. **Classic OCR pipeline** (Tesseract/PaddleOCR + layout-reconstruction rules) — cheap, predictable, fragile on complex layouts / dirty scans.
2. **End-to-end VLM OCR** — the model reads the whole page and emits text/markdown/structure with no separate OCR engine. Candidates: DeepSeek-OCR, **Baidu Unlimited-OCR** (released 2026-06, MIT, 3B MoE / 500M active, R-SWA attention → constant KV-cache, parses a multi-page PDF in one pass, SOTA on OmniDocBench v1.6 — 93.92%), dots.ocr, NVIDIA Nemotron Parse, Marker, MinerU, Docling, Nougat.
3. **Hybrid** — classic OCR as a hint + VLM/LLM as refinement on top.

- **Tension (Q3 from discussion):** the current trend (DeepSeek-OCR → Unlimited-OCR) suggests VLMs can fully replace classic OCR rather than supplement it. Worth taking VLM-only as a baseline and comparing against the hybrid branch.
- **Tension (Q1, hybrid):** feeding "image + ready OCR text" into the model risks anchoring bias — the model may lock in the OCR error instead of fixing it from the image. Need an experiment with two prompts: "here's the OCR, correct it if you see an error" vs "here's the image, read it from scratch".
- Idea (Q2): extract "anchor" entities (names, place names) from the text as more-trusted hints to the model. Echoes the paper *"From Plausibility to Verifiability: Risk-Controlled Generative OCR for VLMs"* (arXiv 2603.19790) — worth studying at the structure stage.

### Layer 3 — verification / fighting hallucinations
- Baseline idea: compare text volume of OCR vs VLM (% deviation as a signal) — simple but crude.
- **Grounding/bbox check**: models with a grounding mode (DeepSeek-OCR — yes, via `<|grounding|>` + `<|ref|>`/`<|det|>` tags, coordinates 0–1000 normalized; **Unlimited-OCR — also yes** [corrected 2026-06-25 from the code in `modeling_unlimitedocr.py`: previously, based on the README, grounding was assumed absent; in fact it has the same `<|grounding|>` + `<|ref|>`/`<|det|>` format, since it is a DeepSeek-OCR successor — see `docs/experiments/2026-06-25-unlimited-baseline.md`]) emit bboxes together with text. What to do with bboxes:
  1. Geometry sanity-check (bbox in a plausible text region, not empty/anomalous) — a cheap first filter.
  2. Crop + verify: cut the region by bbox and either run it through classic OCR for cross-check, or show the same crop to the model again with a yes/no question ("does this say exactly '...'?", read the probability of the yes token) — more reliable than a second OCR pass on small crops.
  3. Use bbox not only for verification but for layout reconstruction (reading order, attaching caption to illustration) — Layer 4 gets this "for free".
- **Engine fork:** ~~Unlimited-OCR (SOTA, fast, but no grounding) vs DeepSeek-OCR (has grounding/verifiability, but KV-cache grows linearly on long documents)~~ [corrected 2026-06-25: Unlimited-OCR DOES have grounding (see above), so this fork largely dissolves — Unlimited gives both SOTA/speed/constant KV-cache and grounding/verifiability at once]. Verification when choosing Unlimited-OCR can be covered by its own grounding, or by a consensus check in an ensemble (see the 2026-06-25 experiment — Surya and Unlimited errors are complementary on stylized fonts).
- From the literature: general LVLM hallucination-detection approaches — bbox/grounding checks, evidential conflict detection (a numeric uncertainty metric for the model).

### Layer 4 — structure and EPUB assembly
- Modern VLM parsers already emit tagged elements (headings, paragraphs, lists, tables as HTML, formulas as LaTeX, captions, footnotes, running heads, table of contents) in correct reading order, including multi-column layout — content markup is largely solved at the model level.
- Pipeline: VLM → Markdown/HTML → **Pandoc** → EPUB3 (headings → chapters, tables → HTML tables, formulas → MathML / rasterization as fallback).
- Using bbox: removing running heads/page numbers by their position on the page; restoring reading order of multi-column layout; attaching caption to illustration by bbox proximity (`<figure><figcaption>`); extracting raster fragments of illustrations as EPUB resources (rather than trying to recognize a picture as text).
- Restoring book structure: automatic EPUB TOC from H1/H2 headings; linking footnote markers to footnote text (with jump-there-and-back in the EPUB).
- **Scene-break (in-chapter section divider) — classify by recurrence, not by OCR-ing the glyph.** Empirically (the 2026-06-25/26 runs, see `docs/experiments/`): both models see the divider ornament as a picture (Surya — a `Picture` block with empty text; Unlimited — extracts a raster `![](images/N.jpg)`), none emits a semantic break, and recognizing the glyph as text yields garbage. Detect at the **book level**: the same small centered crop recurs dozens of times → perceptual hash (dHash/aHash) + clustering; a large cluster of near-identical tiny crops = the divider (a real illustration is unique / large / often has a caption). The glyph raster itself is not needed → once classified → `<hr>`. Cover the textual variant too (`* * *` / `***` as a line). Edge case: chapter-heading ornaments also recur, but at a stable position (top of the chapter's first page) — separable by position within the cluster.
- **Tension:** per-page parsing (more reliable, but breaks paragraphs/footnotes at page boundaries) vs the whole book in one pass (as Unlimited-OCR can — the model stitches text across page breaks itself, but requires trusting reading order over hundreds of pages at once).
- **Resolving the tension — stitching as a deterministic post-process (Path B), not trusting the model.** Order is critical: (1) **remove running heads/page numbers first** — they wedge BETWEEN the halves of a split fragment (a real example from pages 16→17: `…being weight-` → `SPACE COPS 9` → `less…`, the word "weightless" split across the boundary with the running head INSIDE); the signal already exists — Surya labels `PageHeader`/`PageFooter`. (2) Classify the boundary as a binary decision: **word split** (hyphen at end of the last line + lowercase next + dictionary check; careful with genuine compounds like `still-packed`/`up-and-up`) → join without the hyphen; **paragraph split** (no terminal punctuation `.!?"` + lowercase next) → join with a space; otherwise a new paragraph/section. Distinguish `—` (em-dash, NOT a line break) from `-` (hyphen at line end — a candidate). Unlimited's multi-page mode (single pass) as a **cross-check signal**: disagreement between its stitching and the deterministic one → flag for manual review. The brainstorm principle holds: this is **join/no-join classification at the boundary**, not "ask an LLM to merge the pages" (risk of silent rewriting). All required signals are already in the normalized run output — the stitcher is a layer on top, requiring no new model capabilities.

### Garbage cleanup — two-level classification (not generation!)
Key principle: cleanup is better done as **classification** (KEEP/DISCARD) rather than free LLM generation ("rewrite and remove the extra") — generation carries the same risk of hallucination / silent content distortion as the main OCR. Classification is easily audited by a simple input/output diff.

1. **Page-level (whole service pages):** show the model a page and ask "is this a content page of the book, or a service page (ToC, title page, copyright, publisher ad, blank, index)?". Binary classification, low error risk — such pages differ strongly visually/structurally. Confidence can be raised: self-consistency (run the decision twice / ask for an explanation), a cheap heuristic backstop (short lines + leader dots + numbers → ToC signal), heuristic-vs-LLM mismatch → page goes to manual review.
2. **Element/line-level (garbage inside a needed page):** running heads, page numbers, footnotes in the bottom margin — need finer granularity than a whole page. Same principle: KEEP/DISCARD classification of the line/block, not rewriting.
- Separately: reconciling the printed table of contents (ToC) with the book's real structure (if needed for navigation at all, not for removal) — this is an **alignment/matching** task (fuzzy string matching / embeddings between ToC headings and actually-found headings), not a generative task — it needs no LLM at all in the simple case; an LLM is only needed if the ToC headings are heavily abbreviated/paraphrased.

### Local models — general frontier VLMs with native OCR (not only specialized ones)
- **Qwen3-VL** — dense 2B/4B/8B/32B, MoE 30B-A3B and 235B-A22B. Document parsing with layout positions, Qwen HTML output format, robustness to low quality/blur/skew, long context (256K, extensible to 1M — closes the "whole book in one pass" tension). Under 12GB VRAM (RTX 4070 Super): 8B dense quantized fits comfortably; 30B-A3B MoE — theoretically feasible via offloading MoE layers to CPU (Unsloth).
- **Gemma 4** — E2B/E4B (effective), 26B MoE, 31B Dense. Natively claims Document/PDF parsing, OCR (multilingual), handwriting recognition; has a dedicated token-budget setting for OCR/small text (70–1120). E4B should run comfortably on 12GB.
- **Important takeaway:** OCR/document parsing for both is a stated out-of-the-box capability, requiring no fine-tuning. RolmOCR is an example that "specialization" often means a fine-tune of the same general model (Qwen2.5-VL-7B), not a separate architecture.
- **Advantage of a general-purpose model for this project:** one model can cover several pipeline layers at once (OCR + page/line garbage classification + structure + bbox-based verification questions) instead of a zoo of narrow specialized models. The price — likely not SOTA in any single layer.
- **Option A "text-only LLM correction"** (OCR text → LLM with no access to the image) — a risky path: the paper *"OCR Error Post-Correction with LLMs in Historical Documents: No Free Lunches"* (arXiv 2502.01205) shows it does not reliably improve the result and may introduce new errors (the model smooths the text by language priors, with no way to check against the image). Consider at most as a cheap comparison baseline, not as the main path.

### Bag of Experts — multi-model comparison without ground truth
- Idea: run several different VLMs (Unlimited-OCR, DeepSeek-OCR, Qwen3-VL, Gemma 4) on the same page and compare results against each other — even without post-processing / EPUB assembly this is a useful standalone experiment.
- **Consensus Entropy** (arXiv 2504.11101, *"Consensus Entropy: Harnessing Multi-VLM Agreement for Self-Verifying and Self-Improving OCR"*) — training-free, model-agnostic metric: correct predictions across models converge, errors diverge. Gives a reliability signal **without ground truth and without a reference OCR**.
- **ROVER (Recognizer Output Voting Error Reduction)** — a classic approach from ASR, adaptable to OCR: word/character voting between engine results. Even if no single model produced a fully correct result, character-level voting can assemble the right answer from fragments of different models.
- **Cross-reference bbox between models** — if several models have grounding, one can compare not only text but also the geometry of text blocks; a bbox discrepancy with matching text signals different understanding of layout (a subtle signal, separate from the text diff).
- Practical value: a cheap first experiment (even without the EPUB pipeline) that empirically shows which model is stronger on which artifact types — a natural candidate to start the project.

### Routing / pipeline economics
- Pre-classifying pages (text vs picture/table) is **not needed for accuracy** — unified VLM parsers handle mixed pages in one pass anyway.
- But it may make sense for **cost/speed** (route simple text pages to a cheap path, complex ones to an expensive path with stronger verification) and for **targeted QA** (pages with pictures/tables statistically give more layout errors — worth subjecting them to stricter bbox verification).
- **Tension:** uniform pipeline (simpler, more expensive to process everything maximally carefully) vs classify-then-route (more complex architecturally, more economical).

## Staged Plan (draft, 2026-06-24)

**Stage 1 — Bag of Experts: a diagnostic baseline with no post-processing.**
Take local VLMs, run each on the same set of test pages of various types (clean text, text+illustration, table, page with footnotes, poorly scanned page). Compare results: diff by eye, ROVER-style word/character voting, Consensus Entropy as an agreement metric without ground truth. Where grounding exists — cross-reference bbox between models. Goal: empirically understand which model/combination is stronger on which artifacts, without investing in a full pipeline.

**Model shortlist for Stage 1 (entirely within 12GB VRAM, no CPU offload):**
1. **Unlimited-OCR** (~3.3B, FP16 ≈7.3GB) — the newest SOTA, constant KV-cache.
2. **Surya 2** (<3B, 4–8GB depending on batch) — a single layout+OCR+table model, "best in class under 3B" per the authors, has a dedicated `surya-ocr` Python package.
3. **dots.ocr** (3B: 1.2B vision encoder + Qwen2.5-1.5B backbone, 6–8GB via vLLM) — sensitive to scan resolution (VRAM grows with image size), needs checking on real files.
4. **Gemma 4 E4B** (effective 4B, Q4 ≈4GB) — general-purpose, native OCR/document parsing, ready GGUFs (Ollama/LM Studio).
5. **RolmOCR** (fine-tune of Qwen2.5-VL-7B for OCR, Q4 ≈5–6GB) — specialization on top of a general model.
6. **GLM-OCR** (0.9B) — the lightest found, claims to beat Gemini 3 Pro on some benchmarks, needs independent checking.
7. **Qwen3-VL-8B** — general-purpose, for contrast with RolmOCR (specialization vs base).

Deferred to the "heavy echelon" (second round, with CPU offload for MoE layers): DeepSeek-OCR (conflicting VRAM data, no constant KV-cache — risk of memory growth on long documents), Qwen3-VL-30B-A3B, Gemma 4 26B-A4B.

**How to run the models (runtime for Stage 1):**
The landscape is heterogeneous — specialized OCR models often ship their own custom code (`trust_remote_code=True`, as with Unlimited-OCR's deepencoder.py), Surya 2 has a separate Python package with its own pipeline API, and general-purpose VLMs (Gemma 4, Qwen3-VL) are best supported via GGUF/Ollama/llama.cpp.
- **Raw Python + transformers** (`trust_remote_code`) — recommended for the diagnostic phase (Stage 1): maximum compatibility with new/custom architectures (Unlimited-OCR's R-SWA is unlikely to land in llama.cpp soon), low barrier to entry, no waiting for serving-framework support. Throughput is not critical — in Stage 1 models are run once/a few times on test pages, not under production load.
- **vLLM** — officially supported by Unlimited-OCR and dots.ocr, gives a unified OpenAI-compatible API and batching. Worth switching to it at Stage 5 (scaling to a whole book), where throughput and a uniform interface across models really matter — no point standing it up for one-off diagnostic runs.
- **llama.cpp/GGUF** — best support for mature general-purpose models (Gemma 4, possibly Qwen3-VL), requires mmproj files for vision mode, may lag in support for the newest custom OCR architectures.
- Surya 2 — use its own pip package directly, do not wrap it in serving infrastructure.

**Stage 2 — Choosing the main recognition strategy.**
Based on Stage 1, decide: single model vs ensemble in production; whether a separate classic-OCR pass is needed for cross-check (probably not, per the research findings); how verification is covered for the chosen model — bbox-grounding (if the model supports it, e.g. DeepSeek-OCR) or consensus check (if working as an ensemble).

**Stage 3 — Garbage cleanup (classification, not generation).**
Page-level keep/discard for service pages (ToC, title, copyright, ads, blank). Line/element-level keep/discard inside needed pages (running heads, page numbers, footnotes). Both steps — binary classification by the chosen model, audited by diff, not free generation.

**Stage 4 — Structure reconstruction and EPUB assembly.**
Pipeline VLM → Markdown/HTML → Pandoc → EPUB3. Using bbox: reading order of multi-column layout, attaching caption to illustration, extracting raster fragments of illustrations. Automatic TOC from headings. Linking footnotes to their markers in the text.

**Stage 5 — Scaling and economics.**
Decide: per-page parsing vs the whole book in one pass (via the long context of Qwen3-VL/Unlimited-OCR). Decide: uniform pipeline vs classify-then-route (cheap path for simple text pages, stronger verification for pages with pictures/tables).

**Stage 6 — Quality metric and final comparison of combinations.**
Assemble a small reference (manually verified) set of pages to compute CER/WER as an objective metric. Use Consensus Entropy as a proxy metric without ground truth at large scale. Compare full combinations (model + cleanup strategy + verification strategy) against each other by the final EPUB cleanliness.

## Rejected Ideas
| Idea | Reason for rejection |
|------|----------------------|
| A staged plan starting with classic OCR + preprocessing (stages 0–5 from the first structural draft) | Boring and knowingly worse than the target quality — the user wants to go straight to the LLM/VLM approach; classic OCR is considered at most a cross-check signal, not the foundation |

## Unprocessed Ideas
- Layer 5 (a quality metric for comparing engine combinations) — touched partially via verification/hallucinations, but not addressed separately as a metric for scientific comparison of approaches (CER/WER, human evaluation, etc.).
- The paper *"From Plausibility to Verifiability: Risk-Controlled Generative OCR for VLMs"* (arXiv 2603.19790) — worth reading in detail, may offer a ready formal approach to risk control.

## Key Tensions & Open Questions
- Scan preprocessing needed/not needed — depends on the chosen recognition engine; Layer 1 cannot be decided in isolation from Layer 2/3.
- Anchoring bias in the hybrid approach (OCR text + image into the model) — not studied experimentally.
- ~~Unlimited-OCR (SOTA, fast, no grounding) vs DeepSeek-OCR (grounding/verifiability, but linear KV-cache)~~ [corrected 2026-06-25: Unlimited-OCR does have grounding — the fork is largely resolved, Unlimited gives both properties at once; see `docs/experiments/2026-06-25-unlimited-baseline.md`].
- Per-page parsing vs the whole book in one pass — reliability of stitching text across page boundaries.
- Uniform pipeline vs classify-then-route — simplicity vs economy.
- DeepSeek-OCR — conflicting data on real VRAM usage (calculators give the same numbers as Unlimited-OCR, but there's no constant KV-cache → risk of memory growth on long documents). Not in the Stage 1 shortlist; needs separate empirical checking before use.
- dots.ocr — VRAM grows nonlinearly with input image resolution (vision encoder); exact consumption on real book scans unknown until tested.
- GLM-OCR (0.9B, claims to beat Gemini 3 Pro on some benchmarks) — claim not independently verified, needs validating before trusting.
- Text-only LLM OCR correction (no access to the image) — per the literature ("No Free Lunches", arXiv 2502.01205) it does not reliably improve the result; its place in the plan is undecided — possibly only as a cheap comparison baseline, not a working path.
- Risk-Controlled Generative OCR (arXiv 2603.19790) — not read in detail, may provide a ready formal approach to managing generation risk, relevant for Stage 2/3.
- The "quality metric" layer (Stage 6) — still at the idea stage (CER/WER on a manual reference + Consensus Entropy as proxy); the process of building the reference set and the decision thresholds are not worked out.
- Runtime choice (raw Python/transformers vs vLLM vs llama.cpp) for each specific Stage 1 shortlist model is not verified in practice — the list of what actually supports what is based on docs/search, not on hands-on experience.

## Session Log
| Date | Mode | Summary |
|------|------|---------|
| 2026-06-24 | Divergent | Went through Layer 1 (preprocessing), 2/3 (engine choice + verification/bbox/grounding), 4 (EPUB structure), garbage cleanup (page-level + line-level classification), routing economics. Found the fresh Baidu Unlimited-OCR model (2026-06) as a SOTA candidate. Fixed the key forks for structuring the plan. |
| 2026-06-24 | Structured | Rejected the classic-OCR-first plan as knowingly worse than the target quality. Examined local general-purpose VLMs with native OCR (Qwen3-VL, Gemma 4) and the risks of text-only LLM correction with no image access. Added the Bag of Experts / Consensus Entropy / ROVER / bbox cross-reference idea as a cheap diagnostic experiment without ground truth. Assembled the final 6-stage plan: (1) Bag of Experts baseline, (2) recognition-strategy choice, (3) garbage cleanup via classification, (4) structure + EPUB assembly, (5) scaling/economics, (6) quality metric and final comparison. Refined the model shortlist for 12GB VRAM without offload (Unlimited-OCR, Surya 2, dots.ocr, Gemma 4 E4B, RolmOCR, GLM-OCR, Qwen3-VL-8B) and the launch strategy (raw Python/transformers for diagnostics, vLLM for scaling). Session closed without creating tasks — the project is at the research stage, too early to fix concrete steps in a task tracker. |
