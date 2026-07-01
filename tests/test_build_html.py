from scripts.build_html import (
    canonical_label, classify_boundary, extract_elements,
    stitch_boundary, render_tokens, render_element, build_book_html,
    detect_quote_style, normalize_typography,
)


def _tok(text, label=None, emphasis=None, paragraph_start=False):
    return {'text': text, 'label': label, 'emphasis': emphasis, 'paragraph_start': paragraph_start}


def _page(no, tokens, picture=False):
    return {'page': no, 'voted_tokens': tokens, 'picture_page': picture}


# ---------------------------------------------------------------------------
# canonical_label()
# ---------------------------------------------------------------------------

class TestCanonicalLabel:
    def test_known_mappings(self):
        cases = {
            'Title': 'title', 'SectionHeader': 'heading', 'Text': 'text',
            'Caption': 'caption', 'Picture': 'picture', 'ListItem': 'text',
            'PageHeader': 'page_header', 'PageFooter': 'page_footer',
            'title': 'title', 'text': 'text', 'image': 'picture',
            'header': 'page_header', 'footer': 'page_footer',
        }
        for raw, expected in cases.items():
            assert canonical_label(raw) == expected, raw

    def test_none_falls_back_to_text(self):
        assert canonical_label(None) == 'text'

    def test_unknown_falls_back_to_text(self):
        assert canonical_label('UnknownLabel') == 'text'


# ---------------------------------------------------------------------------
# classify_boundary()
# ---------------------------------------------------------------------------

class TestClassifyBoundary:
    def test_word_split(self):
        assert classify_boundary('weight-', 'less') == 'word_split'
        assert classify_boundary('weight-', 'less,') == 'word_split'  # punc on next word is fine

    def test_not_word_split(self):
        assert classify_boundary('was—', 'or') != 'word_split'   # em-dash is not a hyphen
        assert classify_boundary('weight-', 'Less') != 'word_split'   # uppercase next

    def test_paragraph_continuation(self):
        assert classify_boundary('word', 'next') == 'paragraph_continuation'
        assert classify_boundary('word,', 'he') == 'paragraph_continuation'
        assert classify_boundary('said—', 'or') == 'paragraph_continuation'

    def test_new_paragraph_terminal_punct(self):
        for last in ('word.', 'word!', 'word?', 'said.”'):
            assert classify_boundary(last, 'next') == 'new_paragraph', last
        # terminal punctuation wins even when next word is lowercase
        assert classify_boundary('word.', 'next') == 'new_paragraph'

    def test_new_paragraph_uppercase(self):
        assert classify_boundary('word', 'Next') == 'new_paragraph'

    def test_empty_inputs(self):
        assert classify_boundary('', 'word') == 'new_paragraph'
        assert classify_boundary('word', '') == 'new_paragraph'


# ---------------------------------------------------------------------------
# extract_elements()
# ---------------------------------------------------------------------------

class TestExtractElements:
    def test_single_block(self):
        tokens = [
            _tok('hello', 'Text', paragraph_start=True),
            _tok('world', 'Text'),
        ]
        els = extract_elements(tokens)
        assert len(els) == 1
        assert els[0]['label'] == 'text'
        assert [t['text'] for t in els[0]['tokens']] == ['hello', 'world']

    def test_two_blocks_via_paragraph_start(self):
        tokens = [
            _tok('first', 'Text', paragraph_start=True),
            _tok('second', 'Text', paragraph_start=True),
        ]
        assert len(extract_elements(tokens)) == 2

    def test_label_change_starts_new_element(self):
        tokens = [
            _tok('Chapter', 'Title', paragraph_start=True),
            _tok('body', 'Text', paragraph_start=False),
        ]
        els = extract_elements(tokens)
        assert len(els) == 2
        assert els[0]['label'] == 'title'
        assert els[1]['label'] == 'text'

    def test_skip_labels_excluded(self):
        tokens = [
            _tok('12', 'PageHeader', paragraph_start=True),
            _tok('body', 'Text', paragraph_start=True),
        ]
        els = extract_elements(tokens)
        assert len(els) == 1
        assert els[0]['label'] == 'text'

    def test_empty_tokens(self):
        assert extract_elements([]) == []

    def test_label_normalization_applied(self):
        els = extract_elements([_tok('word', 'SectionHeader', paragraph_start=True)])
        assert els[0]['label'] == 'heading'


# ---------------------------------------------------------------------------
# stitch_boundary()
# ---------------------------------------------------------------------------

def _el(label, *texts):
    tokens = [{'text': t, 'label': None, 'emphasis': None, 'paragraph_start': False} for t in texts]
    return {'label': label, 'tokens': tokens}


class TestStitchBoundary:
    def test_new_paragraph(self):
        result, dec = stitch_boundary([_el('text', 'He', 'said.')], [_el('text', 'She', 'left.')])
        assert len(result) == 2
        assert dec['decision'] == 'new_paragraph'

    def test_paragraph_continuation(self):
        result, dec = stitch_boundary([_el('text', 'he', 'said')], [_el('text', 'nothing', 'at', 'all')])
        assert len(result) == 1
        assert dec['decision'] == 'paragraph_continuation'
        assert [t['text'] for t in result[0]['tokens']] == ['he', 'said', 'nothing', 'at', 'all']

    def test_word_split(self):
        result, dec = stitch_boundary([_el('text', 'weight-')], [_el('text', 'less', 'than', 'air')])
        assert len(result) == 1
        assert dec['decision'] == 'word_split'
        assert result[0]['tokens'][0]['text'] == 'weightless'

    def test_no_stitch_across_headings(self):
        result, dec = stitch_boundary([_el('title', 'Chapter')], [_el('text', 'body', 'text')])
        assert len(result) == 2
        assert dec['decision'] == 'new_paragraph'

    def test_empty_inputs(self):
        assert len(stitch_boundary([], [_el('text', 'word')])[0]) == 1
        assert len(stitch_boundary([_el('text', 'word')], [])[0]) == 1


# ---------------------------------------------------------------------------
# render_tokens()
# ---------------------------------------------------------------------------

class TestRenderTokens:
    def test_plain_and_empty(self):
        assert render_tokens([_tok('hello'), _tok('world')]) == 'hello world'
        assert render_tokens([]) == ''

    def test_emphasis_types(self):
        assert render_tokens([_tok('w', emphasis='italic')]) == '<em>w</em>'
        assert render_tokens([_tok('w', emphasis='bold')]) == '<strong>w</strong>'
        assert render_tokens([_tok('w', emphasis='bold_italic')]) == '<strong><em>w</em></strong>'

    def test_consecutive_same_emphasis_grouped(self):
        tokens = [_tok('very', emphasis='bold'), _tok('important', emphasis='bold')]
        assert render_tokens(tokens) == '<strong>very important</strong>'

    def test_mixed_emphasis(self):
        tokens = [_tok('a'), _tok('b', emphasis='italic'), _tok('c', emphasis='italic'), _tok('d')]
        assert render_tokens(tokens) == 'a <em>b c</em> d'

    def test_html_escaping(self):
        result = render_tokens([_tok('<b>raw</b>')])
        assert '&lt;b&gt;' in result
        assert '<b>' not in result


# ---------------------------------------------------------------------------
# render_element()
# ---------------------------------------------------------------------------

class TestRenderElement:
    def test_label_to_tag(self):
        assert render_element({'label': 'text', 'tokens': [_tok('hello')]}) == '<p>hello</p>'
        assert render_element({'label': 'title', 'tokens': [_tok('Ch')]}) == '<h1>Ch</h1>'
        assert render_element({'label': 'heading', 'tokens': [_tok('Sec')]}) == '<h2>Sec</h2>'


# ---------------------------------------------------------------------------
# detect_quote_style() + normalize_typography()
# ---------------------------------------------------------------------------

def _pg_toks(*texts):
    return {'voted_tokens': [{'text': t} for t in texts], 'picture_page': False}


def _el_from_texts(*texts):
    tokens = [{'text': t, 'emphasis': None, 'paragraph_start': False} for t in texts]
    return {'label': 'text', 'tokens': tokens}


class TestDetectQuoteStyle:
    def test_curly_majority(self):
        pages = [_pg_toks('“Hello”', '“world”')]
        assert detect_quote_style(pages) == 'curly'

    def test_straight_majority(self):
        pages = [_pg_toks('\x22Hello\x22', '\x22world\x22')]
        assert detect_quote_style(pages) == 'straight'

    def test_mixed_curly_wins(self):
        # 4 curly chars vs 2 straight
        pages = [_pg_toks('“A”', '“B”', '\x22C\x22')]
        assert detect_quote_style(pages) == 'curly'

    def test_empty(self):
        assert detect_quote_style([]) == 'straight'


class TestNormalizeTypography:
    def test_straight_double_to_curly(self):
        els = [_el_from_texts('\x22Hello', 'world\x22')]
        result, changed = normalize_typography(els)
        assert result[0]['tokens'][0]['text'] == '“Hello'
        assert result[0]['tokens'][1]['text'] == 'world”'
        assert changed == 2

    def test_open_close_alternation(self):
        els = [_el_from_texts('\x22one\x22', '\x22two\x22')]
        result, _ = normalize_typography(els)
        assert result[0]['tokens'][0]['text'] == '“one”'
        assert result[0]['tokens'][1]['text'] == '“two”'

    def test_apostrophe_mid_word(self):
        els = [_el_from_texts("don\x27t", "it\x27s")]
        result, changed = normalize_typography(els)
        assert result[0]['tokens'][0]['text'] == 'don’t'
        assert result[0]['tokens'][1]['text'] == 'it’s'
        assert changed == 2

    def test_state_carries_across_elements(self):
        els = [_el_from_texts('\x22open'), _el_from_texts('close\x22')]
        result, changed = normalize_typography(els)
        assert result[0]['tokens'][0]['text'] == '“open'
        assert result[1]['tokens'][0]['text'] == 'close”'
        assert changed == 2

    def test_no_change_for_already_curly(self):
        result, changed = normalize_typography([_el_from_texts('“hello”')])
        assert changed == 0

    def test_empty(self):
        result, changed = normalize_typography([])
        assert result == []
        assert changed == 0


# ---------------------------------------------------------------------------
# build_book_html() integration
# ---------------------------------------------------------------------------

class TestBuildBookHtml:
    def test_single_page(self):
        pages = [_page(1, [_tok('hello', 'Text', paragraph_start=True), _tok('world', 'Text')])]
        html, decisions, _ = build_book_html(pages)
        assert '<p>hello world</p>' in html
        assert decisions == []

    def test_stitching_decisions(self):
        pages = [
            _page(1, [_tok('he', 'Text', paragraph_start=True), _tok('said', 'Text')]),
            _page(2, [_tok('nothing', 'Text', paragraph_start=True)]),
        ]
        html, decisions, _ = build_book_html(pages)
        assert '<p>he said nothing</p>' in html
        assert decisions[0]['decision'] == 'paragraph_continuation'

    def test_word_split_across_pages(self):
        pages = [
            _page(1, [_tok('weight-', 'Text', paragraph_start=True)]),
            _page(2, [_tok('less', 'Text', paragraph_start=True), _tok('here', 'Text')]),
        ]
        html, decisions, _ = build_book_html(pages)
        assert 'weightless' in html
        assert decisions[0]['decision'] == 'word_split'

    def test_new_paragraph_across_pages(self):
        pages = [
            _page(1, [_tok('He', 'Text', paragraph_start=True), _tok('said.', 'Text')]),
            _page(2, [_tok('She', 'Text', paragraph_start=True), _tok('left.', 'Text')]),
        ]
        html, decisions, _ = build_book_html(pages)
        assert '<p>He said.</p>' in html
        assert '<p>She left.</p>' in html
        assert decisions[0]['decision'] == 'new_paragraph'

    def test_picture_page_skipped(self):
        pages = [
            _page(1, [_tok('before', 'Text', paragraph_start=True)]),
            _page(2, [], picture=True),
            _page(3, [_tok('after', 'Text', paragraph_start=True)]),
        ]
        html, decisions, _ = build_book_html(pages)
        assert 'before' in html
        assert 'after' in html
        assert decisions[0].get('gap') is True

    def test_heading_followed_by_paragraph(self):
        pages = [_page(1, [
            _tok('Chapter', 'Title', paragraph_start=True),
            _tok('One', 'Title'),
            _tok('Body', 'Text', paragraph_start=True),
            _tok('text', 'Text'),
        ])]
        html, _, __ = build_book_html(pages)
        assert '<h1>Chapter One</h1>' in html
        assert '<p>Body text</p>' in html

    def test_empty_input(self):
        html, decisions, _ = build_book_html([])
        assert html == ''
        assert decisions == []

    def test_typo_normalisation_curly_book(self):
        # 4 curly chars vs 1 straight -> style detected as curly -> straight token normalised
        pages = [_page(1, [
            _tok('“hello”', 'Text', paragraph_start=True),
            _tok('“world”', 'Text'),
            _tok('\x22plain', 'Text'),
        ])]
        _, _, stats = build_book_html(pages)
        assert stats['quote_style'] == 'curly'
        assert stats['typo_tokens_changed'] == 1

    def test_typo_skipped_straight_book(self):
        pages = [_page(1, [_tok('\x22hello\x22', 'Text', paragraph_start=True)])]
        _, _, stats = build_book_html(pages)
        assert stats['quote_style'] == 'straight'
        assert stats['typo_tokens_changed'] == 0
