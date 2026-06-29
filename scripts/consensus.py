#!/usr/bin/env python3
"""Consensus across model runs — alignment-first ROVER voting + a disagreement (entropy) report.

Deterministic, no LLM. For each page it gathers the text from every model's run, normalizes to a
flat word stream, aligns the streams into columns (progressive multiple alignment with gap/NULL
insertion — so a single deletion in one model becomes one gap column, not a frame shift), then per
column votes (ROVER) and measures agreement. Token attributes (layout label, emphasis) are voted
separately, considering only models that provide them. Output: a voted consensus text per page plus
a report of exactly where the models disagree (the localized signal).

Reads the latest *__<suffix> run per model under books/output/<book>/runs/. See docs/brainstorm.md
(Consolidation / consensus).
"""

import argparse
import difflib
import json
import math
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple


# --- token -----------------------------------------------------------------------------------------

class Token(NamedTuple):
    text: str
    label: str | None = None    # layout label (PageHeader/Footer/Text/...) from block structure
    emphasis: bool = False       # italic/bold: Surya <i>/<b> HTML, Qwen3-VL *...* Markdown


# --- normalization ---------------------------------------------------------------------------------

# Text-level rules: regex substitutions applied to raw text before tokenization.
_MARKUP_RULES: list[tuple[str, re.Pattern, str]] = [
    ('md_images',  re.compile(r'!\[[^\]]*\]\([^)]*\)'), ' '),
    ('md_links',   re.compile(r'\[([^\]]*)\]\([^)]*\)'), r'\1'),
    ('html_tags',  re.compile(r'</?[a-zA-Z][^>]*>'), ' '),
    ('md_markers', re.compile(r'[*_`#>]'), ' '),
]


def _dehyphenate(tokens: list[str]) -> list[str]:
    """Merge line-break hyphen splits: ['edu-', 'cational'] -> ['educational']."""
    result: list[str] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i].endswith('-'):
            result.append(tokens[i][:-1] + tokens[i + 1])
            i += 2
        else:
            result.append(tokens[i])
            i += 1
    return result


# Token-level rules: functions on list[str] applied after splitting.
_TOKEN_RULES: list[tuple[str, Callable[[list[str]], list[str]]]] = [
    ('dehyphenate', _dehyphenate),
]


def normalize(text: str) -> list[str]:
    """Strip markup, de-hyphenate line-break splits, and tokenize (original case preserved)."""
    for _, pattern, repl in _MARKUP_RULES:
        text = pattern.sub(repl, text)
    tokens = text.split()
    for _, fn in _TOKEN_RULES:
        tokens = fn(tokens)
    return tokens


# Splits Markdown emphasis spans (*...* or **...**) from plain text.
# re.split with a capture group alternates: [plain0, em1, plain2, em3, ...]
_EMPHASIS_RE = re.compile(r'\*+(.+?)\*+', re.DOTALL)


def normalize_attributed(text: str) -> list[Token]:
    """Tokenize text, detecting *emphasis* spans. No layout label (text-only models)."""
    result: list[Token] = []
    parts = _EMPHASIS_RE.split(text)
    for i, part in enumerate(parts):
        is_em = (i % 2 == 1)
        for t in normalize(part):
            result.append(Token(text=t, emphasis=is_em))
    return result


def normalize_blocks(blocks: list[dict]) -> list[Token]:
    """Tokenize structured blocks (Surya / Unlimited grounding), attaching label and emphasis.

    Label from block 'label' field (PageHeader, Text, etc.). Emphasis detected from 'html' field
    if present (Surya: <i>/<b> tags); Unlimited grounding blocks have no html, so emphasis=False.
    Picture/image blocks are excluded — they carry no text content and belong in the EPUB as raster.
    """
    result: list[Token] = []
    for block in blocks:
        label = block.get('label')
        if label in _PICTURE_LABELS:
            continue
        html = block.get('html', '')
        text = block.get('text', '')
        has_em = bool(re.search(r'<[ib][ >]', html, re.IGNORECASE)) if html else False
        for t in normalize(text):
            result.append(Token(text=t, label=label, emphasis=has_em))
    return result


# --- key canonicalization --------------------------------------------------------------------------
# Applied per token to build the matching key for alignment/voting only; output text is unchanged.

_KEY_TYPOGRAPHY = str.maketrans({
    '‘': "'",   # LEFT SINGLE QUOTATION MARK
    '’': "'",   # RIGHT SINGLE QUOTATION MARK
    '“': '"',   # LEFT DOUBLE QUOTATION MARK
    '”': '"',   # RIGHT DOUBLE QUOTATION MARK
    '—': '-',    # EM DASH
    '–': '-',    # EN DASH
    '…': '...', # HORIZONTAL ELLIPSIS
})


def key(token: str) -> str:
    """Matching key for alignment/voting: typography-, case-, edge-punctuation- and hyphen-insensitive."""
    token = token.translate(_KEY_TYPOGRAPHY)
    token = token.casefold()
    token = token.strip('.,;:!?"\'()-')
    token = token.replace('-', '')
    return token


# --- alignment -------------------------------------------------------------------------------------

def _col_key(col: list[Token | None]) -> str:
    """Representative matching key for a column (majority of its non-empty entries)."""
    keys = [key(t.text) for t in col if t is not None]
    return Counter(keys).most_common(1)[0][0] if keys else ''


def align(seqs: list[list[Token]]) -> list[list[Token | None]]:
    """Progressive multiple-sequence alignment of N token streams.

    Returns a list of columns; each column is a list of length N (Token or None=gap), aligned so
    that homologous tokens share a column. Built incrementally: seq0, then merge each next seq
    against the running alignment's representative tokens via difflib opcodes.
    """
    if not seqs:
        return []
    cols: list[list[Token | None]] = [[t] for t in seqs[0]]
    for m in range(1, len(seqs)):
        ref_keys = [_col_key(c) for c in cols]
        new = seqs[m]
        new_keys = [key(t.text) for t in new]
        matcher = difflib.SequenceMatcher(a=ref_keys, b=new_keys, autojunk=False)
        merged: list[list[Token | None]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for off in range(i2 - i1):
                    cols[i1 + off].append(new[j1 + off])
                    merged.append(cols[i1 + off])
            elif tag == 'delete':
                for off in range(i2 - i1):
                    cols[i1 + off].append(None)
                    merged.append(cols[i1 + off])
            elif tag == 'insert':
                for off in range(j2 - j1):
                    merged.append([None] * m + [new[j1 + off]])
            else:  # replace
                overlap = min(i2 - i1, j2 - j1)
                for off in range(overlap):
                    cols[i1 + off].append(new[j1 + off])
                    merged.append(cols[i1 + off])
                for off in range(overlap, i2 - i1):
                    cols[i1 + off].append(None)
                    merged.append(cols[i1 + off])
                for off in range(overlap, j2 - j1):
                    merged.append([None] * m + [new[j1 + off]])
        cols = merged
    return cols


# --- voting + report -------------------------------------------------------------------------------

def vote_column(col: list[Token | None]) -> tuple[str | None, float, bool, dict]:
    """ROVER vote on one aligned column, including attribute voting.

    Returns (winning token text or None=delete, agreement in [0,1], tie?, attrs dict).
    Label is voted among tokens that carry one (models with block structure).
    Emphasis is majority-voted among all non-gap tokens.
    """
    n = len(col)
    counts = Counter(key(t.text) if t is not None else None for t in col)
    (top_key, top_n), *rest = counts.most_common()
    tie = bool(rest) and rest[0][1] == top_n
    agreement = top_n / n

    labels = [t.label for t in col if t is not None and t.label is not None]
    label_vote = Counter(labels).most_common(1)[0][0] if labels else None

    em_votes = [t.emphasis for t in col if t is not None]
    emphasis_vote = (sum(em_votes) > len(em_votes) / 2) if em_votes else False

    attrs = {'label': label_vote, 'emphasis': emphasis_vote}

    if top_key is None:
        return None, agreement, tie, attrs
    spellings = Counter(t.text for t in col if t is not None and key(t.text) == top_key)
    return spellings.most_common(1)[0][0], agreement, tie, attrs


def entropy(col: list[Token | None]) -> float:
    """Shannon entropy (bits) of the vote distribution over a column."""
    n = len(col)
    counts = Counter(key(t.text) if t is not None else None for t in col)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _seq_for_model(page: dict) -> list[Token]:
    """Build an attributed token sequence from a model's page dict."""
    blocks = page.get('blocks') or []
    if blocks:
        return normalize_blocks(blocks)
    return normalize_attributed(page.get('text', ''))


_HEADER_LABELS = {'PageHeader', 'PageFooter', 'page_number', 'header', 'footer'}
_PICTURE_LABELS = {'Picture', 'image'}  # Surya: 'Picture', Unlimited-OCR grounding: 'image'


def _drop_outlier_seqs(seqs: list[list[Token]], models: list[str]) -> tuple[list[list[Token]], list[str]]:
    """Drop models whose token count exceeds 10x the median by more than 100 tokens.

    Guards against a single model hallucinating thousands of tokens on a blank/decorative page
    while the others correctly produce near-zero output. Only fires when the absolute excess is
    large enough to matter; on normal pages all models produce similar counts so nothing is dropped.
    """
    if len(seqs) < 2:
        return seqs, models
    lengths = [len(s) for s in seqs]
    median = sorted(lengths)[len(lengths) // 2]
    threshold = max(median * 10, median + 100)
    keep = [(s, m) for s, m in zip(seqs, models) if len(s) <= threshold]
    return (([s for s, _ in keep], [m for _, m in keep]) if len(keep) >= 2 else (seqs, models))


def _page_area(page: dict) -> float:
    """Return page area (px²) from image_bbox if available, otherwise from block extents."""
    image_bbox = page.get('image_bbox')
    if image_bbox:
        x0, y0, x1, y1 = image_bbox
        return (x1 - x0) * (y1 - y0)
    blocks = page.get('blocks') or []
    xs = [b['bbox'][2] for b in blocks if 'bbox' in b]
    ys = [b['bbox'][3] for b in blocks if 'bbox' in b]
    return float(max(xs, default=0.0)) * float(max(ys, default=0.0))


def picture_coverage(page: dict) -> float:
    """Fraction of page area covered by picture/image blocks (0–1)."""
    blocks = page.get('blocks') or []
    area = _page_area(page)
    if not area or not blocks:
        return 0.0
    pic = sum(
        (b['bbox'][2] - b['bbox'][0]) * (b['bbox'][3] - b['bbox'][1])
        for b in blocks
        if b.get('label') in _PICTURE_LABELS and 'bbox' in b
    )
    return pic / area


def consense_page(pages: dict[str, dict], picture_threshold: float = 0.4) -> dict:
    """Align + vote one page's per-model data; return consensus text, body text, and disagreements.

    'body_text' is 'consensus_text' with PageHeader/PageFooter tokens removed (postprocess), and
    is empty for picture-dominated pages (max picture coverage >= picture_threshold across models).
    Models whose token count is >10x the median are excluded per-page (hallucination guard).
    """
    models = list(pages)

    # Picture-page gate: classify before alignment; body_text is suppressed for raster pages.
    coverages = {m: picture_coverage(pages[m]) for m in models}
    max_coverage = max(coverages.values()) if coverages else 0.0
    is_picture_page = max_coverage >= picture_threshold

    seqs = [_seq_for_model(pages[m]) for m in models]
    seqs, models = _drop_outlier_seqs(seqs, models)
    cols = align(seqs)

    voted: list[str] = []
    body_tokens: list[str] = []
    disagreements: list[dict] = []
    n_header_cols = 0
    for idx, col in enumerate(cols):
        token, agreement, tie, attrs = vote_column(col)
        is_header = attrs.get('label') in _HEADER_LABELS
        if is_header:
            n_header_cols += 1
        if token is not None:
            voted.append(token)
            if not is_header:
                body_tokens.append(token)
        if agreement < 1.0:
            disagreements.append({
                'col': idx,
                'agreement': round(agreement, 3),
                'entropy': round(entropy(col), 3),
                'tie': tie,
                'winner': token,
                'label': attrs.get('label'),
                'emphasis': attrs.get('emphasis'),
                'variants': {m: (col[i].text if col[i] is not None else None) for i, m in enumerate(models)},
            })
    n_cols = len(cols) or 1
    n_content_cols = len(cols) - n_header_cols
    n_content_dis = sum(1 for d in disagreements if d.get('label') not in _HEADER_LABELS)
    return {
        'models': models,
        'n_columns': len(cols),
        'n_header_columns': n_header_cols,
        'n_content_columns': n_content_cols,
        'n_disagreements': len(disagreements),
        'n_content_disagreements': n_content_dis,
        'agreement_rate': round(1 - len(disagreements) / n_cols, 4),
        'content_agreement_rate': round(1 - n_content_dis / (n_content_cols or 1), 4),
        'consensus_text': ' '.join(voted),
        'body_text': '' if is_picture_page else ' '.join(body_tokens),
        'picture_page': is_picture_page,
        'picture_coverage': round(max_coverage, 4),
        'picture_coverage_per_model': {m: round(coverages[m], 4) for m in coverages},
        'disagreements': disagreements,
    }


# --- run discovery + driver ------------------------------------------------------------------------

def latest_runs(runs_dir: Path, suffix: str) -> dict[str, Path]:
    """Latest run directory per model among runs whose id ends with __<suffix> (run ids sort by time)."""
    by_model: dict[str, Path] = {}
    for run in sorted(runs_dir.glob(f'*__{suffix}')):
        manifest = run / 'manifest.json'
        if manifest.exists():
            by_model[json.loads(manifest.read_text())['model']] = run
    return by_model


def page_data(run: Path, page_no: int) -> dict | None:
    """Return full page dict (text, blocks, format, ...) or None if missing."""
    path = run / 'pages' / f'page_{page_no:03d}.json'
    return json.loads(path.read_text()) if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', required=True, help="Book slug, e.g. 'mindblast'")
    parser.add_argument('--out-root', type=Path, default=Path('books/output'), help='Artifacts root')
    parser.add_argument('--suffix', default='full', help='Run-id suffix/label to consolidate (default: full)')
    parser.add_argument('--pages', help="Optional page filter, e.g. '12,20' (default: all common pages)")
    parser.add_argument('--picture-threshold', type=float, default=0.4,
                        help='Picture coverage fraction (0–1) above which a page is classified as raster (default: 0.4)')
    args = parser.parse_args()

    runs_dir = args.out_root / args.book / 'runs'
    runs = latest_runs(runs_dir, args.suffix)
    if len(runs) < 2:
        parser.error(f"Need >=2 model runs with suffix '{args.suffix}' in {runs_dir}; found {list(runs)}")

    pages = sorted({int(p.stem.split('_')[1]) for run in runs.values() for p in (run / 'pages').glob('page_*.json')})
    if args.pages:
        wanted = {int(p) for p in args.pages.split(',')}
        pages = [p for p in pages if p in wanted]

    out_dir = runs_dir.parent / 'consensus' / f'{args.suffix}'
    (out_dir / 'pages').mkdir(parents=True, exist_ok=True)

    totals_cols = totals_dis = totals_header_cols = totals_content_dis = totals_picture = 0
    for page_no in pages:
        page_datas = {m: d for m, run in runs.items() if (d := page_data(run, page_no)) is not None}
        if len(page_datas) < 2:
            continue
        result = consense_page(page_datas, picture_threshold=args.picture_threshold)
        result['page'] = page_no
        if result.get('picture_page'):
            totals_picture += 1
        (out_dir / 'pages' / f'page_{page_no:03d}.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        (out_dir / 'pages' / f'page_{page_no:03d}.txt').write_text(result['body_text'] + '\n', encoding='utf-8')
        totals_cols += result['n_columns']
        totals_dis += result['n_disagreements']
        totals_header_cols += result['n_header_columns']
        totals_content_dis += result['n_content_disagreements']

    content_cols = totals_cols - totals_header_cols
    summary = {
        'book': args.book,
        'suffix': args.suffix,
        'models': list(runs),
        'runs': {m: r.name for m, r in runs.items()},
        'pages': len(pages),
        'picture_pages': totals_picture,
        'picture_threshold': args.picture_threshold,
        'total_columns': totals_cols,
        'total_disagreements': totals_dis,
        'overall_agreement_rate': round(1 - totals_dis / (totals_cols or 1), 4),
        'header_columns': totals_header_cols,
        'content_columns': content_cols,
        'content_disagreements': totals_content_dis,
        'content_agreement_rate': round(1 - totals_content_dis / (content_cols or 1), 4),
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Consensus written to {out_dir}')
    print(f'  {len(pages)} pages ({totals_picture} picture) | {totals_cols} columns | {totals_dis} disagreements '
          f'| agreement {summary["overall_agreement_rate"]:.3%}'
          f' | content {summary["content_agreement_rate"]:.3%}')


if __name__ == '__main__':
    main()
