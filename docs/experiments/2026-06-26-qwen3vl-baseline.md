# Qwen3-VL-8B baseline — a general VLM as the third model (and the emphasis answer)

Third Bag-of-Experts model, and the ≥3 we need for ROVER/consensus. Same 9 Mindblast pages. Two
questions: (1) can a general-purpose VLM compete with the OCR specialists on a real scan? (2) does it
preserve inline emphasis — the axis where Unlimited-OCR fell short and Surya did not?

## Setup
- **Model:** Qwen3-VL-8B-Instruct, **GGUF** `Q4_K_M` + `mmproj-F16` (official `Qwen/Qwen3-VL-8B-Instruct-GGUF`).
- **Runtime — a third style:** the script spawns **llama-server** with `--mmproj`, waits for `/health`,
  POSTs each page image to the OpenAI-compatible chat API, then stops the server. (Surya = own package
  spawning llama-server; Unlimited = transformers in-process; Qwen = we drive llama-server ourselves.)
- **Fits 12GB** comfortably (Q4_K_M ~4.8GB + f16 mmproj + KV). Q5 is a future option for a quality bump.
- **Prompt:** asks for clean Markdown preserving paragraphs and inline emphasis (`*italic*`/`**bold**`).
- **Run:** `uv run scripts/run_qwen3vl.py --book mindblast --label baseline`.
  Run id `2026-06-26T12-52-04Z__qwen3vl__baseline` (gitignored under `books/output/`).

## Result
- **Throughput:** 9 pages in 76.5s = **8.5s/page** amortized (4.9s sparse → 11.2s dense). Slower than
  Surya (6.4) and Unlimited (5.2), but fine for the diagnostic phase.
- **Inline emphasis PRESERVED — the headline.** p12 "Another bolt … *A little too close*, he thought"
  came through as Markdown italic (the source is genuinely italic, verified earlier). Emphasis spans
  appear across the sample (pages 1, 12, 256, 260). **The general VLM keeps what the specialist
  Unlimited dropped under every prompt.**
- **Best of the three on stylized cover logos** — front cover: "SpaceCops" (only the space lost vs
  Unlimited's "Sparkaps"), "MINDBLAST" correct, price "$4.95" correct. It beats both Surya (wrong
  "MINEBLAST") and Unlimited (wrong "Sparkaps"/"$9.99") here → strong, *complementary* ROVER diversity:
  Qwen is right exactly where the other two err.
- **Markdown structure:** emits headings (`# MINDBLAST!`), keeps curly quotes and em-dashes.
- **Omits running headers** — it didn't transcribe "4 / SPACE COPS" at all. Convenient (the header is
  noise), but it's a cleanup decision made *inside* the model — less auditable than Surya's explicit
  `PageHeader` label.

## Trade-offs / caveats
- **No figure extraction** — the plain chat API doesn't crop illustrations; the cover art is simply
  absent from the output (Unlimited extracts a raster, Surya labels a Picture region).
- **No bounding boxes / grounding** — plain transcription only.
- **Emphasis precision not audited.** Recall is good and verified (p12). But general VLMs can *add*
  emphasis that isn't there; e.g. p260 marked "**HYPER-2**" / "*drug*" — plausible but unchecked
  against the source. Worth a precision pass before trusting emphasis blindly.

## Three-way Bag-of-Experts picture
| | Surya 2 | Unlimited-OCR | Qwen3-VL-8B |
|---|---|---|---|
| Speed | 6.4 s/pg | 5.2 s/pg | 8.5 s/pg |
| Inline emphasis | ✅ HTML | ❌ | ✅ Markdown |
| Bounding boxes | ✅ | ✅ (grounding) | ❌ |
| Figure raster | ❌ | ✅ | ❌ |
| Stylized logos | ✗ MINDBLAST | ✗ Space Cops | ✅ both ~right |
| Lineage | Datalab | DeepSeek/Baidu | Alibaba/Qwen |

## Conclusion
Qwen3-VL validates the brainstorm hypothesis that a general-purpose VLM with native OCR competes with
the specialists — and on inline emphasis it *leads*. We now have **three independent lineages**
(Datalab / DeepSeek / Qwen) whose errors are clearly complementary (each nails a stylized logo the
others miss), which is exactly the signal ROVER/consensus needs. No single model dominates: Surya for
labels+hygiene+emphasis, Unlimited for speed+figures+grounding+long-doc, Qwen for emphasis+robust
stylized text+structure.

Next: build the ROVER / Consensus comparison tool over the three runs' normalized output (the
strongest first target: per-word voting on the stylized-logo regions, where all three disagree
differently). Then a book with tables/footnotes to close the test-set gap.

Rationale: known.
