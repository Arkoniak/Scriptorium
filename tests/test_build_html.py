from scripts.build_html import (
    canonical_label, classify_boundary, extract_elements,
    stitch_boundary, render_tokens, render_element, build_book_html,
)


def _tok(text, label=None, emphasis=None, paragraph_start=False):
    return {'text': text, 'label': label, 'emphasis': emphasis, 'paragraph_start': paragraph_start}


def _page(no, tokens, picture=False):
    return {'page': no, 'voted_tokens': tokens, 'picture_page': picture}


# ---------------------------------------------------------------------------
# canonical_label()
# ---------------------------------------------------------------------------

class TestCanonicalLabel:
    def test_surya_title(self):
        assert canonical_label('Title') == 'title'

    def test_surya_section_header(self):
        assert canonical_label('SectionHeader') == 'heading'

    def test_surya_text(self):
        assert canonical_label('Text') == 'text'

    def test_unlimited_title(self):
        assert canonical_label('title') == 'title'

    def test_unlimited_text(self):
        assert canonical_label('text') == 'text'

    def test_picture_labels(self):
        assert canonical_label('Picture') == 'picture'
        assert canonical_label('image') == 'picture'

    def test_header_footer(self):
        assert canonical_label('PageHeader') == 'page_header'
        assert canonical_label('PageFooter') == 'page_footer'
        assert canonical_label('header') == 'page_header'
        assert canonical_label('footer') == 'page_footer'

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

    def test_word_split_with_punctuation_first_word(self):
        assert classify_boundary('weight-', 'less,') == 'word_split'

    def test_em_dash_not_word_split(self):
        # em-dash (U+2014) is not an ASCII hyphen
        assert classify_boundary('was—', 'or') != 'word_split'

    def test_uppercase_next_not_word_split(self):
        assert classify_boundary('weight-', 'Less') != 'word_split'

    def test_paragraph_continuation(self):
        assert classify_boundary('word', 'next') == 'paragraph_continuation'

    def test_comma_is_continuation(self):
        assert classify_boundary('word,', 'he') == 'paragraph_continuation'

    def test_em_dash_end_is_continuation(self):
        # em-dash at end of word: not terminal, lowercase next → continuation
        assert classify_boundary('said—', 'or') == 'paragraph_continuation'

    def test_new_paragraph_period(self):
        assert classify_boundary('word.', 'Next') == 'new_paragraph'

    def test_new_paragraph_period_lowercase(self):
        # terminal punct wins even if next word is lowercase
        assert classify_boundary('word.', 'next') == 'new_paragraph'

    def test_new_paragraph_uppercase(self):
        assert classify_boundary('word', 'Next') == 'new_paragraph'

    def test_new_paragraph_exclamation(self):
        assert classify_boundary('word!', 'next') == 'new_paragraph'

    def test_new_paragraph_question(self):
        assert classify_boundary('word?', 'next') == 'new_paragraph'

    def test_new_paragraph_closing_quote(self):
        assert classify_boundary('said."', 'next') == 'new_paragraph'

    def test_empty_last_word(self):
        assert classify_boundary('', 'word') == 'new_paragraph'

    def test_empty_first_word(self):
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
        els = extract_elements(tokens)
        assert len(els) == 2

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
        tokens = [_tok('word', 'SectionHeader', paragraph_start=True)]
        els = extract_elements(tokens)
        assert els[0]['label'] == 'heading'


# ---------------------------------------------------------------------------
# stitch_boundary()
# ---------------------------------------------------------------------------

def _el(label, *texts):
    """Helper: make a simple element with plain tokens."""
    tokens = [{'text': t, 'label': None, 'emphasis': None, 'paragraph_start': False} for t in texts]
    return {'label': label, 'tokens': tokens}


class TestStitchBoundary:
    def test_new_paragraph(self):
        prev = [_el('text', 'He', 'said.')]
        nxt = [_el('text', 'She', 'left.')]
        result, dec = stitch_boundary(prev, nxt)
        assert len(result) == 2
        assert dec['decision'] == 'new_paragraph'

    def test_paragraph_continuation(self):
        prev = [_el('text', 'he', 'said')]
        nxt = [_el('text', 'nothing', 'at', 'all')]
        result, dec = stitch_boundary(prev, nxt)
        assert len(result) == 1
        assert dec['decision'] == 'paragraph_continuation'
        texts = [t['text'] for t in result[0]['tokens']]
        assert texts == ['he', 'said', 'nothing', 'at', 'all']

    def test_word_split(self):
        prev = [_el('text', 'weight-')]
        nxt = [_el('text', 'less', 'than', 'air')]
        result, dec = stitch_boundary(prev, nxt)
        assert len(result) == 1
        assert dec['decision'] == 'word_split'
        assert result[0]['tokens'][0]['text'] == 'weightless'

    def test_no_stitch_across_headings(self):
        prev = [_el('title', 'Chapter')]
        nxt = [_el('text', 'body', 'text')]
        result, dec = stitch_boundary(prev, nxt)
        assert len(result) == 2
        assert dec['decision'] == 'new_paragraph'

    def test_empty_prev(self):
        nxt = [_el('text', 'word')]
        result, _ = stitch_boundary([], nxt)
        assert len(result) == 1

    def test_empty_next(self):
        prev = [_el('text', 'word')]
        result, _ = stitch_boundary(prev, [])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# render_tokens()
# ---------------------------------------------------------------------------

class TestRenderTokens:
    def test_plain_tokens(self):
        tokens = [_tok('hello'), _tok('world')]
        assert render_tokens(tokens) == 'hello world'

    def test_italic_span(self):
        tokens = [_tok('say'), _tok('hello', emphasis='italic'), _tok('now')]
        result = render_tokens(tokens)
        assert '<em>hello</em>' in result
        assert result == 'say <em>hello</em> now'

    def test_bold_span(self):
        tokens = [_tok('very', emphasis='bold'), _tok('important', emphasis='bold')]
        assert render_tokens(tokens) == '<strong>very important</strong>'

    def test_bold_italic_span(self):
        tokens = [_tok('word', emphasis='bold_italic')]
        assert render_tokens(tokens) == '<strong><em>word</em></strong>'

    def test_mixed_emphasis_groups(self):
        tokens = [
            _tok('normal'),
            _tok('italic', emphasis='italic'),
            _tok('also', emphasis='italic'),
            _tok('plain'),
        ]
        result = render_tokens(tokens)
        assert result == 'normal <em>italic also</em> plain'

    def test_html_escaping(self):
        tokens = [_tok('<b>raw</b>')]
        result = render_tokens(tokens)
        assert '&lt;b&gt;' in result
        assert '<b>' not in result

    def test_empty(self):
        assert render_tokens([]) == ''


# ---------------------------------------------------------------------------
# render_element()
# ---------------------------------------------------------------------------

class TestRenderElement:
    def test_paragraph(self):
        el = {'label': 'text', 'tokens': [_tok('hello'), _tok('world')]}
        assert render_element(el) == '<p>hello world</p>'

    def test_heading_h1(self):
        el = {'label': 'title', 'tokens': [_tok('Chapter'), _tok('One')]}
        assert render_element(el) == '<h1>Chapter One</h1>'

    def test_heading_h2(self):
        el = {'label': 'heading', 'tokens': [_tok('Section')]}
        assert render_element(el) == '<h2>Section</h2>'


# ---------------------------------------------------------------------------
# build_book_html() integration
# ---------------------------------------------------------------------------

class TestBuildBookHtml:
    def test_single_page(self):
        pages = [_page(1, [_tok('hello', 'Text', paragraph_start=True), _tok('world', 'Text')])]
        html, decisions = build_book_html(pages)
        assert '<p>hello world</p>' in html
        assert decisions == []

    def test_paragraph_continuation_across_pages(self):
        pages = [
            _page(1, [_tok('he', 'Text', paragraph_start=True), _tok('said', 'Text')]),
            _page(2, [_tok('nothing', 'Text', paragraph_start=True)]),
        ]
        html, decisions = build_book_html(pages)
        assert '<p>he said nothing</p>' in html
        assert decisions[0]['decision'] == 'paragraph_continuation'

    def test_word_split_across_pages(self):
        pages = [
            _page(1, [_tok('weight-', 'Text', paragraph_start=True)]),
            _page(2, [_tok('less', 'Text', paragraph_start=True), _tok('here', 'Text')]),
        ]
        html, decisions = build_book_html(pages)
        assert 'weightless' in html
        assert decisions[0]['decision'] == 'word_split'

    def test_new_paragraph_across_pages(self):
        pages = [
            _page(1, [_tok('He', 'Text', paragraph_start=True), _tok('said.', 'Text')]),
            _page(2, [_tok('She', 'Text', paragraph_start=True), _tok('left.', 'Text')]),
        ]
        html, decisions = build_book_html(pages)
        assert '<p>He said.</p>' in html
        assert '<p>She left.</p>' in html
        assert decisions[0]['decision'] == 'new_paragraph'

    def test_picture_page_skipped(self):
        pages = [
            _page(1, [_tok('before', 'Text', paragraph_start=True)]),
            _page(2, [], picture=True),
            _page(3, [_tok('after', 'Text', paragraph_start=True)]),
        ]
        html, decisions = build_book_html(pages)
        assert 'before' in html
        assert 'after' in html
        assert decisions[0].get('gap') is True
        assert decisions[0]['decision'] == 'new_paragraph'

    def test_heading_followed_by_paragraph(self):
        pages = [_page(1, [
            _tok('Chapter', 'Title', paragraph_start=True),
            _tok('One', 'Title'),
            _tok('Body', 'Text', paragraph_start=True),
            _tok('text', 'Text'),
        ])]
        html, _ = build_book_html(pages)
        assert '<h1>Chapter One</h1>' in html
        assert '<p>Body text</p>' in html

    def test_empty_input(self):
        html, decisions = build_book_html([])
        assert html == ''
        assert decisions == []
