#!/usr/bin/env python3
"""Extract specific pages from a scanned PDF as PNG images for OCR/VLM experiments."""

import argparse
from pathlib import Path

import pymupdf


def parse_pages(spec: str) -> list[int]:
    """Parse a spec like "1,5,6,8-10,12" into a sorted list of 1-based page numbers."""
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))
    return sorted(pages)


def extract_pages(pdf_path: Path, page_numbers: list[int], out_dir: Path, dpi: int = 300) -> list[Path]:
    """Render the given 1-based page numbers from pdf_path to PNG files in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72
    matrix = pymupdf.Matrix(zoom, zoom)
    output_paths = []
    with pymupdf.open(pdf_path) as doc:
        for page_number in page_numbers:
            pix = doc[page_number - 1].get_pixmap(matrix=matrix)
            out_path = out_dir / f"page_{page_number:03d}.png"
            pix.save(out_path)
            output_paths.append(out_path)
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path, help="Path to the source PDF")
    parser.add_argument("--pages", required=True, help="Page numbers/ranges, e.g. '1,5,6,8-10,12'")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for the rendered PNGs")
    parser.add_argument("--dpi", type=int, default=300, help="Render resolution in DPI (default: 300)")
    args = parser.parse_args()

    page_numbers = parse_pages(args.pages)
    for path in extract_pages(args.pdf, page_numbers, args.out, args.dpi):
        print(path)


if __name__ == "__main__":
    main()
