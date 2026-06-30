#!/usr/bin/env python3
"""Assemble per-page HTML fragments from consensus voted_tokens into a single book.html.

Reads voted_tokens from consensus pages (books/output/<book>/consensus/<suffix>/pages/),
normalizes layout labels (Surya/Unlimited → canonical), groups tokens into HTML elements
(paragraphs, headings, etc.), wraps emphasis spans, applies cross-page stitching at paragraph
boundaries, and emits book.html ready for Pandoc → EPUB3 conversion.

Design: docs/brainstorm.md § Layer 4 (EPUB assembly via Pandoc, HTML canonical).
Part of issue #30 (enriched voted_tokens + HTML assembler).

Cross-page stitching (issue #20), typography normalization (#21), and scene-break detection (#22)
will be wired in here as this script matures.
"""

import argparse
import html as html_module
import json
import re
from pathlib import Path

_SEPARATOR_RE = re.compile(r'^[\*\•\-\—\#\s]+$')

# ---------------------------------------------------------------------------
# Label normalization — both Surya and Unlimited grounding labels → canonical
# ---------------------------------------------------------------------------

_LABEL_CANONICAL: dict[str | None, str] = {
    # Surya
    'Title': 'title',
    'SectionHeader': 'heading',
    'Text': 'text',
    'Caption': 'caption',
    'PageHeader': 'page_header',
    'PageFooter': 'page_footer',
    'Picture': 'picture',
    'ListItem': 'text',
    'Footnote': 'footnote',
    # Unlimited grounding
    'title': 'title',
    'text': 'text',
    'image': 'picture',
    'header': 'page_header',
    'footer': 'page_footer',
    'caption': 'caption',
    # Fallback
    None: 'text',
}

_SKIP_LABELS = {'page_header', 'page_footer'}

_LABEL_TO_TAG: dict[str, str] = {
    'title': 'h1',
    'heading': 'h2',
    'text': 'p',
    'caption': 'figcaption',
    'footnote': 'p',  # footnotes as plain paragraphs for now
}

# Characters that mark a definite sentence/paragraph end when last on a page.
_TERMINAL = frozenset('.!?"' + '”’')  # . ! ? "  +  curly " '


def canonical_label(raw: str | None) -> str:
    """Map a raw model label to a canonical label string."""
    return _LABEL_CANONICAL.get(raw, 'text')


# ---------------------------------------------------------------------------
# Cross-page boundary classification (issue #20)
# ---------------------------------------------------------------------------

def classify_boundary(last_word: str, first_word: str) -> str:
    """Classify a cross-page boundary as 'word_split', 'paragraph_continuation', or 'new_paragraph'.

    Design: docs/brainstorm.md § "Resolving the tension — stitching as a deterministic post-process".
    """
    if not last_word or not first_word:
        return 'new_paragraph'
    # Word split: ASCII hyphen at end (U+002D, not em-dash U+2014) + lowercase start on next page
    if last_word[-1] == '-' and first_word[:1].islower():
        return 'word_split'
    # Paragraph continuation: no terminal punctuation + lowercase start
    if last_word[-1] not in _TERMINAL and first_word[:1].islower():
        return 'paragraph_continuation'
    return 'new_paragraph'


# ---------------------------------------------------------------------------
# Element extraction — voted_tokens → list of elements
# ---------------------------------------------------------------------------

def extract_elements(voted_tokens: list[dict]) -> list[dict]:
    """Group a page's voted_tokens into element dicts ({label, tokens}).

    A new element starts when paragraph_start=True or the label changes.
    Tokens with skip labels (page_header/footer) are excluded.
    """
    elements: list[dict] = []
    current_label: str | None = None
    current_tokens: list[dict] = []

    for tok in voted_tokens:
        clabel = canonical_label(tok.get('label'))
        if clabel in _SKIP_LABELS:
            continue
        new_element = tok.get('paragraph_start', False) or (current_label is not None and clabel != current_label)
        if new_element and current_tokens:
            elements.append({'label': current_label or 'text', 'tokens': current_tokens})
            current_tokens = []
        current_label = clabel
        current_tokens.append(tok)

    if current_tokens:
        elements.append({'label': current_label or 'text', 'tokens': current_tokens})

    return elements


# ---------------------------------------------------------------------------
# Cross-page stitching of element lists
# ---------------------------------------------------------------------------

def stitch_boundary(prev_elements: list[dict], next_elements: list[dict]) -> tuple[list[dict], dict]:
    """Potentially merge the last element of prev_elements with the first of next_elements.

    Returns (merged element list, decision dict).
    Stitching only applies when both boundary elements are 'text' paragraphs (not headings/
    captions), and page numbers are consecutive (caller must gate on non-consecutive page gaps).
    """
    decision: dict = {'decision': 'new_paragraph', 'last_word': '', 'first_word': ''}

    if not prev_elements or not next_elements:
        return prev_elements + next_elements, decision

    last_el = prev_elements[-1]
    first_el = next_elements[0]

    # Only stitch plain text paragraphs
    if last_el['label'] != 'text' or first_el['label'] != 'text':
        return prev_elements + next_elements, decision

    last_word = last_el['tokens'][-1]['text'] if last_el['tokens'] else ''
    first_word = first_el['tokens'][0]['text'] if first_el['tokens'] else ''
    boundary = classify_boundary(last_word, first_word)
    decision = {'decision': boundary, 'last_word': last_word, 'first_word': first_word}

    if boundary == 'new_paragraph':
        return prev_elements + next_elements, decision

    if boundary == 'word_split':
        # Strip trailing hyphen from last token of prev, join to first token of next
        joined_text = last_word[:-1] + first_word
        new_last_tok = {**last_el['tokens'][-1], 'text': joined_text}
        merged_tokens = last_el['tokens'][:-1] + [new_last_tok] + first_el['tokens'][1:]
    else:  # paragraph_continuation
        merged_tokens = last_el['tokens'] + first_el['tokens']

    merged = {'label': 'text', 'tokens': merged_tokens}
    return prev_elements[:-1] + [merged] + next_elements[1:], decision


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _wrap_emphasis(em: str | None, text: str) -> str:
    if em == 'italic':
        return f'<em>{text}</em>'
    if em == 'bold':
        return f'<strong>{text}</strong>'
    if em == 'bold_italic':
        return f'<strong><em>{text}</em></strong>'
    return text


def render_tokens(tokens: list[dict]) -> str:
    """Render a token list to inner HTML, grouping consecutive same-emphasis tokens into spans."""
    if not tokens:
        return ''
    groups: list[tuple[str | None, list[str]]] = []
    current_em = tokens[0].get('emphasis')
    current_words = [html_module.escape(tokens[0]['text'])]
    for tok in tokens[1:]:
        em = tok.get('emphasis')
        word = html_module.escape(tok['text'])
        if em == current_em:
            current_words.append(word)
        else:
            groups.append((current_em, current_words))
            current_em = em
            current_words = [word]
    groups.append((current_em, current_words))
    return ' '.join(_wrap_emphasis(em, ' '.join(words)) for em, words in groups)


def _is_separator_element(tokens: list[dict]) -> bool:
    """True if all tokens in the element consist only of typographic separator characters.

    Handles the '* * *' / '***' / '• • •' scene-break variant in plain text.
    See docs/brainstorm-scene-break.md §2 (typographic form).
    """
    text = ' '.join(t.get('text', '') for t in tokens).strip()
    return bool(text and _SEPARATOR_RE.match(text))


def render_element(element: dict) -> str:
    """Render one element dict to an HTML string."""
    label = element['label']
    tokens = element['tokens']

    if label == 'hr':
        return '<hr>'

    # Typographic scene break: '* * *' / '***' / '• • •' etc.
    if label == 'text' and _is_separator_element(tokens):
        return '<hr>'

    if label == 'picture':
        return '<!-- picture: illustration -->'

    tag = _LABEL_TO_TAG.get(label, 'p')
    inner = render_tokens(tokens)
    return f'<{tag}>{inner}</{tag}>'


# ---------------------------------------------------------------------------
# Scene-break insertion
# ---------------------------------------------------------------------------

# Labels excluded when counting paragraph blocks for scene-break position mapping.
_PARA_SKIP_LABELS = {
    'PageHeader', 'PageFooter', 'page_number', 'header', 'footer',
    'Picture', 'image', 'Title', 'SectionHeader', 'title', 'heading',
}
# Blocks with x0 > this threshold are centred/decorative, not paragraph text.
_X_THRESHOLD = 0.25


def _para_blocks_before(voted_blocks: list[dict], y_top: float) -> int:
    """Count left-aligned paragraph blocks whose centre is above y_top.

    Uses block centre rather than y_bot to handle the common case where Surya's
    last paragraph block slightly overlaps the ornament's top edge.
    """
    return sum(
        1 for b in voted_blocks
        if b.get('bbox')
        and b.get('label') not in _PARA_SKIP_LABELS
        and b['bbox'][0] < _X_THRESHOLD
        and (b['bbox'][1] + b['bbox'][3]) / 2 < y_top
    )


def _insert_scene_breaks(elements: list[dict], breaks: list[dict], page_data: dict) -> list[dict]:
    """Insert {'label': 'hr', 'tokens': []} markers at scene-break positions.

    Uses voted_blocks_surya geometry to map each break's y_top to a paragraph
    index, then inserts the marker after that paragraph in the element list.
    Ornament Picture blocks carry no text tokens and never appear in elements,
    so spatial mapping via voted_blocks is the only way to find the right position.
    See docs/brainstorm-scene-break.md §6 (pipeline integration).
    """
    if not breaks:
        return elements

    blocks = page_data.get('voted_blocks_surya') or page_data.get('voted_blocks_unlimited') or []
    text_indices = [i for i, el in enumerate(elements) if el['label'] == 'text']

    inserts: list[tuple[int, dict]] = []
    for brk in breaks:
        n_before = _para_blocks_before(blocks, brk['y_top'])
        if n_before == 0:
            pos = 0
        elif n_before >= len(text_indices):
            pos = len(elements)
        else:
            pos = text_indices[n_before - 1] + 1
        inserts.append((pos, {'label': 'hr', 'tokens': []}))

    result = list(elements)
    for pos, el in sorted(inserts, key=lambda x: x[0], reverse=True):
        result.insert(pos, el)
    return result


# ---------------------------------------------------------------------------
# Book-level assembly
# ---------------------------------------------------------------------------

def build_book_html(
    page_results: list[dict],
    scene_breaks: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """Convert ordered page results (from consensus) to a full book HTML string.

    scene_breaks: list of scene-break entries from scene_breaks.json (produced by
    detect_scene_breaks.py). Each entry has 'page', 'y_top', 'y_bot', 'classification'.
    If provided, <hr> markers are inserted at the correct intra-page positions using
    voted_blocks_surya geometry. If None, no scene breaks are emitted.

    Returns (html_string, list_of_stitching_decisions).
    Each decision: {from_page, to_page, last_word, first_word, decision, gap?}.
    """
    text_pages = [
        p for p in sorted(page_results, key=lambda x: x['page'])
        if not p.get('picture_page') and p.get('voted_tokens')
    ]
    if not text_pages:
        return '', []

    breaks_by_page: dict[int, list[dict]] = {}
    for e in (scene_breaks or []):
        if e.get('classification') == 'scene_break':
            breaks_by_page.setdefault(e['page'], []).append(e)

    all_decisions: list[dict] = []
    first_page = text_pages[0]
    all_elements = _insert_scene_breaks(
        extract_elements(first_page.get('voted_tokens', [])),
        breaks_by_page.get(first_page['page'], []),
        first_page,
    )

    for i in range(1, len(text_pages)):
        prev = text_pages[i - 1]
        curr = text_pages[i]
        next_elements = _insert_scene_breaks(
            extract_elements(curr.get('voted_tokens', [])),
            breaks_by_page.get(curr['page'], []),
            curr,
        )

        gap = curr['page'] - prev['page'] > 1
        if gap:
            all_decisions.append({
                'from_page': prev['page'], 'to_page': curr['page'],
                'decision': 'new_paragraph', 'gap': True, 'last_word': '', 'first_word': '',
            })
            all_elements = all_elements + next_elements
        else:
            all_elements, decision = stitch_boundary(all_elements, next_elements)
            all_decisions.append({'from_page': prev['page'], 'to_page': curr['page'], **decision})

    html_parts = [render_element(el) for el in all_elements]
    return '\n'.join(html_parts), all_decisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book', required=True, help="Book slug, e.g. 'mindblast'")
    parser.add_argument('--out-root', type=Path, default=Path('books/output'))
    parser.add_argument('--suffix', default='full', help='Consensus run suffix (default: full)')
    args = parser.parse_args()

    consensus_dir = args.out_root / args.book / 'consensus' / args.suffix
    pages_dir = consensus_dir / 'pages'
    if not pages_dir.exists():
        parser.error(f'Consensus pages not found: {pages_dir}')

    page_results = [
        json.loads(p.read_text(encoding='utf-8'))
        for p in sorted(pages_dir.glob('page_*.json'))
    ]
    if not page_results:
        parser.error(f'No page_*.json files found in {pages_dir}')

    # Load scene breaks if available (produced by detect_scene_breaks.py).
    scene_breaks_path = consensus_dir / 'scene_breaks.json'
    scene_breaks: list[dict] | None = None
    if scene_breaks_path.exists():
        scene_breaks = json.loads(scene_breaks_path.read_text(encoding='utf-8'))
        n_pages = len({e['page'] for e in scene_breaks if e.get('classification') == 'scene_break'})
        print(f'Loaded {len(scene_breaks)} scene break(s) on {n_pages} page(s) from {scene_breaks_path.name}')

    book_html, decisions = build_book_html(page_results, scene_breaks=scene_breaks)

    (consensus_dir / 'book.html').write_text(book_html + '\n', encoding='utf-8')
    (consensus_dir / 'stitching_decisions.json').write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    n_word = sum(1 for d in decisions if d['decision'] == 'word_split')
    n_cont = sum(1 for d in decisions if d['decision'] == 'paragraph_continuation')
    n_para = sum(1 for d in decisions if d['decision'] == 'new_paragraph')
    print(f'Built {consensus_dir / "book.html"} from {len(page_results)} pages')
    print(f'  word_split: {n_word}  paragraph_continuation: {n_cont}  new_paragraph: {n_para}')


if __name__ == '__main__':
    main()
