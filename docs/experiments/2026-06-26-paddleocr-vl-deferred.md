# PaddleOCR-VL — accuracy leader, deferred (transformers runtime swamp)

Surfaced when re-searching for models we'd missed: **PaddleOCR-VL** is the current OmniDocBench
accuracy leader (v1.6 ≈ 96.33%, above GLM-OCR's 94.62 and Unlimited's 93.92), a compact 0.9B
multilingual document VLM — and multilingual matters for future Russian books. We tried to add it as a
5th working model via our usual transformers-in-process path. **Deferred** — the transformers
integration is a version swamp and the native arch is too slow.

## What we tried (all transformers paths failed or were impractical)
| Path | Result |
|---|---|
| `trust_remote_code` @ transformers 5.12.1 | crash at init: `ROPE_INIT_FUNCTIONS['default']` KeyError (5.x renamed it) |
| `trust_remote_code` @ project 4.57.6 | needs `sentencepiece` + `protobuf`; then crashes in forward: `create_causal_mask() got an unexpected keyword 'inputs_embeds'` (kwarg renamed) |
| native `paddleocr_vl` arch @ 5.12.1 (no remote code) | loads and runs, but generation is **pathologically slow (~454s/page)** — the image encodes to ~3577 vision tokens and the fresh native impl decodes very slowly / without early stop |

The authors' remote code is pinned to a narrow transformers version that is neither our 4.57.6 nor
5.12.1; the native implementation just landed and isn't yet practical.

## Why deferred, not dropped (vs Gemma)
Unlike Gemma (which *fabricated* — a correctness failure that poisons consensus), PaddleOCR-VL is a
**runtime/integration** problem, not a quality one. On paper it's the strongest model and it's
multilingual. The viable runtimes are just heavier than our simple transformers approach:
- **vLLM** — officially supported, exposes an OpenAI-compatible API → the *best* fit for our existing
  server-style runners (run_qwen3vl.py / run_gemma.py talk to exactly that). Cost: heavy install + its
  own dependency pins.
- **Official PaddlePaddle pipeline** — `paddleocr` + `paddlepaddle-gpu` in a separate venv; page-level
  parsing, but a different integration and a heavy non-PyTorch stack.

## Decision
Defer PaddleOCR-VL; proceed with the **4 working models** (Surya, Unlimited-OCR, Qwen3-VL, GLM-OCR) for
the consolidation phase. Revisit PaddleOCR-VL via **vLLM** (preferred — fits the runner pattern) when
worthwhile — it's the accuracy leader and multilingual, so it's worth getting right later, not via the
broken transformers path. `scripts/run_paddleocr.py` is kept (DEFERRED) as the reproducible artifact.

Rationale: known.
