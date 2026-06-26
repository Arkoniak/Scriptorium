#!/usr/bin/env python3
"""Run Baidu Unlimited-OCR on a book's page images (per-page document parsing -> Markdown).

Reads the PNGs produced by extract_pages.py and writes a normalized run under
books/output/<book>/runs/<run-id>/ — one manifest.json plus per-page output. This is a
second model adapter in the Stage 1 "Bag of Experts" harness, sharing run_surya.py's output
layout so comparison tooling targets the format, not the model. See docs/brainstorm.md (Stage 1).

Unlimited-OCR is a DeepSeek-OCR successor (transformers + trust_remote_code). The default
'document parsing.' prompt returns Markdown; a '<|grounding|>...' prompt additionally emits
<|ref|>/<|det|> boxes (consumed by the model's own post-processing). NB: brainstorm.md claimed
this model has no grounding — that is wrong (README-based); the remote code supports it.
"""

import argparse
import ast
import json
import os
import re
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

MODEL_NAME = "baidu/Unlimited-OCR"
PARSING_PROMPT = "<image>document parsing."
GROUNDING_PROMPT = "<image>\n<|grounding|>Given the layout of the image."

# Grounding output is a sequence of "<|ref|>label<|/ref|><|det|>[box]<|/det|>text" or the shorter
# "<|det|>label [box]<|/det|>text" form. Coordinates are 0-1000 normalized.
GROUNDING_RE = re.compile(
    r"<\|ref\|>(?P<rlabel>.*?)<\|/ref\|><\|det\|>(?P<rbox>.*?)<\|/det\|>"
    r"|<\|det\|>\s*(?P<dlabel>[A-Za-z_][\w-]*)\s*(?P<dbox>\[[^\]]+\])\s*<\|/det\|>",
    re.DOTALL,
)


def page_number(path: Path) -> int:
    """Extract the page number from a name like page_012.png; fall back to 0."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _norm_boxes(box_str: str) -> list[list[float]]:
    """Parse a det box string into a list of [x1,y1,x2,y2] (0-1000 coords)."""
    try:
        coords = ast.literal_eval(box_str.strip())
    except (ValueError, SyntaxError):
        return []
    if coords and isinstance(coords[0], (int, float)):
        coords = [coords]
    return [list(c) for c in coords if len(c) >= 4]


def parse_grounding(raw: str, width: int, height: int) -> tuple[str, list[dict]]:
    """Parse Unlimited-OCR grounding output into (clean_text, blocks).

    Each block carries its label, the text following its tag, and the bbox in both the model's
    0-1000 space (bbox_norm) and pixels (bbox, scaled by the page size). Any preamble before the
    first tag — the model sometimes emits a spurious refusal note — is dropped by construction.
    """
    matches = list(GROUNDING_RE.finditer(raw))
    blocks = []
    texts = []
    for i, match in enumerate(matches):
        label = (match.group("rlabel") or match.group("dlabel") or "").strip()
        box_str = match.group("rbox") or match.group("dbox") or "[]"
        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        block_text = raw[match.end() : text_end].strip()

        boxes_norm = _norm_boxes(box_str)
        boxes_px = [
            [round(b[0] / 1000 * width), round(b[1] / 1000 * height),
             round(b[2] / 1000 * width), round(b[3] / 1000 * height)]
            for b in boxes_norm
        ]
        blocks.append(
            {
                "text": block_text,
                "label": label,
                "bbox": boxes_px[0] if boxes_px else None,
                "bbox_all": boxes_px,
                "bbox_norm": boxes_norm,
            }
        )
        if block_text:
            texts.append(block_text)
    return "\n\n".join(texts), blocks


def run_unlimited(
    book: str,
    pages_dir: Path,
    out_root: Path,
    pages_filter: set[int] | None,
    label: str,
    prompt: str,
    grounding: bool,
) -> dict:
    """Run Unlimited-OCR per page and write a normalized run; return the manifest.

    Two modes:
      - default: 'document parsing.' prompt -> Markdown via infer()'s post-processing (also
        extracts figures to <page_out>/images/); blocks stay empty.
      - grounding: '<|grounding|>...' prompt + eval_mode=True returns the raw tagged output, which
        we parse into structured blocks (text + label + bbox). Raw output is kept for audit.

    Raises ValueError if no matching page images are found.
    """
    images_paths = sorted(pages_dir.glob("*.png"), key=page_number)
    if pages_filter is not None:
        images_paths = [p for p in images_paths if page_number(p) in pages_filter]
    if not images_paths:
        raise ValueError(f"No matching page images found in {pages_dir}")

    # The SAM vision encoder's peak allocation is large for high-res page tiles; on 12GB it OOMs
    # by a hair due to fragmentation. expandable_segments reclaims reserved-but-unallocated memory.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # Lazy imports: only pay the torch/transformers load when actually running.
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoTokenizer

    run_id = f"{utc_now()}__unlimited__{label}"
    run_dir = out_root / book / "runs" / run_id
    run_pages_dir = run_dir / "pages"
    run_pages_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    )
    model = model.eval().cuda()

    page_numbers = [page_number(p) for p in images_paths]
    per_page_s: dict[str, float] = {}
    started_at = utc_now()
    start = time.time()

    for page_no, src_path in zip(page_numbers, images_paths):
        page_out = run_pages_dir / f"page_{page_no:03d}"
        page_out.mkdir(parents=True, exist_ok=True)

        page_start = time.time()
        # Shared "gundam" single-image preprocessing (base_size=1024, image_size=640, crop).
        infer_kwargs = dict(
            image_file=str(src_path),
            output_path=str(page_out),
            base_size=1024,
            image_size=640,
            crop_mode=True,
            max_length=32768,
            no_repeat_ngram_size=35,
            ngram_window=128,
        )
        if grounding:
            # eval_mode returns the raw tagged output (no post-processing / box drawing).
            raw = model.infer(tokenizer, prompt=prompt, eval_mode=True, save_results=False, **infer_kwargs)
            (page_out / "raw.txt").write_text(raw, encoding="utf-8")
            width, height = Image.open(src_path).size
            text, blocks = parse_grounding(raw, width, height)
            page_format = "grounding"
        else:
            # infer writes <page_out>/result.md (Markdown) and figures under <page_out>/images/.
            model.infer(tokenizer, prompt=prompt, save_results=True, **infer_kwargs)
            result_md = page_out / "result.md"
            text = result_md.read_text(encoding="utf-8") if result_md.exists() else ""
            blocks = []
            page_format = "markdown"
        per_page_s[str(page_no)] = round(time.time() - page_start, 2)

        (run_pages_dir / f"page_{page_no:03d}.json").write_text(
            json.dumps(
                {
                    "page": page_no,
                    "source_image": src_path.name,
                    "text": text,
                    "format": page_format,
                    "blocks": blocks,
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
        "model": "unlimited-ocr",
        "mode": "grounding_per_page" if grounding else "gundam_per_page",
        "prompt": prompt,
        "coordinate_space": "0-1000 normalized; bbox is scaled to pixels, bbox_norm keeps original" if grounding else None,
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
    parser.add_argument(
        "--grounding",
        action="store_true",
        help="Grounding mode: capture <|det|> label+bbox per block as structured blocks (text+bbox+label).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override the prompt (incl. the <image> token). Defaults to the grounding prompt with "
        "--grounding, else the document-parsing prompt.",
    )
    args = parser.parse_args()

    pages_dir = args.pages_dir or (args.out_root / args.book / "pages")
    pages_filter = {int(p) for p in args.pages.split(",")} if args.pages else None
    prompt = args.prompt or (GROUNDING_PROMPT if args.grounding else PARSING_PROMPT)

    try:
        manifest = run_unlimited(
            book=args.book,
            pages_dir=pages_dir,
            out_root=args.out_root,
            pages_filter=pages_filter,
            label=args.label,
            prompt=prompt,
            grounding=args.grounding,
        )
    except ValueError as error:
        parser.error(str(error))

    timing = manifest["timing_s"]
    print(f"Run written to {manifest['run_dir']}")
    print(f"  {timing['num_pages']} pages in {timing['total']}s ({timing['avg_per_page']}s/page)")


if __name__ == "__main__":
    main()
