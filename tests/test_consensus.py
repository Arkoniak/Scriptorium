import pytest
from scripts.consensus import Token, key, normalize, normalize_attributed, normalize_blocks, consense_page, picture_coverage, _html_emphasis


def _page(text: str) -> dict:
    """Minimal page dict for a text-only model (no blocks)."""
    return {'text': text, 'blocks': [], 'format': 'markdown'}


def _block_page(blocks: list[dict]) -> dict:
    """Page dict for a model with structured blocks (Surya / Unlimited grounding)."""
    return {'text': ' '.join(b.get('text', '') for b in blocks), 'blocks': blocks}


# ---------------------------------------------------------------------------
# _html_emphasis()
# ---------------------------------------------------------------------------

class TestHtmlEmphasis:
    def test_italic(self):
        assert _html_emphasis('<i>word</i>') == 'italic'

    def test_bold(self):
        assert _html_emphasis('<b>word</b>') == 'bold'

    def test_bold_italic(self):
        assert _html_emphasis('<b><i>word</i></b>') == 'bold_italic'

    def test_no_emphasis(self):
        assert _html_emphasis('<p>plain text</p>') is None

    def test_empty_string(self):
        assert _html_emphasis('') is None

    def test_case_insensitive(self):
        assert _html_emphasis('<I>word</I>') == 'italic'
        assert _html_emphasis('<B>word</B>') == 'bold'


# ---------------------------------------------------------------------------
# normalize()
# ---------------------------------------------------------------------------

class TestNormalizeMarkup:
    def test_strips_markdown_images(self):
        assert normalize('before ![alt](url) after') == ['before', 'after']

    def test_strips_markdown_links_keeps_text(self):
        assert normalize('see [chapter](url) for details') == ['see', 'chapter', 'for', 'details']

    def test_strips_html_tags(self):
        assert normalize('<i>word</i>') == ['word']

    def test_strips_emphasis_markers(self):
        assert normalize('**bold** _italic_ text') == ['bold', 'italic', 'text']

    def test_strips_heading_markers(self):
        assert normalize('# Title') == ['Title']


class TestNormalizeDehyphenate:
    def test_merges_cross_token_line_break_split(self):
        assert normalize('edu-\ncational') == ['educational']

    def test_merges_multiple_splits_in_sequence(self):
        assert normalize('foot-\nsteps in-\nrun') == ['footsteps', 'inrun']

    def test_does_not_touch_single_token_hyphen(self):
        assert normalize('walkie-talkie') == ['walkie-talkie']

    def test_trailing_hyphen_at_end_of_stream_stays(self):
        assert normalize('self-') == ['self-']

    def test_mixed_normal_and_split(self):
        assert normalize('over-\ncome the self-doubt') == ['overcome', 'the', 'self-doubt']


# ---------------------------------------------------------------------------
# normalize_attributed()
# ---------------------------------------------------------------------------

class TestNormalizeAttributed:
    def test_plain_text_no_emphasis(self):
        tokens = normalize_attributed('hello world')
        assert all(t.emphasis is None for t in tokens)
        assert [t.text for t in tokens] == ['hello', 'world']

    def test_italic_span(self):
        tokens = normalize_attributed('say *hello* now')
        by_text = {t.text: t.emphasis for t in tokens}
        assert by_text['say'] is None
        assert by_text['hello'] == 'italic'
        assert by_text['now'] is None

    def test_bold_span(self):
        tokens = normalize_attributed('say **hello** now')
        by_text = {t.text: t.emphasis for t in tokens}
        assert by_text['hello'] == 'bold'

    def test_bold_italic_span(self):
        tokens = normalize_attributed('say ***hello*** now')
        by_text = {t.text: t.emphasis for t in tokens}
        assert by_text['hello'] == 'bold_italic'

    def test_no_label_from_text(self):
        tokens = normalize_attributed('*word*')
        assert all(t.label is None for t in tokens)

    def test_no_paragraph_start_from_text(self):
        tokens = normalize_attributed('*word* plain')
        assert all(not t.paragraph_start for t in tokens)


# ---------------------------------------------------------------------------
# normalize_blocks()
# ---------------------------------------------------------------------------

class TestNormalizeBlocks:
    def test_label_attached(self):
        blocks = [
            {'text': '12', 'label': 'PageHeader', 'html': '12'},
            {'text': 'body text', 'label': 'Text', 'html': '<p>body text</p>'},
        ]
        tokens = normalize_blocks(blocks)
        assert tokens[0].label == 'PageHeader'
        assert tokens[0].text == '12'
        assert tokens[1].label == 'Text'

    def test_italic_from_html(self):
        blocks = [{'text': 'word', 'label': 'Text', 'html': '<i>word</i>'}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].emphasis == 'italic'

    def test_bold_from_html(self):
        blocks = [{'text': 'word', 'label': 'Text', 'html': '<b>word</b>'}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].emphasis == 'bold'

    def test_bold_italic_from_html(self):
        blocks = [{'text': 'word', 'label': 'Text', 'html': '<b><i>word</i></b>'}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].emphasis == 'bold_italic'

    def test_no_emphasis_without_html(self):
        blocks = [{'text': 'word', 'label': 'Text'}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].emphasis is None

    def test_unlimited_grounding_no_html(self):
        blocks = [{'text': 'title here', 'label': 'title', 'bbox': [0, 0, 100, 50]}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].label == 'title'
        assert tokens[0].emphasis is None

    def test_paragraph_start_first_token_of_each_block(self):
        blocks = [
            {'text': 'one two', 'label': 'Text', 'html': ''},
            {'text': 'three four', 'label': 'Text', 'html': ''},
        ]
        tokens = normalize_blocks(blocks)
        assert tokens[0].paragraph_start is True   # 'one' — first in block 0
        assert tokens[1].paragraph_start is False  # 'two'
        assert tokens[2].paragraph_start is True   # 'three' — first in block 1
        assert tokens[3].paragraph_start is False  # 'four'

    def test_paragraph_start_single_token_block(self):
        blocks = [{'text': 'alone', 'label': 'Text', 'html': ''}]
        tokens = normalize_blocks(blocks)
        assert tokens[0].paragraph_start is True


# ---------------------------------------------------------------------------
# key()
# ---------------------------------------------------------------------------

class TestKeyTypography:
    def test_curly_apostrophe_equals_straight(self):
        assert key('Joss’s') == key("Joss's")

    def test_em_dash_equals_hyphen(self):
        assert key('well—known') == key('well-known')

    def test_en_dash_equals_hyphen(self):
        assert key('2020–2021') == key('2020-2021')

    def test_curly_double_quotes_ignored(self):
        assert key('“hello”') == key('"hello"')


class TestKeyCase:
    def test_casefold(self):
        assert key('WORD') == key('word')
        assert key('Title') == key('title')


class TestKeyEdgePunctuation:
    def test_strips_trailing_period(self):
        assert key('word.') == key('word')

    def test_strips_leading_and_trailing_quotes(self):
        assert key('"word"') == key('word')

    def test_strips_parentheses(self):
        assert key('(word)') == key('word')


class TestKeyHyphens:
    def test_single_token_hyphen_ignored(self):
        assert key('foot-steps') == key('footsteps') == 'footsteps'

    def test_internal_hyphen_stripped(self):
        assert key('in-run') == key('inrun') == 'inrun'

    def test_walkie_talkie_matches_dehyphenated(self):
        assert key('walkie-talkie') == key('walkietalkie') == 'walkietalkie'


# ---------------------------------------------------------------------------
# consense_page() integration
# ---------------------------------------------------------------------------

class TestConsensePage:
    def test_unanimous_agreement(self):
        pages = {
            'm1': _page('hello world'),
            'm2': _page('hello world'),
            'm3': _page('hello world'),
        }
        result = consense_page(pages)
        assert result['agreement_rate'] == 1.0
        assert result['n_disagreements'] == 0
        assert result['consensus_text'] == 'hello world'

    def test_hyphen_variants_count_as_agreement(self):
        pages = {
            'm1': _page('foot-steps ahead'),
            'm2': _page('footsteps ahead'),
            'm3': _page('footsteps ahead'),
            'm4': _page('footsteps ahead'),
        }
        result = consense_page(pages)
        assert result['n_disagreements'] == 0
        assert result['agreement_rate'] == 1.0

    def test_majority_vote_picks_winner(self):
        pages = {
            'm1': _page('correct word'),
            'm2': _page('correct word'),
            'm3': _page('correct word'),
            'm4': _page('correct wrord'),
        }
        result = consense_page(pages)
        assert 'correct' in result['consensus_text']
        assert 'word' in result['consensus_text']

    def test_disagreement_reported(self):
        pages = {
            'm1': _page('alpha bravo'),
            'm2': _page('alpha charlie'),
        }
        result = consense_page(pages)
        assert result['n_disagreements'] >= 1

    def test_header_stripped_from_body_text(self):
        pages = {
            'surya': _block_page([
                {'text': '12', 'label': 'PageHeader', 'html': '12'},
                {'text': 'hello world', 'label': 'Text', 'html': '<p>hello world</p>'},
            ]),
            'other': _page('12 hello world'),
        }
        result = consense_page(pages)
        assert '12' in result['consensus_text']
        assert '12' not in result['body_text']
        assert 'hello world' in result['body_text']

    def test_body_text_equals_consensus_when_no_headers(self):
        pages = {
            'surya': _block_page([{'text': 'hello world', 'label': 'Text', 'html': '<p>hello world</p>'}]),
            'other': _page('hello world'),
        }
        result = consense_page(pages)
        assert result['body_text'] == result['consensus_text']

    def test_label_in_disagreements(self):
        pages = {
            'surya': _block_page([
                {'text': '12', 'label': 'PageHeader', 'html': '12'},
                {'text': 'body', 'label': 'Text', 'html': '<p>body</p>'},
            ]),
            'other': _page('body'),
        }
        result = consense_page(pages)
        header_dis = [d for d in result['disagreements'] if d.get('label') == 'PageHeader']
        assert len(header_dis) > 0

    def test_emphasis_in_disagreements(self):
        pages = {
            'surya': _block_page([{'text': 'word', 'label': 'Text', 'html': '<i>word</i>'}]),
            'qwen3-vl-8b': _page('*word*'),
        }
        result = consense_page(pages)
        # Both models agree on 'word' → text agreement=1.0
        assert result['agreement_rate'] == 1.0
        assert 'word' in result['consensus_text']

    def test_voted_tokens_present(self):
        pages = {
            'surya': _block_page([{'text': 'hello world', 'label': 'Text', 'html': '<p>hello world</p>'}]),
            'other': _page('hello world'),
        }
        result = consense_page(pages)
        assert 'voted_tokens' in result
        assert len(result['voted_tokens']) == 2
        assert result['voted_tokens'][0]['text'] == 'hello'
        assert result['voted_tokens'][1]['text'] == 'world'

    def test_voted_tokens_has_required_fields(self):
        pages = {
            'surya': _block_page([{'text': 'word', 'label': 'Text', 'html': '<i>word</i>'}]),
            'other': _page('word'),
        }
        result = consense_page(pages)
        token = result['voted_tokens'][0]
        assert 'text' in token
        assert 'label' in token
        assert 'emphasis' in token
        assert 'paragraph_start' in token

    def test_voted_tokens_emphasis_typed(self):
        pages = {
            'surya': _block_page([{'text': 'word', 'label': 'Text', 'html': '<i>word</i>'}]),
            'qwen3-vl-8b': _page('*word*'),
        }
        result = consense_page(pages)
        assert result['voted_tokens'][0]['emphasis'] == 'italic'

    def test_qwen_none_defeats_surya_false_bold(self):
        """Qwen3-VL 'no emphasis' wins over Surya's false bold (e.g. ALL CAPS → <b>)."""
        pages = {
            'surya': _block_page([{'text': 'CAPS', 'label': 'Text', 'html': '<b>CAPS</b>'}]),
            'qwen3-vl-8b': _page('CAPS'),
        }
        result = consense_page(pages)
        assert result['voted_tokens'][0]['emphasis'] is None

    def test_qwen_italic_wins_surya_none(self):
        """Qwen3-VL italic detection wins when Surya produces no emphasis."""
        pages = {
            'surya': _block_page([{'text': 'word', 'label': 'Text', 'html': '<p>word</p>'}]),
            'qwen3-vl-8b': _page('*word*'),
        }
        result = consense_page(pages)
        assert result['voted_tokens'][0]['emphasis'] == 'italic'

    def test_glm_does_not_participate_in_emphasis_voting(self):
        """GLM-OCR (priority 0) does not affect emphasis voting."""
        pages = {
            'surya': _block_page([{'text': 'word', 'label': 'Text', 'html': '<i>word</i>'}]),
            'glm-ocr': _page('word'),
        }
        result = consense_page(pages)
        assert result['voted_tokens'][0]['emphasis'] == 'italic'

    def test_voted_tokens_excludes_headers(self):
        pages = {
            'surya': _block_page([
                {'text': '12', 'label': 'PageHeader', 'html': '12'},
                {'text': 'body', 'label': 'Text', 'html': '<p>body</p>'},
            ]),
            'other': _page('12 body'),
        }
        result = consense_page(pages)
        texts = [t['text'] for t in result['voted_tokens']]
        assert '12' not in texts
        assert 'body' in texts

    def test_voted_tokens_empty_on_picture_page(self):
        pages = {
            'surya': {
                'image_bbox': [0, 0, 100, 100],
                'blocks': [_picture_block(0, 0, 100, 80)],
                'text': '',
            },
            'other': _page('cover text'),
        }
        result = consense_page(pages, picture_threshold=0.4)
        assert result['voted_tokens'] == []

    def test_voted_tokens_paragraph_start(self):
        pages = {
            'surya': _block_page([
                {'text': 'first block', 'label': 'Text', 'html': ''},
                {'text': 'second block', 'label': 'Text', 'html': ''},
            ]),
            'unlimited': _block_page([
                {'text': 'first block', 'label': 'text', 'html': ''},
                {'text': 'second block', 'label': 'text', 'html': ''},
            ]),
        }
        result = consense_page(pages)
        tokens = result['voted_tokens']
        # 'first' is the first token of block 0 → paragraph_start=True
        first_tokens = [t for t in tokens if t['text'] == 'first']
        assert first_tokens[0]['paragraph_start'] is True
        # 'block' (end of block 0) → paragraph_start=False
        # 'second' is first token of block 1 → paragraph_start=True
        second_tokens = [t for t in tokens if t['text'] == 'second']
        assert second_tokens[0]['paragraph_start'] is True


# ---------------------------------------------------------------------------
# picture_coverage() + image/graphic gate
# ---------------------------------------------------------------------------

def _picture_block(x0, y0, x1, y1, label='Picture'):
    return {'label': label, 'text': '', 'bbox': [x0, y0, x1, y1]}


def _text_block(text, x0, y0, x1, y1, label='Text'):
    return {'label': label, 'text': text, 'bbox': [x0, y0, x1, y1]}


class TestPictureCoverage:
    def test_no_blocks_zero(self):
        assert picture_coverage({'blocks': []}) == 0.0

    def test_full_page_picture_surya(self):
        # Surya provides image_bbox for page dimensions
        page = {
            'image_bbox': [0, 0, 100, 200],
            'blocks': [_picture_block(0, 0, 100, 200)],
        }
        assert picture_coverage(page) == pytest.approx(1.0)

    def test_half_page_picture(self):
        page = {
            'image_bbox': [0, 0, 100, 200],
            'blocks': [_picture_block(0, 100, 100, 200)],
        }
        assert picture_coverage(page) == pytest.approx(0.5)

    def test_unlimited_label_image(self):
        # Unlimited-OCR uses 'image' label; page area inferred from block extents
        page = {
            'blocks': [
                _text_block('hello', 0, 0, 100, 50, label='text'),
                _picture_block(0, 50, 100, 100, label='image'),
            ]
        }
        # page area = 100 * 100 = 10000; picture = 100 * 50 = 5000
        assert picture_coverage(page) == pytest.approx(0.5)

    def test_text_only_page_zero(self):
        page = {
            'image_bbox': [0, 0, 100, 200],
            'blocks': [_text_block('hello world', 10, 10, 90, 50, label='Text')],
        }
        assert picture_coverage(page) == 0.0


class TestConsensePagePictureGate:
    def test_picture_page_flag_set(self):
        # Page where one model reports >40% picture coverage
        pages = {
            'surya': {
                'image_bbox': [0, 0, 100, 100],
                'blocks': [_picture_block(0, 0, 100, 60)],  # 60% coverage
                'text': '',
            },
            'other': _page('some text'),
        }
        result = consense_page(pages, picture_threshold=0.4)
        assert result['picture_page'] is True
        assert result['picture_coverage'] == pytest.approx(0.6)

    def test_picture_page_body_text_empty(self):
        pages = {
            'surya': {
                'image_bbox': [0, 0, 100, 100],
                'blocks': [_picture_block(0, 0, 100, 80)],
                'text': '',
            },
            'other': _page('cover text'),
        }
        result = consense_page(pages, picture_threshold=0.4)
        assert result['picture_page'] is True
        assert result['body_text'] == ''

    def test_text_page_not_flagged(self):
        pages = {
            'surya': {
                'image_bbox': [0, 0, 100, 100],
                'blocks': [
                    _picture_block(0, 90, 100, 100),  # 10% coverage
                    _text_block('body', 0, 0, 100, 90, label='Text'),
                ],
                'text': 'body',
            },
            'other': _page('body'),
        }
        result = consense_page(pages, picture_threshold=0.4)
        assert result['picture_page'] is False
        assert 'body' in result['body_text']

    def test_picture_blocks_excluded_from_tokens(self):
        blocks = [
            _picture_block(0, 0, 50, 50),
            _text_block('real text', 0, 50, 100, 100, label='Text'),
        ]
        tokens = normalize_blocks(blocks)
        texts = [t.text for t in tokens]
        assert 'real' in texts
        assert 'text' in texts
        # picture block had no text to begin with, but label is excluded
        assert all(t.label != 'Picture' for t in tokens)

    def test_picture_coverage_per_model_in_result(self):
        pages = {
            'surya': {
                'image_bbox': [0, 0, 100, 100],
                'blocks': [_picture_block(0, 0, 100, 50)],
                'text': '',
            },
            'other': _page('text'),
        }
        result = consense_page(pages)
        assert 'picture_coverage_per_model' in result
        assert 'surya' in result['picture_coverage_per_model']
        assert result['picture_coverage_per_model']['surya'] == pytest.approx(0.5)
