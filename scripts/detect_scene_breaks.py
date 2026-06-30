#!/usr/bin/env python3
"""Detect scene-break dividers in a book's consensus pages.

Post-processing step on consensus output. Reads voted_blocks_surya and voted_blocks_unlimited
from consensus page JSONs, performs book-level gap calibration, and classifies large inter-paragraph
gaps as scene breaks. Outputs scene_breaks.json (consumed by build_html.py) and
scene_breaks_diagnostic.json (full per-model comparison for manual review).

Design and all rejected alternatives: docs/brainstorm-scene-break.md, GitHub issue #22.

Usage:
    python scripts/detect_scene_breaks.py --book mindblast [--suffix full]
"""

import argparse
import json
import re
import statistics
from pathlib import Path


# ── constants ────────────────────────────────────────────────────────────────

_HEADER_LABELS = {'PageHeader', 'PageFooter', 'page_number', 'header', 'footer'}
_PICTURE_LABELS = {'Picture', 'image'}
_TITLE_LABELS = {'Title', 'SectionHeader', 'title', 'heading'}

# Geometry thresholds (normalised [0, 1]).
# Derived from mindblast data: ornament w ≈ 4.4%, h ≈ 2.7% of page.
# ×3 headroom → 0.15. See docs/brainstorm-scene-break.md §4 Phase 2.
_ORNAMENT_MAX_SIZE = 0.15
_ORNAMENT_MAX_OFFSET = 0.15     # |cx − 0.5| < this

# Robust gap threshold: Q3 + k×IQR (see §4 Phase 0, IQR-robustness argument).
_IQR_K = 3.0

# Separability: large-gap cluster must be this far above threshold to be "high confidence".
_SEPARABILITY_RATIO = 1.5

# Minimum ornament cluster size for confirmed classification.
_MIN_CLUSTER = 3

# x-offset IQR multiplier for paragraph-block threshold.
_X_IQR_K = 3.0

# Cross-model y-overlap tolerance for matching gap candidates.
_Y_MATCH_TOL = 0.05

# Separator text: a block whose entire token content is only these characters.
_SEPARATOR_RE = re.compile(r'^[\*\•\-\—\#\s]+$')


# ── geometry helpers ─────────────────────────────────────────────────────────

def _iqr_threshold(values: list[float], k: float) -> float:
    """Return Q3 + k*IQR as a robust upper-tail threshold."""
    if not values:
        return float('inf')
    s = sorted(values)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    iqr = q3 - q1
    return q3 + k * iqr


def _is_paragraph_block(block: dict, x_threshold: float) -> bool:
    label = block.get('label', '')
    if label in _HEADER_LABELS or label in _PICTURE_LABELS or label in _TITLE_LABELS:
        return False
    bbox = block.get('bbox')
    return bool(bbox and bbox[0] < x_threshold)


def _is_small_centered(block: dict) -> bool:
    """True if block is small and horizontally centred — candidate visual ornament."""
    bbox = block.get('bbox')
    if not bbox:
        return False
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    return w < _ORNAMENT_MAX_SIZE and h < _ORNAMENT_MAX_SIZE and abs(cx - 0.5) < _ORNAMENT_MAX_OFFSET


# ── phase 0: book-level calibration ─────────────────────────────────────────

def calibrate(page_results: list[dict]) -> dict:
    """Compute x_threshold and gap_threshold from all non-picture pages.

    Returns a dict with thresholds and separability info for both models.
    See docs/brainstorm-scene-break.md §4 Phase 0.
    """
    all_x: list[float] = []
    all_gaps: list[float] = []

    for page in page_results:
        if page.get('picture_page'):
            continue
        for key in ('voted_blocks_surya', 'voted_blocks_unlimited'):
            blocks = page.get(key) or []
            for b in blocks:
                bbox = b.get('bbox')
                if bbox:
                    all_x.append(bbox[0])

    x_threshold = _iqr_threshold(all_x, _X_IQR_K) if all_x else 0.5

    # Collect gaps between consecutive paragraph blocks on the same page.
    for page in page_results:
        if page.get('picture_page'):
            continue
        for key in ('voted_blocks_surya', 'voted_blocks_unlimited'):
            blocks = page.get(key) or []
            para = [b for b in blocks if _is_paragraph_block(b, x_threshold)]
            para.sort(key=lambda b: b['bbox'][1])  # sort by y0
            for i in range(1, len(para)):
                gap = para[i]['bbox'][1] - para[i - 1]['bbox'][3]
                if gap > 0:
                    all_gaps.append(gap)

    gap_threshold = _iqr_threshold(all_gaps, _IQR_K) if all_gaps else float('inf')
    large_gaps = [g for g in all_gaps if g > gap_threshold]

    separable = False
    if large_gaps:
        separable = min(large_gaps) > gap_threshold * _SEPARABILITY_RATIO

    return {
        'x_threshold': round(x_threshold, 4),
        'gap_threshold': round(gap_threshold, 4),
        'n_gaps_total': len(all_gaps),
        'n_gaps_large': len(large_gaps),
        'separable': separable,
        'gap_median': round(statistics.median(all_gaps), 4) if all_gaps else None,
    }


# ── phase 1+2: per-page candidate extraction and classification ──────────────

def _classify_zone(zone_blocks: list[dict]) -> tuple[str, str]:
    """Classify the contents of a gap zone.

    Returns (classification, subtype):
      ('scene_break', 'blank')       — nothing in the zone
      ('scene_break', 'ornament')    — small centred picture or mislabelled title
      ('scene_break', 'typographic') — small centred text (content check in build_html.py)
      ('chapter_boundary', '')       — large/non-centred title/heading block
      ('unknown', '')                — anything else

    Note: Unlimited-OCR sometimes labels small centred ornaments as 'title' instead of 'image'.
    A title/heading block that is also small+centred is treated as an ornament, not a chapter
    boundary. Real chapter headings span most of the text width and are not centred at 50%.
    """
    if not zone_blocks:
        return 'scene_break', 'blank'

    for block in zone_blocks:
        label = block.get('label', '')
        if label in _PICTURE_LABELS:
            if _is_small_centered(block):
                return 'scene_break', 'ornament'
            return 'unknown', ''
        if label in _TITLE_LABELS:
            # Small+centred title → Unlimited mislabelled the ornament; treat as ornament.
            if _is_small_centered(block):
                return 'scene_break', 'ornament'
            return 'chapter_boundary', ''
        if label not in _HEADER_LABELS and _is_small_centered(block):
            # Small centred text block — likely typographic separator (* * *).
            # Actual content check is done in build_html.py via voted_tokens.
            return 'scene_break', 'typographic'

    return 'unknown', ''


def find_candidates(page: dict, x_threshold: float, gap_threshold: float, model_key: str) -> list[dict]:
    """Find gap candidates for one model on one page."""
    blocks = page.get(f'voted_blocks_{model_key}') or []
    para = [b for b in blocks if _is_paragraph_block(b, x_threshold)]
    para.sort(key=lambda b: b['bbox'][1])

    candidates = []
    for i in range(1, len(para)):
        y_top = para[i - 1]['bbox'][3]
        y_bot = para[i]['bbox'][1]
        gap = y_bot - y_top
        if gap <= gap_threshold:
            continue
        # Collect decoration blocks whose y-range falls inside the gap zone.
        zone_blocks = [
            b for b in blocks
            if not _is_paragraph_block(b, x_threshold)
            and b.get('bbox') and b['bbox'][1] >= y_top and b['bbox'][3] <= y_bot
        ]
        classification, subtype = _classify_zone(zone_blocks)
        candidates.append({
            'y_top': round(y_top, 4),
            'y_bot': round(y_bot, 4),
            'gap': round(gap, 4),
            'classification': classification,
            'subtype': subtype,
        })
    return candidates


# ── cross-model merging ───────────────────────────────────────────────────────

def _intervals_overlap(a_top: float, a_bot: float, b_top: float, b_bot: float, tol: float) -> bool:
    return a_top - tol <= b_bot and b_top - tol <= a_bot


def merge_candidates(
    page_no: int,
    surya_cands: list[dict],
    unlimited_cands: list[dict],
) -> list[dict]:
    """Merge per-model candidates for one page by y-overlap.

    Returns merged entries with confidence: 'high' (both agree) or 'low' (one only).
    """
    merged: list[dict] = []
    used_unlimited: set[int] = set()

    for sc in surya_cands:
        matched = None
        for j, uc in enumerate(unlimited_cands):
            if j in used_unlimited:
                continue
            if _intervals_overlap(sc['y_top'], sc['y_bot'], uc['y_top'], uc['y_bot'], _Y_MATCH_TOL):
                matched = j
                break

        if matched is not None:
            uc = unlimited_cands[matched]
            used_unlimited.add(matched)
            # Prefer scene_break classification over unknown; surya takes precedence on tie.
            classification = sc['classification'] if sc['classification'] != 'unknown' else uc['classification']
            subtype = sc['subtype'] if sc['subtype'] else uc['subtype']
            merged.append({
                'page': page_no,
                'y_top': round((sc['y_top'] + uc['y_top']) / 2, 4),
                'y_bot': round((sc['y_bot'] + uc['y_bot']) / 2, 4),
                'classification': classification,
                'subtype': subtype,
                'confidence': 'high',
                'surya': True,
                'unlimited': True,
            })
        else:
            merged.append({
                'page': page_no,
                'y_top': sc['y_top'],
                'y_bot': sc['y_bot'],
                'classification': sc['classification'],
                'subtype': sc['subtype'],
                'confidence': 'low',
                'surya': True,
                'unlimited': False,
            })

    for j, uc in enumerate(unlimited_cands):
        if j not in used_unlimited:
            merged.append({
                'page': page_no,
                'y_top': uc['y_top'],
                'y_bot': uc['y_bot'],
                'classification': uc['classification'],
                'subtype': uc['subtype'],
                'confidence': 'low',
                'surya': False,
                'unlimited': True,
            })

    merged.sort(key=lambda e: e['y_top'])
    return merged


# ── phase 3: book-level validation ───────────────────────────────────────────

def validate(all_entries: list[dict]) -> list[dict]:
    """Book-level validation passes.

    1. Ornament cluster size: if < _MIN_CLUSTER ornaments found, downgrade to low confidence.
    2. Blank suppression: if the book uses ornaments as scene-break markers, blank gaps are
       ambiguous (quoted letters, epigraphs, layout indentation — see issue #37) and are
       suppressed. If the book has no ornaments at all, blank gaps are the only available
       signal and are kept. See docs/brainstorm-scene-break.md §4 Phase 3.
    """
    ornament_count = sum(
        1 for e in all_entries
        if e.get('classification') == 'scene_break' and e.get('subtype') == 'ornament'
    )
    if 0 < ornament_count < _MIN_CLUSTER:
        for e in all_entries:
            if e.get('subtype') == 'ornament' and e.get('confidence') == 'high':
                e['confidence'] = 'low'
                e['validation_note'] = f'only {ornament_count} ornament(s) found (< {_MIN_CLUSTER})'

    if ornament_count > 0:
        for e in all_entries:
            if e.get('subtype') == 'blank' and e.get('classification') == 'scene_break':
                e['classification'] = 'unknown'
                e['validation_note'] = 'suppressed: book uses ornaments; blank gaps are ambiguous (see issue #37)'

    return all_entries


# ── main ─────────────────────────────────────────────────────────────────────

def detect_scene_breaks(consensus_dir: Path) -> tuple[list[dict], list[dict], dict]:
    """Run full detection pipeline on a consensus directory.

    Returns (scene_breaks, diagnostic_entries, calibration_info).
    """
    pages_dir = consensus_dir / 'pages'
    page_results = sorted(
        [json.loads(p.read_text(encoding='utf-8')) for p in pages_dir.glob('page_*.json')],
        key=lambda d: d.get('page', 0),
    )

    cal = calibrate(page_results)

    all_entries: list[dict] = []
    for page in page_results:
        if page.get('picture_page'):
            continue
        page_no = page['page']
        surya_cands = find_candidates(page, cal['x_threshold'], cal['gap_threshold'], 'surya')
        unlimited_cands = find_candidates(page, cal['x_threshold'], cal['gap_threshold'], 'unlimited')
        entries = merge_candidates(page_no, surya_cands, unlimited_cands)
        all_entries.extend(entries)

    all_entries = validate(all_entries)

    scene_breaks = [e for e in all_entries if e.get('classification') == 'scene_break']
    return scene_breaks, all_entries, cal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', required=True, help="Book slug, e.g. 'mindblast'")
    parser.add_argument('--out-root', type=Path, default=Path('books/output'))
    parser.add_argument('--suffix', default='full', help='Consensus run suffix (default: full)')
    args = parser.parse_args()

    consensus_dir = args.out_root / args.book / 'consensus' / args.suffix
    if not (consensus_dir / 'pages').exists():
        parser.error(f'Consensus pages not found: {consensus_dir / "pages"}')

    scene_breaks, diagnostic, cal = detect_scene_breaks(consensus_dir)

    (consensus_dir / 'scene_breaks.json').write_text(
        json.dumps(scene_breaks, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (consensus_dir / 'scene_breaks_diagnostic.json').write_text(
        json.dumps({'calibration': cal, 'entries': diagnostic}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    n_high = sum(1 for e in scene_breaks if e['confidence'] == 'high')
    n_low = sum(1 for e in scene_breaks if e['confidence'] == 'low')
    n_chapter = sum(1 for e in diagnostic if e.get('classification') == 'chapter_boundary')
    n_unknown = sum(1 for e in diagnostic if e.get('classification') == 'unknown')
    print(f'Calibration: gap_threshold={cal["gap_threshold"]:.4f}  separable={cal["separable"]}')
    print(f'Scene breaks: {len(scene_breaks)} total  ({n_high} high, {n_low} low confidence)')
    if n_chapter:
        print(f'Chapter boundaries: {n_chapter}')
    if n_unknown:
        print(f'Unknown / flagged for review: {n_unknown}')
    print(f'Written to {consensus_dir}')


if __name__ == '__main__':
    main()
