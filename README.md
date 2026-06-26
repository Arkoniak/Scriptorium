# Scriptorium

**From a scanned PDF book to a clean EPUB — comparing classic OCR and neural (VLM) approaches.**

Scriptorium is a research / self-learning project. The goal is to convert scanned book pages into
trustworthy, cleanly-structured text, and to find out *empirically* which recognition approach does
that best on a real scan. The name reflects the focus: not just format conversion, but verified,
scriptorium-grade transcription. **This is exploratory work in progress, not a finished tool.**

## Status

Stage 1 of a 6-stage plan — a **"Bag of Experts"** diagnostic: run several models on the same pages
and compare. Three models evaluated so far (Surya 2, Unlimited-OCR, Qwen3-VL-8B) on one test book.
The full plan and accumulated research notes live in [`docs/brainstorm.md`](docs/brainstorm.md).

## Approach

The staged plan (details in [`docs/brainstorm.md`](docs/brainstorm.md)):

1. **Bag of Experts** — run multiple local VLMs on the same test pages; compare without ground truth.
2. **Recognition strategy** — single model vs ensemble; how verification is covered.
3. **Garbage cleanup** — service pages / running heads / footnotes, as KEEP/DISCARD *classification*
   (auditable by diff), never free-form rewriting.
4. **Structure + EPUB assembly** — Markdown/HTML → Pandoc → EPUB3; figures, footnotes, TOC.
5. **Scaling & economics** — per-page vs whole-book-in-one-pass; uniform vs classify-then-route.
6. **Quality metric** — CER/WER on a small reference set + Consensus Entropy as a proxy.

The lever for "is the output right without a reference?" is **agreement across independent models**
(Consensus Entropy, ROVER voting): where models converge they're likely right, where they diverge is
the signal. Each model runs as an adapter writing the **same normalized per-run output**, so
comparison tooling targets the format, not the model.

## Models evaluated so far

| Model | Lineage | Notes |
|---|---|---|
| **Surya 2** | Datalab | layout+OCR specialist; HTML with bbox, labels, confidence; preserves inline emphasis; de-hyphenates |
| **Unlimited-OCR** | DeepSeek-OCR successor (Baidu) | fast; grounding boxes; extracts figure rasters; multi-page one-pass — but drops inline emphasis |
| **Qwen3-VL-8B** | Alibaba/Qwen (general VLM) | preserves emphasis; strongest on stylized logos; no figures/bbox; slower |

Full capability matrix: [`docs/model-comparison.md`](docs/model-comparison.md).

## Key findings so far

- **Complementary errors → a real consensus signal.** On stylized cover logos the three models fail on
  *different* words (each nails one the others miss) — exactly what ROVER/consensus needs, with no
  ground truth.
- **Inline emphasis is a real differentiator.** Surya and Qwen3-VL preserve italics (which carry
  meaning in fiction); Unlimited-OCR drops them under every prompt tried.
- **A general VLM competes with the specialists.** Qwen3-VL holds its own and *leads* on emphasis and
  stylized text — at the cost of figure extraction and grounding.

Per-experiment write-ups (setup, results, conclusions): [`docs/experiments/`](docs/experiments/).

## Repository layout

```
scripts/    extract_pages.py, run_surya.py, run_unlimited.py, run_qwen3vl.py
docs/       brainstorm.md (plan), model-comparison.md (matrix), experiments/ (log)
books/      input/ (source PDFs) and output/ (renders + runs) — gitignored, large binaries
```

## Setup & usage

Requires [pyenv](https://github.com/pyenv/pyenv) (Python 3.14) and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

Render selected pages of a PDF to PNGs:

```bash
uv run scripts/extract_pages.py \
  --pdf books/input/<book>.pdf --pages "1,5,12,20" \
  --out books/output/<book>/pages --dpi 300
```

Run a model over those pages (writes `books/output/<book>/runs/<run-id>/` with a manifest and per-page
text/JSON). Model weights download automatically from Hugging Face on first run.

```bash
uv run scripts/run_surya.py    --book <book>                 # Surya 2 (GGUF via llama-server)
uv run scripts/run_unlimited.py --book <book> [--grounding]  # Unlimited-OCR (transformers, in-process)
uv run scripts/run_qwen3vl.py  --book <book>                 # Qwen3-VL-8B (GGUF via llama-server)
```

**Hardware target:** a single NVIDIA RTX 4070 Super (12GB VRAM); all Stage 1 models fit without CPU
offload. The Surya and Qwen3-VL runners need a CUDA-enabled `llama-server` (from
[llama.cpp](https://github.com/ggml-org/llama.cpp)) on `PATH`.

## License

[MIT](LICENSE).
