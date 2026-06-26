#!/usr/bin/env python3
"""Run Qwen3-VL-8B-Instruct (GGUF) on a book's page images via a llama-server we spawn.

Third Bag-of-Experts adapter, and a third runtime style: a general-purpose VLM served by
llama.cpp's llama-server with a vision mmproj. The script downloads the GGUF + mmproj (cached),
spawns llama-server, waits for /health, POSTs each page image to its OpenAI-compatible API, and
collects the transcription into the shared normalized run layout, then stops the server.

See docs/brainstorm.md (Stage 1) and docs/model-comparison.md. The default prompt explicitly asks
for inline emphasis (italics/bold) — the axis where Unlimited-OCR fell short and Surya did not.
"""

import argparse
import base64
import json
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "Qwen/Qwen3-VL-8B-Instruct-GGUF"
MODEL_FILE = "Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MMPROJ_FILE = "mmproj-Qwen3VL-8B-Instruct-F16.gguf"
DEFAULT_PROMPT = (
    "Transcribe this scanned book page to clean Markdown. Preserve paragraphs and reading order. "
    "Keep inline emphasis using Markdown: *italic* and **bold**. Do not translate or summarize; "
    "output only the page's text content, no commentary."
)


def page_number(path: Path) -> int:
    """Extract the page number from a name like page_012.png; fall back to 0."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float) -> None:
    """Poll llama-server /health until it returns 200, or raise on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(2)
    raise TimeoutError(f"llama-server did not become healthy within {timeout}s")


def _ocr_page(base_url: str, image_path: Path, prompt: str, max_tokens: int) -> str:
    """POST one page image to the OpenAI-compatible chat endpoint; return the model's text."""
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"]


def _gpu_name() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def run_qwen3vl(
    book: str,
    pages_dir: Path,
    out_root: Path,
    pages_filter: set[int] | None,
    label: str,
    prompt: str,
    n_gpu_layers: int,
    ctx: int,
    max_tokens: int,
) -> dict:
    """Spawn llama-server, OCR each page over its API into a normalized run; return the manifest.

    Raises ValueError if no matching page images are found.
    """
    images_paths = sorted(pages_dir.glob("*.png"), key=page_number)
    if pages_filter is not None:
        images_paths = [p for p in images_paths if page_number(p) in pages_filter]
    if not images_paths:
        raise ValueError(f"No matching page images found in {pages_dir}")

    from huggingface_hub import hf_hub_download

    model_path = hf_hub_download(REPO, MODEL_FILE)
    mmproj_path = hf_hub_download(REPO, MMPROJ_FILE)

    run_id = f"{utc_now()}__qwen3vl__{label}"
    run_dir = out_root / book / "runs" / run_id
    run_pages_dir = run_dir / "pages"
    run_pages_dir.mkdir(parents=True, exist_ok=True)

    binary = shutil.which("llama-server") or "llama-server"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    server_cmd = [
        binary, "-m", model_path, "--mmproj", mmproj_path,
        "-ngl", str(n_gpu_layers), "-c", str(ctx),
        "--host", "127.0.0.1", "--port", str(port),
    ]

    page_numbers = [page_number(p) for p in images_paths]
    per_page_s: dict[str, float] = {}
    started_at = utc_now()
    start = time.time()

    with (run_dir / "llama-server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(server_cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            _wait_for_health(base_url, timeout=300)
            for page_no, src_path in zip(page_numbers, images_paths):
                page_start = time.time()
                text = _ocr_page(base_url, src_path, prompt, max_tokens)
                per_page_s[str(page_no)] = round(time.time() - page_start, 2)

                (run_pages_dir / f"page_{page_no:03d}.md").write_text(text + "\n", encoding="utf-8")
                (run_pages_dir / f"page_{page_no:03d}.json").write_text(
                    json.dumps(
                        {
                            "page": page_no,
                            "source_image": src_path.name,
                            "text": text,
                            "format": "markdown",
                            "blocks": [],  # no grounding from the plain chat API
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    total_s = time.time() - start
    finished_at = utc_now()

    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "model": "qwen3-vl-8b",
        "mode": "instruct_per_page",
        "runtime": "llama-server (GGUF)",
        "prompt": prompt,
        "model_checkpoint": REPO,
        "gguf": {"model_file": MODEL_FILE, "mmproj_file": MMPROJ_FILE},
        "server_cmd": " ".join(str(c) for c in server_cmd),
        "book": book,
        "input_dir": str(pages_dir),
        "pages": page_numbers,
        "device": "cuda",
        "n_gpu_layers": n_gpu_layers,
        "ctx": ctx,
        "gpu": _gpu_name(),
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
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="OCR prompt sent with each page")
    parser.add_argument("--ngl", type=int, default=99, help="GPU layers for llama-server (default: 99 = all)")
    parser.add_argument("--ctx", type=int, default=16384, help="llama-server context size (default: 16384)")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max output tokens per page (default: 4096)")
    args = parser.parse_args()

    pages_dir = args.pages_dir or (args.out_root / args.book / "pages")
    pages_filter = {int(p) for p in args.pages.split(",")} if args.pages else None

    try:
        manifest = run_qwen3vl(
            book=args.book,
            pages_dir=pages_dir,
            out_root=args.out_root,
            pages_filter=pages_filter,
            label=args.label,
            prompt=args.prompt,
            n_gpu_layers=args.ngl,
            ctx=args.ctx,
            max_tokens=args.max_tokens,
        )
    except ValueError as error:
        parser.error(str(error))

    timing = manifest["timing_s"]
    print(f"Run written to {manifest['run_dir']}")
    print(f"  {timing['num_pages']} pages in {timing['total']}s ({timing['avg_per_page']}s/page)")


if __name__ == "__main__":
    main()
