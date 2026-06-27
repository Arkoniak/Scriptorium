import pytest
from scripts.consensus import key, normalize, consense_page


# ---------------------------------------------------------------------------
# normalize()
# ---------------------------------------------------------------------------

class TestNormalizeMarkup:
    def test_strips_markdown_images(self):
        assert normalize("before ![alt](url) after") == ["before", "after"]

    def test_strips_markdown_links_keeps_text(self):
        assert normalize("see [chapter](url) for details") == ["see", "chapter", "for", "details"]

    def test_strips_html_tags(self):
        assert normalize("<i>word</i>") == ["word"]

    def test_strips_emphasis_markers(self):
        assert normalize("**bold** _italic_ text") == ["bold", "italic", "text"]

    def test_strips_heading_markers(self):
        assert normalize("# Title") == ["Title"]


class TestNormalizeDehyphenate:
    def test_merges_cross_token_line_break_split(self):
        # "edu-\ncational" split by whitespace -> ["edu-", "cational"] -> ["educational"]
        assert normalize("edu-\ncational") == ["educational"]

    def test_merges_multiple_splits_in_sequence(self):
        # "foot-\nsteps in-\nrun" -> ["footsteps", "inrun"]
        assert normalize("foot-\nsteps in-\nrun") == ["footsteps", "inrun"]

    def test_does_not_touch_single_token_hyphen(self):
        # "walkie-talkie" is one token, no trailing dash -> unchanged
        assert normalize("walkie-talkie") == ["walkie-talkie"]

    def test_trailing_hyphen_at_end_of_stream_stays(self):
        # no next token to merge with
        assert normalize("self-") == ["self-"]

    def test_mixed_normal_and_split(self):
        assert normalize("over-\ncome the self-doubt") == ["overcome", "the", "self-doubt"]


# ---------------------------------------------------------------------------
# key()
# ---------------------------------------------------------------------------

class TestKeyTypography:
    def test_curly_apostrophe_equals_straight(self):
        assert key('Joss’s') == key("Joss's")

    def test_em_dash_equals_hyphen(self):
        assert key("well—known") == key("well-known")

    def test_en_dash_equals_hyphen(self):
        assert key("2020–2021") == key("2020-2021")

    def test_curly_double_quotes_ignored(self):
        assert key('“hello”') == key('"hello"')


class TestKeyCase:
    def test_casefold(self):
        assert key("WORD") == key("word")
        assert key("Title") == key("title")


class TestKeyEdgePunctuation:
    def test_strips_trailing_period(self):
        assert key("word.") == key("word")

    def test_strips_leading_and_trailing_quotes(self):
        assert key('"word"') == key("word")

    def test_strips_parentheses(self):
        assert key("(word)") == key("word")


class TestKeyHyphens:
    def test_single_token_hyphen_ignored(self):
        # foot-steps and footsteps should match
        assert key("foot-steps") == key("footsteps") == "footsteps"

    def test_internal_hyphen_stripped(self):
        assert key("in-run") == key("inrun") == "inrun"

    def test_walkie_talkie_matches_dehyphenated(self):
        # after cross-token dehyphenation, walkietalkie and walkie-talkie agree
        assert key("walkie-talkie") == key("walkietalkie") == "walkietalkie"


# ---------------------------------------------------------------------------
# consense_page() integration
# ---------------------------------------------------------------------------

class TestConsensePage:
    def test_unanimous_agreement(self):
        texts = {
            "m1": "hello world",
            "m2": "hello world",
            "m3": "hello world",
        }
        result = consense_page(texts)
        assert result["agreement_rate"] == 1.0
        assert result["n_disagreements"] == 0
        assert result["consensus_text"] == "hello world"

    def test_hyphen_variants_count_as_agreement(self):
        # foot-steps vs footsteps: should agree, no disagreement reported
        texts = {
            "m1": "foot-steps ahead",
            "m2": "footsteps ahead",
            "m3": "footsteps ahead",
            "m4": "footsteps ahead",
        }
        result = consense_page(texts)
        assert result["n_disagreements"] == 0
        assert result["agreement_rate"] == 1.0

    def test_majority_vote_picks_winner(self):
        texts = {
            "m1": "correct word",
            "m2": "correct word",
            "m3": "correct word",
            "m4": "correct wrord",  # typo
        }
        result = consense_page(texts)
        assert "correct" in result["consensus_text"]
        assert "word" in result["consensus_text"]

    def test_disagreement_reported(self):
        texts = {
            "m1": "alpha bravo",
            "m2": "alpha charlie",
        }
        result = consense_page(texts)
        assert result["n_disagreements"] >= 1
