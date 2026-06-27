# Consensus across 4 models — alignment-first ROVER + disagreement map (full book)

First consolidation experiment. Built `scripts/consensus.py` (deterministic, no LLM) and ran it over the
full-book runs of the 4 working models (Surya, Unlimited-OCR, Qwen3-VL, GLM-OCR), 260 pages each.

## Method
Per page: gather each model's `text`, normalize to a flat word stream (strip markup; canonicalize
typographic punctuation — `’`→`'`, `“”`→`"`, `—`→`-` — in the *matching key* only, so curly/straight
variants count as agreement), **align** the streams into columns via progressive multiple alignment
(`difflib` opcodes with gap/NULL insertion), then per column **vote** (ROVER) and measure agreement +
entropy. Output: a voted consensus text per page plus a localized disagreement report.

**Why alignment-first** (the key point): naive position-by-position voting frame-shifts — one model's
deletion makes everything downstream look wrong. Alignment turns that deletion into a single gap
column, so disagreement localizes to the one real spot and the rest stays unanimous. Validated on
page 20: 2 models include the running head "12 / SPACE COPS", 2 omit it; after alignment the header is
3 gap columns at the top and the 375-word body is 100% unanimous.

## Result (full book)
- **260 pages, 89,237 columns, 1,423 disagreements → 98.41% agreement.** The models agree on the vast
  majority of body text.
- **Breakdown of the 1,423 disagreements:**
  - **Omission (running head / boundary): 1,176 (83%)** — mostly the "page-number + SPACE COPS" header
    that 2 models include and 2 omit. Not content errors; Stage-3 header removal handles them. The
    pattern itself (short top/bottom token omitted by ≥1 model) is a usable header detector.
  - **Substitution (real read difference): 247 (17%)**, which split into:
    - *Stylized logos / barcode* (cover, title, ISBN) — content we keep as raster anyway (the gate
      filters it). Oddity: Qwen emitted the literal word `markdown` on the title logo — a prompt artifact.
    - *Line-break hyphenation* (`foot-steps`↔`footsteps`, `in-run`↔`inrun`) — a soft typographic
      disagreement, like apostrophes; should be folded into the matching key.
    - **Real OCR misreads — ROVER's payoff:** `prytool`×3 vs `pyytool`, `inrunner`×3 vs `irrunner`,
      `inrunners`×3 vs `innurners`, `N'wast'm'time`×3 vs `…'tine`. Three models agree, one misreads →
      the 3:1 vote **recovers the correct word**. Consensus actively fixes single-model errors.

## Reliability signal (lone dissenter, 1-vs-3)
`surya 18 · glm 37 · unlimited 45 · qwen 52`. **Surya diverges from the majority least often** (most
consensus-aligned); Qwen most. Unlimited is notably prone to character-level misreads (irrunner,
innurners, pyytool). Empirical support for weighting Surya higher — at least it tracks the consensus.

## Typography
Canonicalized only in the matching key (so variants agree). The *output* still keeps the models'
spellings; choosing the book-correct glyph (curly quotes, em-dash) is a separate output-normalization
step, deferred — with a candidate policy of **per-aspect authority**: trust Surya for typography,
take emphasis only from emphasis-capable models, let all 4 vote on plain content.

## Conclusion
The Bag-of-Experts thesis holds: consensus localizes disagreement (98.4% agreement), most of the rest
is strippable header noise, and where a single model misreads, alignment-first voting fixes it. The
disagreement map also hands us, for free, signals for the next steps (header detection, the image
gate, the typography policy). Next steps filed as GitHub issues.

Rationale: known.
