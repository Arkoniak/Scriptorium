# Surya spell-checker bias: manual audit of Surya's content disagreements

Manual review of every case where Surya's output differs from the consensus winner on content tokens
(headers excluded). Run on the full book (260 pages, 4 models: Surya, Unlimited-OCR, Qwen3-VL, GLM-OCR)
after adding `content_agreement_rate` to the consensus output.

## Setup
- Models: all 4 (see `books/output/mindblast/consensus/full/summary.json`)
- Input: Mindblast, 260 pages, consensus run `full`
- Method: filtered disagreements to `key(surya) != key(winner)` to separate real semantic differences
  from typography-only (straight vs curly quotes). See analysis session 2026-06-29.

## Result

Out of 783 total content disagreements, **Surya produced a different key from the consensus winner
in only 11 cases** across the full book. All 11 reviewed manually:

| Page | Surya | Winner | Verdict |
|------|-------|--------|---------|
| p001 | `Space` | `SpaceCops` | title page, unreliable by design |
| p001 | `Cops` | `MINDBLAST` | title page, unreliable by design |
| p002 | `94` | `9` | ISBN barcode fragment, unreliable |
| p052 | `damnest` | `damndest` | **Surya wrong** — spell-checker normalised |
| p052 | `and—aah,` | `and'—aah,` | **Surya wrong** — dropped apostrophe before em-dash |
| p124 | `"Don't` | `"Don'` | **Surya wrong** — added `t`; character speaks broken English deliberately |
| p127 | `said,` | `aid,` | **Surya wrong** — "corrected" original typo in the printed book |
| p173 | `video` | `vid-cassette` | **Surya wrong** — normalised sci-fi neologism |
| p173 | `video` | `vidshooter` | **Surya wrong** — normalised sci-fi neologism |
| p217 | `batting.` | `bat-thing.` | **Surya wrong** — merged tokens and changed word |
| p260 | `dangerous` | `dang` | back cover, partially obscured word; Surya hallucinated the full word |

Score: **8 confirmed Surya errors, 3 unreliable pages** (cover/barcode). Zero cases where Surya was
right and the consensus was wrong.

**The `aid,` case** is particularly revealing: `aid,` is an apparent typo in the printed book (should be
`said,`). All three other models read it as `aid,`; Surya "corrected" it to `said,`. The consensus
correctly preserved the original, typo and all. This is the desired behavior — faithful transcription,
not proofreading.

The two `video` cases on p173 are also notable: the book uses invented compound words (`vid-cassette`,
`vidshooter`). Surya appears to pull toward familiar vocabulary under uncertainty. `vid-cassette` is
a hyphenated-across-line-break case where the correct form may be `vidcassette` (see below).

## Open questions

**`vid-cassette` vs `vidcassette`**: if the word breaks across a line as `vid-` / `cassette`, our
`_dehyphenate` rule would produce `vidcassette`, but the winner is `vid-cassette` (three models read
it as a single hyphenated token). Frequency analysis across the full book would determine the
author's canonical spelling — currently unknown.

**50/50 tie bias**: 101 of 783 content disagreements are at 50% agreement (2-vs-2 split). In these,
the winner is chosen by `Counter.most_common()` which, for equal counts, follows dict insertion order
— i.e., whoever comes first in the `models` list. Surya is currently first. This means Surya
effectively wins all 2-vs-2 ties by position, not by quality. Some of those ties may be cases where
Surya's spell-checker tendency pulls two models the "corrected" way while two others read the original.
Unquantified but worth auditing, especially for neologisms and proper nouns.

**Undetected corrections**: if Surya normalizes a word and all three other models happen to agree
(e.g., a common English word that all models converge on), the correction is invisible to the
disagreement report. Ground truth would be needed to catch these.

## Conclusion

Surya is the most consensus-aligned model (18 lone dissents in the original analysis, 11 real semantic
divergences after full-book audit), but its divergences follow a consistent pattern: **it behaves as a
spell-checker**, normalising unusual words, invented compounds, and original typos toward familiar
English. This is harmful for faithful transcription — see `docs/brainstorm.md` (Stage 1 Key Tensions:
hallucination vs. missing text).

Mitigations to consider:
1. Audit 2-vs-2 tie cases for Surya-leads-normalization pattern.
2. For neologism-heavy sci-fi text, consider downweighting Surya in the tiebreaker (or randomising
   position rather than putting Surya first).
3. Frequency analysis across pages for recurring compound words (would also resolve `vid-cassette`).
4. Pages 1–2 (cover, copyright/ISBN) and 260 (back cover) probably should be excluded from body text
   processing — they have non-narrative content and all models perform poorly on them.

Rationale: known.
