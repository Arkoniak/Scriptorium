# Scene-break detection — design record

Design discussion held 2026-06-29. This document is the durable record of every decision made,
every approach considered, and the reasons for each choice. The final algorithm is summarised at
the end; the bulk of this file records the *why*, including rejected alternatives.

When the code is written, it must cite this file (and the GitHub issue #22 comment) for any
non-obvious threshold or heuristic.

---

## 1. What is a scene-break divider?

A scene-break divider is a typographic element that signals an in-chapter section break. It always
has these structural properties:

1. **Same throughout the book** — a book buys one design element and uses it everywhere. This is
   the strongest single signal: the divider recurs identically many times.
2. **Horizontally centered** on the page (or on the text column).
3. **Small relative to the page** — a few percent of the page width/height.
4. **Isolated** — surrounded by more whitespace than a normal inter-paragraph gap, both above and
   below.
5. **Within a chapter** — it appears between paragraphs of running text, not at the top of a new
   chapter and not on a standalone page.

There are two physical forms:

| Form | Appearance | How models see it |
|---|---|---|
| Visual ornament | Small decorative glyph (vignette) | Surya: `Picture` block, empty text, bbox ~5% of page; Unlimited: `image` label, extracted raster |
| Typographic | `* * *`, `• • •`, `§`, `#` | Text block, narrow, centered; content = only separator characters |

A third form — **blank line only** (extra whitespace, no visible element) — also exists. It cannot
be detected by examining picture or text blocks; it is only detectable via the vertical gap between
consecutive paragraphs. This is handled by the gap-first approach described below.

---

## 2. Data available

**Surya** (layout model): `Picture` blocks with `bbox` in absolute pixel coordinates; reliable
`PageHeader`/`PageFooter` labels; `image_bbox` on every page giving page dimensions.

**Unlimited-OCR** (grounding mode): `image` blocks with `bbox` in 0–1000 normalised coordinates;
`header`/`footer` labels.

**Qwen3-VL, GLM-OCR**: no bounding-box output in our pipeline (plain chat / Text Recognition
mode). They do not contribute to geometric analysis.

Both Surya and Unlimited coordinates are normalised to `[0, 1]` relative to page dimensions before
any comparison. Surya's `image_bbox` provides the page size for this normalisation.

---

## 3. Rejected approaches

### 3a. Perceptual hashing (dHash/aHash)

**Idea**: crop the picture region from the page PNG, compute a perceptual hash, cluster by
Hamming distance; near-identical hashes → same ornament → scene-break.

**Why rejected**: scan quality varies per page (brightness, slight damage, ink spread). Although
dHash with a Hamming threshold of ≤10 is designed to tolerate minor variation, it adds a
dependency on PIL/imagehash and introduces a tunable parameter (the threshold) with no principled
way to set it per book. The size + recurrence approach (see §4) achieves the same goal with no
additional dependency and no per-pixel reasoning.

### 3b. Single-model label filtering (Option 1)

**Idea**: filter blocks by label directly from one model's output (e.g. exclude Surya
`PageHeader`/`PageFooter`) before gap analysis.

**Why rejected**: this implicitly trusts that another model (Unlimited) also labels running heads
correctly in every book. This holds for mindblast but may not hold in general. The consensus
pipeline already handles header/footer stripping in a cross-model way; re-implementing it in the
scene-break script would be duplicate fragile logic.

**Chosen instead**: use the consensus output (`voted_blocks_surya` / `voted_blocks_unlimited` in
the page JSON), which are derived after the consensus filtering step has already excluded
headers/footers by label.

### 3c. Maximum-jump 1D clustering

**Idea**: sort all inter-block gaps, find the largest jump between consecutive sorted values; use
midpoint as threshold.

**Why rejected**: an epigraph page with one line at the top and one at the bottom produces a gap
of ~80% page height — a massive outlier. This single value creates a jump from ~400px to ~2500px
that eclipses the true cluster boundary (~150px → ~300px), pushing the threshold far above all
scene-break gaps and making them invisible.

**Chosen instead**: IQR-based robust threshold (see §4, Phase 0).

### 3d. Global stats first, per-page stats as fallback

**Idea**: compute gap statistics per page; fall back to global stats for pages with few blocks.

**Why rejected** (in this order): pages with very few blocks are exactly the pages (epigraphs,
special pages) whose gaps are anomalous. Using them as a per-page calibration source would
produce wrong thresholds for those pages specifically. The book-level statistics, computed from all
non-picture pages, provide a single robust reference.

**Chosen instead**: one book-level calibration pass before any candidate identification.

### 3e. Starting from the picture block (geometry-first)

**Idea**: classify each picture block by size + centering → scene-break candidates, then validate
by recurrence.

**Why not the primary approach**: this misses blank-line-only scene breaks entirely (no picture
block exists). Adopted as a *secondary classification step* (Phase 2) after the gap has already
flagged the zone.

---

## 4. Final algorithm

### Phase 0 — Book-level geometry calibration

**Input**: `voted_blocks_surya` and `voted_blocks_unlimited` from all pages in
`consensus/<suffix>/pages/page_*.json` where `picture_page != true`.

**Step A — x-offset clustering (identify paragraph blocks)**

Collect the normalised left-edge `x0` of every block from both models (pooled). The distribution
is bimodal:
- Left cluster: paragraph text blocks (x0 ≈ 0.02–0.10 of page width)
- Right cluster: centred ornaments, chapter titles, etc. (x0 ≈ 0.40–0.55)

Apply IQR-based threshold: `paragraph_x_threshold = Q3(x0) + 3 × IQR(x0)`.

A block is a **paragraph block** if `x0 < paragraph_x_threshold`.

**Step B — gap distribution (find scene-break threshold)**

For each page, sort paragraph blocks by `y0` (top edge). For each consecutive pair
`(block_i, block_{i+1})` on the same page, compute:

```
gap = block_{i+1}.y0 - block_i.y1      # normalised to [0, 1] by page height
```

Cross-page gaps are excluded (they carry no scene-break information).

Pool all gaps from both models. Apply robust threshold:

```
Q1, Q3 = 25th and 75th percentile of all gaps
IQR = Q3 - Q1
large_gap_threshold = Q3 + 3 × IQR
```

**Separability check**: if `min(gaps > threshold) > 1.5 × large_gap_threshold`, the two clusters
are well-separated → high confidence. Otherwise emit a warning ("marginal separation, review
manually").

If no gaps exceed the threshold: emit "no scene breaks detected" and exit.

---

### Phase 1 — Candidate identification

Walk every page in book order. For every pair of consecutive paragraph blocks with
`gap > large_gap_threshold`, record a **gap candidate**:

```
{page, y_gap_top, y_gap_bottom, gap_surya, gap_unlimited}
```

Also collect all non-paragraph blocks that fall vertically within `[y_gap_top, y_gap_bottom]`
on that page — these are the decoration blocks *inside* the gap zone.

---

### Phase 2 — Classification

For each gap candidate:

| Contents of gap zone | Classification |
|---|---|
| No blocks | `scene_break` (blank-line style) |
| Picture block, `w < 0.15`, `h < 0.15`, `\|cx − 0.5\| < 0.15` | `scene_break` (visual ornament) |
| Text block, content = only `*`/`•`/`-`/`—`/`#` chars, centred | `scene_break` (typographic) |
| Block with label `title` or `heading` | `chapter_boundary` (not `<hr>`) |
| Anything else | `unknown` — flagged for manual review |

Size/centering numbers (`0.15`) are relative to page dimensions, derived from mindblast data
(ornament ≈ 4.4% of page width) with ×3 headroom. They are book-independent because both sides
of the equation are relative.

---

### Phase 3 — Book-level validation

For visual ornament candidates: check size consistency across all instances (std of `w` and `h`
should be < 0.02 in normalised coordinates). If consistent → confirmed. If < 3 instances total →
warn ("too few occurrences to confirm cluster").

---

### Cross-model comparison

The two models are processed independently through Phases 0–2. For each candidate, record which
models agree:

```
{page, y_top, y_bottom, classification,
 surya: true/false, unlimited: true/false, confidence: "high"/"low"}
```

**Confidence**:
- Both models agree → `high`
- Only one model sees the gap → `low` (included in output but flagged)

Matching across models: a Surya gap and an Unlimited gap on the same page are considered the same
break if their `y` intervals overlap (tolerance ±0.05 in normalised coordinates).

---

## 5. Output format

**`scene_breaks.json`** — machine-readable, consumed by `build_html.py`:

```json
[
  {"page": 9,  "y_top": 0.29, "y_bottom": 0.33,
   "classification": "scene_break", "subtype": "ornament",
   "confidence": "high", "surya": true, "unlimited": true},
  {"page": 113, "y_top": 0.04, "y_bottom": 0.07,
   "classification": "scene_break", "subtype": "ornament",
   "confidence": "low", "surya": true, "unlimited": false}
]
```

**`scene_breaks_diagnostic.json`** — human-readable comparison table; records all gap candidates
from both models including `unknown` and `chapter_boundary` entries, for manual review.

---

## 6. Pipeline integration

```
consensus.py
  adds to page JSON:
    voted_blocks_surya   — Surya blocks excl. PageHeader/Footer, bbox normalised to [0,1]
    voted_blocks_unlimited — Unlimited blocks excl. header/footer, bbox normalised to [0,1]

detect_scene_breaks.py
  reads: consensus/<suffix>/pages/page_*.json
  writes: consensus/<suffix>/scene_breaks.json
          consensus/<suffix>/scene_breaks_diagnostic.json

build_html.py
  reads: voted_tokens (existing)
         scene_breaks.json (new, optional)
  inserts <hr> at positions matching scene_breaks entries
```

`detect_scene_breaks.py` is a standalone post-processing step. It does not re-run any model.
It reads only from the consensus directory. `build_html.py` gracefully skips scene-break
insertion if `scene_breaks.json` is absent.

---

## 7. Known limitations

1. **Blank-line scene breaks at page boundaries** cannot be detected. The gap spans two pages and
   we only measure within-page gaps. Accepted as an inherent limitation of per-page processing.

2. **Special/frontmatter pages (epigraphs, half-titles)** are included in the gap calibration
   because we have no page classifier yet (issue #33). Their anomalous gaps (single line at top
   and bottom → gap ≈ 80% page height) are neutralised by the IQR-based threshold rather than
   the fragile max-jump approach. Once #33 lands, calibration should be rerun on `content`-only
   pages for cleaner separation.

3. **Books with no scene breaks** produce no gaps above threshold. The algorithm exits cleanly
   with "no scene breaks detected".

4. **Chapter boundaries** appear as large gaps with a `title`/`heading` block inside; they are
   classified as `chapter_boundary`, not `<hr>`. This is by design. The current test book
   (mindblast) has no chapters, so this branch of Phase 2 is not validated yet.

---

## 8. Soft dependencies

- **#33 page classifier**: when available, restrict calibration (Phase 0) to `content` pages only.
  This tightens the gap distribution and improves threshold quality.
- **#34 image extraction**: not needed for scene-break detection itself, but `build_html.py`
  needs it for picture pages. The two scripts are independent.
