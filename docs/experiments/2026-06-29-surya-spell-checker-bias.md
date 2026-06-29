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

## 50/50 tie audit (2026-06-29)

Of the 101 content disagreements at 50% agreement, **36 are won by Surya's side** (by insertion-order
tiebreaking in `Counter.most_common()`). All 36 reviewed manually.

Result: **35/36 correct, 1/36 wrong.**

The one wrong case: **p221** `"Don't` — Surya+Qwen read `Don't`, Unlimited+GLM read `"'Don'`/`''Don'`.
Correct answer is `Don'` (the character speaks broken English deliberately, dropping the `t`). Consensus
picked Surya's spell-corrected version.

Revised picture of the 36 ties:
- **p001** (12 ties) — title/copyright page, unreliable by design; excluded from body text in practice.
- **p172/173** `Ivar` vs `lvar` — Surya+Unlimited correct; Qwen+GLM confused capital `I` with lowercase `l`.
- **p101/163/178/256** `creds` vs `credits` — Surya+Qwen correct; sci-fi currency slang, Unlimited+GLM spell-checked to `credits`.
- **p181** `unmistakeable` vs `unmistakable` — Surya+GLM have the British spelling from the original; both valid.
- **p015** `receipted:` vs `received:` — Surya+GLM correct.
- **p130** `"Suspicions,` vs `"Suspicious,` — Surya+GLM correct.
- **p252** `neuotransmitter` vs `neurotransmitter` — **Surya+GLM correctly preserved an original typo**; Unlimited+Qwen spell-checked to `neurotransmitter`. Consensus correctly preserved the typo.
- **p123** `raied` vs `raised` — same: **original typo in the book**; Surya+GLM faithful, Unlimited+Qwen spell-checked.
- Remaining ties: isolated punctuation/quote disagreements, no semantic content.

**Key revision**: the spell-checker behavior is not unique to Surya. Unlimited and Qwen also
spell-check — they normalised `raied`→`raised` and `neuotransmitter`→`neurotransmitter`. Surya's
spell-checker failures are concentrated on a different class: **composite neologisms** (`vid-cassette`,
`vidshooter`, `bat-thing`) and **non-standard dialect** (`Don't`/`Don'`). Unlimited/Qwen fail on
**ordinary-word typos** that happen to resemble real words.

The 50/50 position bias is therefore largely benign in practice: Surya wins tiebreaks correctly 35/36
times on this book. The one loss (p221) would be caught by a 5th tie-breaking model.

## Open questions

**`vid-cassette` vs `vidcassette`**: if the word breaks across a line as `vid-` / `cassette`, our
`_dehyphenate` rule would produce `vidcassette`, but the winner is `vid-cassette` (three models read
it as a single hyphenated token). Frequency analysis across the full book would determine the
author's canonical spelling — currently unknown.

**Undetected corrections**: if all 4 models normalise the same word the same way (unanimous), the
change is invisible to the disagreement report. Ground truth would be needed to catch these.

## Conclusion

Surya is the most consensus-aligned model, and after auditing the 2-vs-2 ties its tiebreak choices
are reliable (35/36). The spell-checker behavior is real but narrow — composite neologisms and
non-standard dialect — not a general problem. Unlimited and Qwen have a parallel spell-checker
tendency on ordinary-word typos.

The structural fix for the one failure class (p221-style broken English) is a **5th tie-breaking
model** that reads the page independently. The key property needed: faithfulness to what is on the
page, without language-model priors pushing toward standard spellings. Classical OCR (Tesseract or
similar) is a strong candidate — it has no learned English bias, is deterministic, and is cheap to
run as a supplementary signal on contested slots only.

Remaining mitigations:
1. Frequency analysis across pages for recurring compound words (resolves `vid-cassette`).
2. Pages 1–2 (cover, copyright/ISBN) and 260 (back cover) should be excluded from body text
   processing — all models perform poorly on them and they are not narrative content.

Rationale: known.
