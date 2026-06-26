# Model comparison matrix

Durable, at-a-glance capability tracker for the OCR/VLM models we evaluate. The per-experiment
narrative lives in `docs/experiments/`; this file is the structured summary that must survive a
context reset. **Update it whenever a model is evaluated or a new capability is observed.**

## What we track (criteria)

- **Fits 12GB** — runs on the target RTX 4070 Super (12GB) without CPU offload, and at what config
  (quant, flags). The hard gate: if it doesn't fit, nothing else matters.
- **Runtime** — how it's actually launched (own package / transformers in-process / llama-server GGUF).
- **Speed** — amortized seconds per page on the 4070 Super.
- **Output format** — plain text / Markdown / HTML.
- **Inline emphasis** — does it preserve italic/bold *inside* a paragraph (e.g. `<i>` or `*...*`)?
  Carries meaning in fiction; lost emphasis can't be recovered downstream.
- **Bounding boxes** — does it emit structured per-element coordinates (grounding), not just a drawn
  image?
- **Layout labels** — semantic element types (title / text / header / footer / picture / ...).
- **Figure extraction** — does it crop illustrations to raster files (vs only labelling the region)?
- **Text hygiene** — de-hyphenates words split across line breaks; preserves typographic quotes.
- **Multi-page one-pass** — can it parse many pages in a single pass (long-document / flat-KV)?
- **Lineage** — model family, for ROVER/ensemble diversity reasoning (independent errors vote better).

*(Add a criterion here when a new axis of difference shows up — don't let it stay ephemeral.)*

## Matrix

| Criterion | Surya 2 | Unlimited-OCR | Qwen3-VL-8B | GLM-OCR (0.9B) |
|---|---|---|---|---|
| Fits 12GB | ✅ (no docker; GGUF backend) | ✅ but tight — needs `expandable_segments` (bf16 safetensors) | ✅ comfortable (Q4_K_M + f16 mmproj) | ✅ trivially (~2GB, 0.9B) |
| Runtime | `surya-ocr` pkg → spawns llama-server (GGUF) | transformers + `trust_remote_code`, in-process | we spawn llama-server (GGUF + `--mmproj`) | transformers in-process; needs 5.x (isolated via `uv run --with`) |
| Speed | ~6.4 s/page | ~5.2 s/page | ~8.5 s/page | **~3.9 s/page** (fastest) |
| Output format | per-block HTML | Markdown (default) / raw grounding text | Markdown (headings, emphasis) | plain text / Markdown |
| **Inline emphasis** | ✅ `<i>` | ❌ dropped under every prompt | ✅ `*italic*` (recall good; precision unaudited) | ❌ dropped |
| Bounding boxes | ✅ polygon + bbox + confidence | ✅ via grounding mode (0–1000 coords) | ❌ (plain chat API) | ❌ (plain mode; JSON/grounding modes untested) |
| Layout labels | ✅ PageHeader/Footer/SectionHeader/Picture/Text | ✅ in grounding (title/text/image) | ➖ Markdown headings only | ➖ Markdown only |
| Figure extraction | ❌ labels Picture, no raster | ✅ crops illustrations to image files | ❌ | ❌ |
| Text hygiene | ✅ de-hyphenates, keeps curly quotes | ➖ keeps soft-hyphens, inconsistent quotes | ✅ curly quotes; omits running headers | ✅ de-hyphenates, curly quotes |
| Multi-page one-pass | ❌ per-page | ✅ flat-KV (headline feature; untested) | ❌ per-page | ❌ per-page |
| Lineage | Datalab (own arch) | DeepSeek-OCR successor (Baidu) | Alibaba/Qwen (general-purpose) | Zhipu / Z.ai (GLM) |
| Experiments | [surya-baseline](experiments/2026-06-25-surya-baseline.md) | [baseline](experiments/2026-06-25-unlimited-baseline.md), [grounding](experiments/2026-06-26-unlimited-grounding.md) | [baseline](experiments/2026-06-26-qwen3vl-baseline.md) | [baseline](experiments/2026-06-26-glm-ocr-baseline.md) |

Legend: ✅ yes / ❌ no / ➖ partial-or-weak / ⏳ not yet measured.

## Excluded

- **Gemma 4 E4B** (general VLM, Google lineage) — **evaluated and dropped.** Its GGUF vision can't read
  dense scanned body text: at the default budget it fabricates the body; raising resolution crashes
  (ubatch), then loops, then fabricates fluently. Fabrication would poison the consensus, so it is out
  of the ensemble. See [gemma-vision-failure](experiments/2026-06-26-gemma-vision-failure.md).

## Shortlist — not yet integrated (revisit later)

- **PaddleOCR-VL** (0.9B, multilingual) — **OmniDocBench accuracy leader** (v1.6 ≈ 96.33%). **Deferred:**
  the transformers integration is a version swamp and the native arch is ~454s/page; the viable
  runtimes are vLLM (best fit — OpenAI API) or the official PaddlePaddle pipeline. Worth getting right
  later (leader + multilingual). See [paddleocr-vl-deferred](experiments/2026-06-26-paddleocr-vl-deferred.md).
- **FireRed OCR** — surfaced as a "best balanced operational choice" in 2026 OCR roundups; not yet
  evaluated.
- **DeepSeek-OCR**, **dots.ocr**, **RolmOCR** — original Stage 1 shortlist, still untried (DeepSeek-OCR
  is the parent of Unlimited; dots.ocr wants vLLM; RolmOCR is a Qwen2.5-VL fine-tune).

## Open cross-model questions

- Do **general-purpose** VLMs match the specialists on dense scanned prose? Mixed: Qwen3-VL yes (and it
  preserves inline emphasis where Unlimited does not); Gemma 4 E4B no (excluded — fabricates dense text).
- ROVER / Consensus needs ≥3 independent models; Surya and Unlimited already show **complementary**
  errors on stylized cover logos — the strongest ensemble signal so far.
- Test-set gap: no tables or footnotes in the current book — structure-markup differences may widen
  there.
