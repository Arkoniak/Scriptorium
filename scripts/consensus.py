#!/usr/bin/env python3
"""Consensus across model runs — alignment-first ROVER voting + a disagreement (entropy) report.

Deterministic, no LLM. For each page it gathers the text from every model's run, normalizes to a flat
word stream, **aligns** the streams into columns (progressive multiple alignment with gap/NULL
insertion — so a single deletion in one model becomes one gap column, not a frame shift), then per
column votes (ROVER) and measures agreement. Output: a voted consensus text per page plus a report of
exactly where the models disagree (the localized signal — no spurious downstream uncertainty).

Reads the latest `*__<suffix>` run per model under books/output/<book>/runs/. See docs/brainstorm.md
(Consolidation / consensus).
"""

import argparse
import difflib
import json
import math
import re
from collections import Counter
from pathlib import Path

# --- normalization ---------------------------------------------------------------------------------

_MD = [
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),   # markdown images
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),  # markdown links -> link text
    (re.compile(r"</?[a-zA-Z][^>]*>"), " "),       # html tags (e.g. Surya's <i>)
    (re.compile(r"[*_`#>]"), " "),                  # emphasis / heading / code / quote markers
]


def normalize(text: str) -> list[str]:
    """Strip markup and tokenize into whitespace-delimited word tokens (original case preserved)."""
    for pattern, repl in _MD:
        text = pattern.sub(repl, text)
    return text.split()


# Canonicalize typographic punctuation so curly/straight variants aren't counted as disagreements
# (e.g. "Joss’s" vs "Joss's" — a glyph choice, not an OCR error).
_PUNCT_CANON = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-", "…": "..."})


def key(token: str) -> str:
    """Matching key for alignment/voting: typography-, case- and edge-punctuation-insensitive."""
    return token.translate(_PUNCT_CANON).casefold().strip(".,;:!?\"'()-")


# --- alignment -------------------------------------------------------------------------------------

def _col_key(col: list[str | None]) -> str:
    """Representative matching key for a column (majority of its non-empty entries)."""
    keys = [key(t) for t in col if t is not None]
    return Counter(keys).most_common(1)[0][0] if keys else ""


def align(seqs: list[list[str]]) -> list[list[str | None]]:
    """Progressive multiple-sequence alignment of N token streams.

    Returns a list of columns; each column is a list of length N (token or None=gap), aligned so that
    homologous tokens share a column. Built incrementally: seq0, then merge each next seq against the
    running alignment's representative tokens via difflib opcodes, inserting gap/insert columns.
    """
    if not seqs:
        return []
    cols: list[list[str | None]] = [[t] for t in seqs[0]]
    for m in range(1, len(seqs)):
        ref_keys = [_col_key(c) for c in cols]
        new = seqs[m]
        new_keys = [key(t) for t in new]
        matcher = difflib.SequenceMatcher(a=ref_keys, b=new_keys, autojunk=False)
        merged: list[list[str | None]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for off in range(i2 - i1):
                    cols[i1 + off].append(new[j1 + off])
                    merged.append(cols[i1 + off])
            elif tag == "delete":  # in the alignment, absent from this model
                for off in range(i2 - i1):
                    cols[i1 + off].append(None)
                    merged.append(cols[i1 + off])
            elif tag == "insert":  # this model has tokens the alignment lacks -> new columns
                for off in range(j2 - j1):
                    merged.append([None] * m + [new[j1 + off]])
            else:  # replace: pair the overlap, gap/insert the remainder
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

def vote_column(col: list[str | None]) -> tuple[str | None, float, bool]:
    """ROVER vote on one aligned column.

    Returns (winning token or None=delete, agreement in [0,1], tie?). None entries vote for deletion;
    among real tokens, the majority by matching key wins (original spelling = its most common form).
    """
    n = len(col)
    counts = Counter(key(t) if t is not None else None for t in col)
    (top_key, top_n), *rest = counts.most_common()
    tie = bool(rest) and rest[0][1] == top_n
    agreement = top_n / n
    if top_key is None:
        return None, agreement, tie
    # pick the most common original spelling among entries matching the winning key
    spellings = Counter(t for t in col if t is not None and key(t) == top_key)
    return spellings.most_common(1)[0][0], agreement, tie


def entropy(col: list[str | None]) -> float:
    """Shannon entropy (bits) of the vote distribution over a column (None = a 'delete' class)."""
    n = len(col)
    counts = Counter(key(t) if t is not None else None for t in col)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def consense_page(texts: dict[str, str]) -> dict:
    """Align + vote one page's per-model texts; return consensus text and a disagreement report."""
    models = list(texts)
    seqs = [normalize(texts[m]) for m in models]
    cols = align(seqs)

    voted: list[str] = []
    disagreements: list[dict] = []
    for idx, col in enumerate(cols):
        token, agreement, tie = vote_column(col)
        if token is not None:
            voted.append(token)
        if agreement < 1.0:
            disagreements.append(
                {
                    "col": idx,
                    "agreement": round(agreement, 3),
                    "entropy": round(entropy(col), 3),
                    "tie": tie,
                    "winner": token,
                    "variants": {m: col[i] for i, m in enumerate(models)},
                }
            )
    n_cols = len(cols) or 1
    return {
        "models": models,
        "n_columns": len(cols),
        "n_disagreements": len(disagreements),
        "agreement_rate": round(1 - len(disagreements) / n_cols, 4),
        "consensus_text": " ".join(voted),
        "disagreements": disagreements,
    }


# --- run discovery + driver ------------------------------------------------------------------------

def latest_runs(runs_dir: Path, suffix: str) -> dict[str, Path]:
    """Latest run directory per model among runs whose id ends with __<suffix> (run ids sort by time)."""
    by_model: dict[str, Path] = {}
    for run in sorted(runs_dir.glob(f"*__{suffix}")):
        manifest = run / "manifest.json"
        if manifest.exists():
            by_model[json.loads(manifest.read_text())["model"]] = run  # later (sorted) wins
    return by_model


def page_text(run: Path, page_no: int) -> str | None:
    path = run / "pages" / f"page_{page_no:03d}.json"
    return json.loads(path.read_text())["text"] if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True, help="Book slug, e.g. 'mindblast'")
    parser.add_argument("--out-root", type=Path, default=Path("books/output"), help="Artifacts root")
    parser.add_argument("--suffix", default="full", help="Run-id suffix/label to consolidate (default: full)")
    parser.add_argument("--pages", help="Optional page filter, e.g. '12,20' (default: all common pages)")
    args = parser.parse_args()

    runs_dir = args.out_root / args.book / "runs"
    runs = latest_runs(runs_dir, args.suffix)
    if len(runs) < 2:
        parser.error(f"Need >=2 model runs with suffix '{args.suffix}' in {runs_dir}; found {list(runs)}")

    pages = sorted({int(p.stem.split("_")[1]) for run in runs.values() for p in (run / "pages").glob("page_*.json")})
    if args.pages:
        wanted = {int(p) for p in args.pages.split(",")}
        pages = [p for p in pages if p in wanted]

    out_dir = runs_dir.parent / "consensus" / f"{args.suffix}"
    (out_dir / "pages").mkdir(parents=True, exist_ok=True)

    totals_cols = totals_dis = 0
    for page_no in pages:
        texts = {m: t for m, run in runs.items() if (t := page_text(run, page_no)) is not None}
        if len(texts) < 2:
            continue
        result = consense_page(texts)
        result["page"] = page_no
        (out_dir / "pages" / f"page_{page_no:03d}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "pages" / f"page_{page_no:03d}.txt").write_text(result["consensus_text"] + "\n", encoding="utf-8")
        totals_cols += result["n_columns"]
        totals_dis += result["n_disagreements"]

    summary = {
        "book": args.book,
        "suffix": args.suffix,
        "models": list(runs),
        "runs": {m: r.name for m, r in runs.items()},
        "pages": len(pages),
        "total_columns": totals_cols,
        "total_disagreements": totals_dis,
        "overall_agreement_rate": round(1 - totals_dis / (totals_cols or 1), 4),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Consensus written to {out_dir}")
    print(f"  {len(pages)} pages | {totals_cols} columns | {totals_dis} disagreements "
          f"| agreement {summary['overall_agreement_rate']:.3%}")


if __name__ == "__main__":
    main()
