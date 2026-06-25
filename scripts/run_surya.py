#!/usr/bin/env python3
"""Run Surya (full-page OCR, the "Surya 2" foundation model) on a book's page images.

Reads the PNGs produced by extract_pages.py and writes a normalized run under
books/output/<book>/runs/<run-id>/ — one manifest.json plus per-page text + JSON.
This is one model adapter in the Stage 1 "Bag of Experts" harness; all model
runners share the same output layout so comparison tooling can target the format,
not the model. See docs/brainstorm.md (Stage 1) and the experiments skill.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from importlib.metadata import version
from pathlib import Path


def strip_html(html: str) -> str:
    """Crude HTML -> plain text for human-readable previews; the JSON keeps the real HTML."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def page_number(path: Path) -> int:
    """Extract the page number from a name like page_012.png; fall back to 0."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_surya(
    book: str,
    pages_dir: Path,
    out_root: Path,
    pages_filter: set[int] | None,
    label: str,
    backend: str,
) -> dict:
    """Run Surya full-page OCR over the page images and write a normalized run.

    Returns the run manifest (which includes the run directory and timing).
    Raises ValueError if no matching page images are found.
    """
    images_paths = sorted(pages_dir.glob("*.png"), key=page_number)
    if pages_filter is not None:
        images_paths = [p for p in images_paths if page_number(p) in pages_filter]
    if not images_paths:
        raise ValueError(f"No matching page images found in {pages_dir}")

    # Surya 2 serves the VLM via an external backend. Select it before importing surya so
    # pydantic-settings picks it up. "llamacpp" spawns a native llama-server (no docker);
    # "vllm" spawns a docker container that needs the nvidia container runtime.
    os.environ["SURYA_INFERENCE_BACKEND"] = backend

    # Lazy imports: only pay the torch/surya load when actually running, not at import/--help time.
    import torch
    from PIL import Image
    from surya.inference import SuryaInferenceManager
    from surya.recognition import RecognitionPredictor
    from surya.settings import settings

    run_id = f"{utc_now()}__surya__{label}"
    run_dir = out_root / book / "runs" / run_id
    run_pages_dir = run_dir / "pages"
    run_pages_dir.mkdir(parents=True, exist_ok=True)

    images = [Image.open(p).convert("RGB") for p in images_paths]
    page_numbers = [page_number(p) for p in images_paths]

    manager = SuryaInferenceManager()
    predictor = RecognitionPredictor(manager)

    started_at = utc_now()
    start = time.time()
    results = predictor(images, full_page=True)
    total_s = time.time() - start
    finished_at = utc_now()

    for page_no, src_path, result in zip(page_numbers, images_paths, results):
        blocks = [
            {
                "text": strip_html(block.html),
                "html": block.html,
                "bbox": block.bbox,
                "polygon": block.polygon,
                "confidence": block.confidence,
                "label": block.label,
                "reading_order": block.reading_order,
                "skipped": block.skipped,
            }
            for block in result.blocks
        ]
        ordered = sorted(blocks, key=lambda b: b["reading_order"])
        page_text = "\n\n".join(b["text"] for b in ordered if b["text"])

        (run_pages_dir / f"page_{page_no:03d}.txt").write_text(page_text + "\n", encoding="utf-8")
        (run_pages_dir / f"page_{page_no:03d}.json").write_text(
            json.dumps(
                {
                    "page": page_no,
                    "source_image": src_path.name,
                    "text": page_text,
                    "blocks": ordered,
                    "image_bbox": result.image_bbox,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "model": "surya",
        "mode": "full_page",
        "backend": settings.SURYA_INFERENCE_BACKEND,
        "library": f"surya-ocr=={version('surya-ocr')}",
        "model_checkpoint": settings.SURYA_MODEL_CHECKPOINT,
        "gguf": (
            {
                "repo": settings.SURYA_GGUF_REPO,
                "model_file": settings.SURYA_GGUF_MODEL_FILE,
                "mmproj_file": settings.SURYA_GGUF_MMPROJ_FILE,
            }
            if settings.SURYA_INFERENCE_BACKEND == "llamacpp"
            else None
        ),
        "book": book,
        "input_dir": str(pages_dir),
        "pages": page_numbers,
        "device": settings.TORCH_DEVICE_MODEL,
        "dtype": str(settings.MODEL_DTYPE),
        "gpu": gpu,
        "started_at": started_at,
        "finished_at": finished_at,
        "timing_s": {
            "total": round(total_s, 2),
            "num_pages": len(images),
            "avg_per_page": round(total_s / len(images), 2),
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
    parser.add_argument(
        "--backend",
        default="llamacpp",
        choices=["llamacpp", "vllm"],
        help="Surya inference backend (default: llamacpp, native llama-server, no docker)",
    )
    args = parser.parse_args()

    pages_dir = args.pages_dir or (args.out_root / args.book / "pages")
    pages_filter = {int(p) for p in args.pages.split(",")} if args.pages else None

    try:
        manifest = run_surya(
            book=args.book,
            pages_dir=pages_dir,
            out_root=args.out_root,
            pages_filter=pages_filter,
            label=args.label,
            backend=args.backend,
        )
    except ValueError as error:
        parser.error(str(error))

    timing = manifest["timing_s"]
    print(f"Run written to {manifest['run_dir']}")
    print(f"  {timing['num_pages']} pages in {timing['total']}s ({timing['avg_per_page']}s/page)")


if __name__ == "__main__":
    main()
