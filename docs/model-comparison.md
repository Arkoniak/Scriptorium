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

| Criterion | Surya 2 | Unlimited-OCR | Qwen3-VL-8B |
|---|---|---|---|
| Fits 12GB | ✅ (no docker; GGUF backend) | ✅ but tight — needs `expandable_segments` (bf16 safetensors) | ✅ comfortable (Q4_K_M + f16 mmproj) |
| Runtime | `surya-ocr` pkg → spawns llama-server (GGUF) | transformers + `trust_remote_code`, in-process | we spawn llama-server (GGUF + `--mmproj`) |
| Speed | ~6.4 s/page | ~5.2 s/page | ~8.5 s/page |
| Output format | per-block HTML | Markdown (default) / raw grounding text | Markdown (headings, emphasis) |
| **Inline emphasis** | ✅ `<i>` | ❌ dropped under every prompt | ✅ `*italic*` (recall good; precision unaudited) |
| Bounding boxes | ✅ polygon + bbox + confidence | ✅ via grounding mode (0–1000 coords) | ❌ (plain chat API) |
| Layout labels | ✅ PageHeader/Footer/SectionHeader/Picture/Text | ✅ in grounding (title/text/image) | ➖ Markdown headings only |
| Figure extraction | ❌ labels Picture, no raster | ✅ crops illustrations to image files | ❌ |
| Text hygiene | ✅ de-hyphenates, keeps curly quotes | ➖ keeps soft-hyphens, inconsistent quotes | ✅ curly quotes; omits running headers |
| Multi-page one-pass | ❌ per-page | ✅ flat-KV (headline feature; untested) | ❌ per-page |
| Lineage | Datalab (own arch) | DeepSeek-OCR successor (Baidu) | Alibaba/Qwen (general-purpose) |
| Experiments | [surya-baseline](experiments/2026-06-25-surya-baseline.md) | [baseline](experiments/2026-06-25-unlimited-baseline.md), [grounding](experiments/2026-06-26-unlimited-grounding.md) | [baseline](experiments/2026-06-26-qwen3vl-baseline.md) |

Legend: ✅ yes / ❌ no / ➖ partial-or-weak / ⏳ not yet measured.

## Open cross-model questions

- Do **general-purpose** VLMs (Qwen3-VL, Gemma 4) match the specialists on dense scanned prose, and do
  they preserve inline emphasis where Unlimited does not?
- ROVER / Consensus needs ≥3 independent models; Surya and Unlimited already show **complementary**
  errors on stylized cover logos — the strongest ensemble signal so far.
- Test-set gap: no tables or footnotes in the current book — structure-markup differences may widen
  there.
