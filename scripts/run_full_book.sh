#!/usr/bin/env bash
#
# Full-book run: render every page of a PDF, then run each OCR/VLM model over the whole book
# sequentially, with per-step and total timing. Built for an unattended (overnight) run — it does
# NOT abort if one model fails; it logs the failure and moves on, then prints a summary.
#
# Usage:
#   scripts/run_full_book.sh <book-slug> <pdf-path> [dpi]
#
# To keep the machine awake for the whole run, wrap it with systemd-inhibit:
#   systemd-inhibit --what=sleep:idle --why="scriptorium full run" \
#     scripts/run_full_book.sh mindblast "books/input/<file>.pdf"
#
# Artifacts land under books/output/<book>/ (gitignored): pages/ and runs/<run-id>/, plus a log.

set -uo pipefail  # deliberately NOT -e: continue past a failing model and report at the end.

BOOK="${1:?usage: run_full_book.sh <book-slug> <pdf-path> [dpi]}"
PDF="${2:?usage: run_full_book.sh <book-slug> <pdf-path> [dpi]}"
DPI="${3:-300}"

OUT_ROOT="books/output"
PAGES_DIR="$OUT_ROOT/$BOOK/pages"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$OUT_ROOT/$BOOK/full-run-$STAMP.log"
mkdir -p "$OUT_ROOT/$BOOK"

# name<TAB>duration_s<TAB>exit_code, one line per step — used to print the summary at the end.
SUMMARY="$(mktemp)"
trap 'rm -f "$SUMMARY"' EXIT

log() { echo "$@" | tee -a "$LOG"; }

human() {  # seconds -> "1h 02m 03s"
    local s=$1
    printf '%dh %02dm %02ds' $((s / 3600)) $(((s % 3600) / 60)) $((s % 60))
}

run_step() {  # <name> <command...>
    local name="$1"; shift
    local start end dur rc
    log ""
    log "=== [$(date -u +%H:%M:%S)Z] START  $name"
    log "    \$ $*"
    start=$(date +%s)
    "$@" >>"$LOG" 2>&1
    rc=$?
    end=$(date +%s); dur=$((end - start))
    if [ "$rc" -eq 0 ]; then
        log "=== [$(date -u +%H:%M:%S)Z] OK     $name  ($(human "$dur"))"
    else
        log "=== [$(date -u +%H:%M:%S)Z] FAIL   $name  ($(human "$dur"), exit $rc)"
    fi
    printf '%s\t%s\t%s\n' "$name" "$dur" "$rc" >>"$SUMMARY"
}

overall_start=$(date +%s)
log "Full-book run: book=$BOOK pdf=$PDF dpi=$DPI"
log "Log: $LOG"

# 1) Render every page (auto-detect page count from the PDF).
PAGE_COUNT="$(uv run python -c "import pymupdf,sys; print(pymupdf.open(sys.argv[1]).page_count)" "$PDF")"
log "Page count: $PAGE_COUNT"
run_step "extract_pages" \
    uv run scripts/extract_pages.py --pdf "$PDF" --pages "1-$PAGE_COUNT" --out "$PAGES_DIR" --dpi "$DPI"

# 2) Each model over the whole book (label 'full' to distinguish from the 9-page 'baseline' runs).
run_step "surya"     uv run scripts/run_surya.py     --book "$BOOK" --label full
run_step "unlimited" uv run scripts/run_unlimited.py --book "$BOOK" --label full
run_step "qwen3vl"   uv run scripts/run_qwen3vl.py   --book "$BOOK" --label full
# GLM-OCR needs transformers 5.x, isolated so the project env stays at 4.57.6 for the others.
run_step "glm-ocr"   uv run --with "transformers==5.12.1" scripts/run_glm_ocr.py --book "$BOOK" --label full
# Gemma 4 E4B is intentionally NOT run: it fabricates dense body text and would poison the
# consensus — see docs/experiments/2026-06-26-gemma-vision-failure.md (scripts/run_gemma.py kept
# only as the reproducible artifact behind that finding).

# Summary.
overall_dur=$(( $(date +%s) - overall_start ))
log ""
log "==================== SUMMARY ===================="
printf '%-14s %-7s %s\n' "step" "status" "duration" | tee -a "$LOG"
failed=0
while IFS=$'\t' read -r name dur rc; do
    if [ "$rc" -eq 0 ]; then status="OK"; else status="FAIL($rc)"; failed=$((failed + 1)); fi
    printf '%-14s %-7s %s\n' "$name" "$status" "$(human "$dur")" | tee -a "$LOG"
done <"$SUMMARY"
log "-------------------------------------------------"
log "TOTAL $(human "$overall_dur")  |  failures: $failed"

[ "$failed" -eq 0 ]
