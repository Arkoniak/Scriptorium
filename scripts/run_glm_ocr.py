#!/usr/bin/env python3
"""Run Zhipu GLM-OCR (0.9B) on a book's page images (per-page document parsing).

Fourth Bag-of-Experts adapter. GLM-OCR is a tiny (0.9B) OCR VLM (CogViT vision + GLM decoder) that
tops OmniDocBench despite its size. It runs via transformers in-process, BUT its architecture
(`glm_ocr`) landed only in transformers 5.x, newer than this project's pinned 4.57.6 (kept for the
other models). So run this script with an isolated newer transformers:

    uv run --with "transformers==5.12.1" scripts/run_glm_ocr.py --book mindblast

Output goes into the shared normalized run layout. See docs/brainstorm.md (Stage 1) and
docs/model-comparison.md.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

MODEL_NAME = "zai-org/GLM-OCR"
DEFAULT_PROMPT = "Text Recognition:"


def page_number(path: Path) -> int:
    """Extract the page number from a name like page_012.png; fall back to 0."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_glm_ocr(
    book: str,
    pages_dir: Path,
    out_root: Path,
    pages_filter: set[int] | None,
    label: str,
    prompt: str,
    max_new_tokens: int,
) -> dict:
    """Run GLM-OCR per page and write a normalized run; return the manifest.

    Raises ValueError if no matching page images are found.
    """
    images_paths = sorted(pages_dir.glob("*.png"), key=page_number)
    if pages_filter is not None:
        images_paths = [p for p in images_paths if page_number(p) in pages_filter]
    if not images_paths:
        raise ValueError(f"No matching page images found in {pages_dir}")

    # Lazy imports: only pay the torch/transformers load when actually running.
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageTextToText.from_pretrained(MODEL_NAME, dtype="auto").eval().to("cuda")

    run_id = f"{utc_now()}__glm-ocr__{label}"
    run_dir = out_root / book / "runs" / run_id
    run_pages_dir = run_dir / "pages"
    run_pages_dir.mkdir(parents=True, exist_ok=True)

    page_numbers = [page_number(p) for p in images_paths]
    per_page_s: dict[str, float] = {}
    started_at = utc_now()
    start = time.time()

    for page_no, src_path in zip(page_numbers, images_paths):
        page_start = time.time()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": str(src_path)},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        ).to(model.device)
        inputs.pop("token_type_ids", None)
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=max_new_tokens)
        new_tokens = generated[0][inputs["input_ids"].shape[1] :]
        text = processor.decode(new_tokens, skip_special_tokens=True).strip()
        raw = processor.decode(new_tokens, skip_special_tokens=False)
        per_page_s[str(page_no)] = round(time.time() - page_start, 2)

        page_out = run_pages_dir / f"page_{page_no:03d}"
        page_out.mkdir(parents=True, exist_ok=True)
        (page_out / "raw.txt").write_text(raw, encoding="utf-8")
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
        "model": "glm-ocr",
        "mode": "per_page",
        "prompt": prompt,
        "library": f"transformers=={version('transformers')}",
        "model_checkpoint": MODEL_NAME,
        "book": book,
        "input_dir": str(pages_dir),
        "pages": page_numbers,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "dtype": str(model.dtype),
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
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Task prompt (default: 'Text Recognition:')")
    parser.add_argument("--max-new-tokens", type=int, default=8192, help="Max output tokens per page")
    args = parser.parse_args()

    pages_dir = args.pages_dir or (args.out_root / args.book / "pages")
    pages_filter = {int(p) for p in args.pages.split(",")} if args.pages else None

    try:
        manifest = run_glm_ocr(
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
