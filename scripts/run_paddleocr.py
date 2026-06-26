#!/usr/bin/env python3
"""Run PaddleOCR-VL (0.9B) on a book's page images (per-page OCR).

⚠️ DEFERRED — not in the ensemble yet. PaddleOCR-VL is the OmniDocBench accuracy leader, but its
transformers integration is a version swamp and the native arch is too slow to be practical:
  - trust_remote_code @ transformers 5.x → crashes (ROPE_INIT_FUNCTIONS['default']);
  - trust_remote_code @ 4.57.6 → crashes in forward (create_causal_mask kwarg mismatch);
  - native `paddleocr_vl` arch @ 5.12.1 → loads but generation is pathologically slow (~454s/page).
The viable runtimes are heavier — the official PaddlePaddle pipeline or vLLM (OpenAI API, the best
fit for our runners). Revisit via one of those. See docs/experiments/2026-06-26-paddleocr-vl-deferred.md.
This script (native-arch path) is kept only as the reproducible artifact behind the finding.

PaddleOCR-VL is the current OmniDocBench accuracy leader
(v1.6 ≈ 96.33%), a compact 0.9B multilingual document VLM. Run via transformers in-process using the
NATIVE `paddleocr_vl` arch (the repo's trust_remote_code path targets an older transformers and
crashes on ROPE_INIT_FUNCTIONS['default']). That arch landed in transformers 5.x, newer than this
project's pinned 4.57.6 (kept for the other models), so run this script with an isolated newer one:

    uv run --with "transformers==5.12.1" scripts/run_paddleocr.py --book mindblast

Note: the transformers path does element-level recognition (the official PaddleOCR pipeline adds a
layout model for full page-level parsing). Our pages are single-column prose, so feeding the whole
page with the "OCR:" prompt is expected to work; revisit if multi-column/complex pages appear.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

MODEL_NAME = "PaddlePaddle/PaddleOCR-VL"
DEFAULT_PROMPT = "OCR:"  # task prompts: 'OCR:' | 'Table Recognition:' | 'Formula Recognition:' | 'Chart Recognition:'


def page_number(path: Path) -> int:
    """Extract the page number from a name like page_012.png; fall back to 0."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_paddleocr(
    book: str,
    pages_dir: Path,
    out_root: Path,
    pages_filter: set[int] | None,
    label: str,
    prompt: str,
    max_new_tokens: int,
) -> dict:
    """Run PaddleOCR-VL per page and write a normalized run; return the manifest.

    Raises ValueError if no matching page images are found.
    """
    images_paths = sorted(pages_dir.glob("*.png"), key=page_number)
    if pages_filter is not None:
        images_paths = [p for p in images_paths if page_number(p) in pages_filter]
    if not images_paths:
        raise ValueError(f"No matching page images found in {pages_dir}")

    # Lazy imports: only pay the torch/transformers load when actually running.
    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor

    # Use the NATIVE paddleocr_vl arch (in transformers 5.x) rather than the repo's trust_remote_code:
    # the remote modeling code targets an older transformers and crashes on ROPE_INIT_FUNCTIONS['default'].
    model = AutoModelForImageTextToText.from_pretrained(MODEL_NAME, dtype=torch.bfloat16).to("cuda").eval()
    processor = AutoProcessor.from_pretrained(MODEL_NAME)

    run_id = f"{utc_now()}__paddleocr__{label}"
    run_dir = out_root / book / "runs" / run_id
    run_pages_dir = run_dir / "pages"
    run_pages_dir.mkdir(parents=True, exist_ok=True)

    page_numbers = [page_number(p) for p in images_paths]
    per_page_s: dict[str, float] = {}
    started_at = utc_now()
    start = time.time()

    for page_no, src_path in zip(page_numbers, images_paths):
        page_start = time.time()
        image = Image.open(src_path).convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        ).to("cuda")
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=max_new_tokens)
        new_tokens = generated[0][inputs["input_ids"].shape[1] :]
        text = processor.decode(new_tokens, skip_special_tokens=True).strip()
        per_page_s[str(page_no)] = round(time.time() - page_start, 2)

        (run_pages_dir / f"page_{page_no:03d}.md").write_text(text + "\n", encoding="utf-8")
        (run_pages_dir / f"page_{page_no:03d}.json").write_text(
            json.dumps(
                {
                    "page": page_no,
                    "source_image": src_path.name,
                    "text": text,
                    "format": "markdown",
                    "blocks": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    total_s = time.time() - start
    finished_at = utc_now()

    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "model": "paddleocr-vl",
        "mode": "per_page_element",
        "prompt": prompt,
        "library": f"transformers=={version('transformers')}",
        "model_checkpoint": MODEL_NAME,
        "book": book,
        "input_dir": str(pages_dir),
        "pages": page_numbers,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "dtype": "torch.bfloat16",
        "gpu": gpu,
        "started_at": started_at,
        "finished_at": finished_at,
        "timing_s": {
            "total": round(total_s, 2),
            "num_pages": len(images_paths),
            "avg_per_page": round(total_s / len(images_paths), 2),
            "per_page": per_page_s,
        },
        "label": label,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True, help="Book slug, e.g. 'mindblast'")
    parser.add_argument("--out-root", type=Path, default=Path("books/output"), help="Artifacts root")
    parser.add_argument("--pages-dir", type=Path, help="Override input dir (default: <out-root>/<book>/pages)")
    parser.add_argument("--pages", help="Optional page filter, e.g. '1,5,12' (default: all images found)")
    parser.add_argument("--label", default="default", help="Human label for this run, used in the run id")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Task prompt (default: 'OCR:')")
    parser.add_argument("--max-new-tokens", type=int, default=4096, help="Max output tokens per page")
    args = parser.parse_args()

    pages_dir = args.pages_dir or (args.out_root / args.book / "pages")
    pages_filter = {int(p) for p in args.pages.split(",")} if args.pages else None

    try:
        manifest = run_paddleocr(
            book=args.book,
            pages_dir=pages_dir,
            out_root=args.out_root,
            pages_filter=pages_filter,
            label=args.label,
            prompt=args.prompt,
            max_new_tokens=args.max_new_tokens,
        )
    except ValueError as error:
        parser.error(str(error))

    timing = manifest["timing_s"]
    print(f"Run written to {manifest['run_dir']}")
    print(f"  {timing['num_pages']} pages in {timing['total']}s ({timing['avg_per_page']}s/page)")


if __name__ == "__main__":
    main()
