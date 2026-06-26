# Gemma 4 E4B — vision-resolution failure on dense scans (excluded)

Intended fifth model (a second general VLM, Google lineage). Outcome: **excluded** — it cannot
reliably OCR dense scanned body text, and its failure mode (fabrication) would poison the consensus.
Worth recording in full as a cautionary tale about general-VLM GGUF vision for OCR.

## Setup
- **Model:** Gemma 4 E4B, GGUF `Q5_K_M` + `mmproj-F16` (`unsloth/gemma-4-E4B-it-GGUF`), via llama-server
  (same runtime as Qwen3-VL). 9-page Mindblast smoke on page 12 (the action/dialogue page).

## What happened — the full saga
1. **Default vision budget → hallucination.** The mmproj reports `image_size: 224`,
   `image_max_pixels: 645120`; the whole 1830×3338 page is encoded into a **single 264-token slice**.
   Gemma read only the large header ("4 / SPACE COPS") and **fabricated the entire body** — invented a
   coherent fake scene ("a small, dark room … filled with crates and barrels …") with none of page 12's
   real text. The small print is simply below the encoder's effective resolution.
2. **Raise resolution (`--image-max-tokens 2048`) → crash.** This works (`image_max_pixels` →
   4718592, image now 2013 tokens), but llama-server aborts:
   `GGML_ASSERT(... n_ubatch >= n_tokens) ... non-causal attention requires n_ubatch >= n_tokens` —
   the vision tokens are attended non-causally in one batch, so the image must fit a single ubatch.
3. **Fix the batch (`-b 2048 -ub 2048`) → repetition loop.** No crash, and it now *sees* real words,
   but greedy decoding degenerates into "MINDS A LITTLE MORE OF THE …" repeated in all caps.
4. **Anti-loop sampling (`repeat_penalty 1.3` + DRY + `temp 0.3`) → fluent fabrication.** The loop
   clears, but the output is grammatical *invention*: "than other minds were counting on their own
   side; the charge was a little more powerful …" — it catches scattered real words ("minds", "a
   little more") and weaves them into a fabricated narrative. Still not page 12.

Every knob (resolution, ubatch, sampling) was exhausted; there is no setting that yields a faithful
transcription of this dense page.

## Why it matters
- **Contrast:** the same runtime (llama-server + mmproj) gives Qwen3-VL a faithful read — because
  Qwen3-VL's vision tiles to high resolution natively (and llama.cpp implements it), whereas Gemma's
  encoder here does one fixed low-res slice; raising it exposes batch and decoding fragility. So
  "general VLM + GGUF vision" is **not** uniformly usable for OCR — it depends entirely on the model's
  vision pipeline.
- **Fabrication is the worst failure mode** for an ensemble: it is fluent and plausible, so it would
  silently poison ROVER/consensus. A model that *can't read but invents* must be kept out, not voted in.

## Decision
**Gemma 4 E4B is excluded from the Bag of Experts.** The four working models (Surya, Unlimited-OCR,
Qwen3-VL, GLM-OCR) read dense body text faithfully and are a sufficient, sound ensemble. `scripts/run_gemma.py`
is kept (with a warning) only as the reproducible artifact behind this finding; it is not wired into
`scripts/run_full_book.sh`.

Note (knob clarification surfaced while debugging): two distinct token budgets — `--image-max-tokens`
controls *visual resolution* (input detail, VRAM-bound), while the request `max_tokens` controls
*transcription length* (what would truncate a long/Russian page). They are independent.

Rationale: known.
