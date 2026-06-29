# Experiment log index

One row per entry in this directory. Keep rows to one line — the entry file is where the
narrative lives. See `.claude/skills/experiments/SKILL.md` for conventions.

| Date | Question | Outcome | Link |
|------|----------|---------|------|
| 2026-06-25 | Surya 2 baseline on a real scan (9 pages, 12GB, no docker) | Body text flawless @ 6.4s/page; errors only on stylized cover logos; layout labels a bonus | [surya-baseline](2026-06-25-surya-baseline.md) |
| 2026-06-25 | Unlimited-OCR baseline + head-to-head vs Surya (same 9 pages) | 5.16s/page; complementary errors on stylized logos (consensus signal); extracts figure rasters; has grounding (corrects brainstorm) | [unlimited-baseline](2026-06-25-unlimited-baseline.md) |
| 2026-06-26 | Unlimited-OCR grounding mode: capture boxes as data + does it keep inline markup? | Grounding gives structured text+label+bbox per block; but Unlimited drops inline emphasis under every prompt (Surya keeps it via HTML) | [unlimited-grounding](2026-06-26-unlimited-grounding.md) |
| 2026-06-26 | Qwen3-VL-8B (general VLM) as 3rd model: competitive? keeps emphasis? | 8.5s/page; preserves inline emphasis (where Unlimited failed); best on stylized logos; no figures/bbox; gives ROVER its 3rd independent lineage | [qwen3vl-baseline](2026-06-26-qwen3vl-baseline.md) |
| 2026-06-26 | GLM-OCR (0.9B) as 4th model: does tiny compete? | Fastest (3.9s/page), accurate incl. front-cover logo, de-hyphenates — but drops inline emphasis. Pattern: OCR-specialists drop emphasis, general/HTML models keep it. Needs transformers 5.x (isolated via uv --with) | [glm-ocr-baseline](2026-06-26-glm-ocr-baseline.md) |
| 2026-06-26 | Gemma 4 E4B as 5th model: usable for dense scans? | No — **excluded**. Default vision res too low → fabricates body; raising it crashes (ubatch), then loops, then fabricates fluently. Fabrication would poison consensus. 4 working models kept | [gemma-vision-failure](2026-06-26-gemma-vision-failure.md) |
| 2026-06-26 | PaddleOCR-VL (OmniDocBench #1, multilingual) as 5th model? | **Deferred** — transformers integration is a version swamp (remote-code crashes on 4.57.6 and 5.x; native arch ~454s/page). Runtime problem, not quality. Revisit via vLLM later | [paddleocr-vl-deferred](2026-06-26-paddleocr-vl-deferred.md) |
| 2026-06-27 | Consensus across the 4 models (alignment-first ROVER) on the full book | 98.4% agreement; 83% of disagreements are header-omission noise, 17% real — and 3:1 voting fixes single-model misreads (prytool>pyytool). Surya least divergent | [consensus-rover](2026-06-27-consensus-rover.md) |
| 2026-06-29 | Manual audit of Surya's content disagreements vs consensus — spell-checker bias? | Surya wrong in 8/11 real divergences; pattern is spell-checker normalization (neologisms, original typos, broken English). 50/50 tie bias (Surya wins by position) unquantified | [surya-spell-checker-bias](2026-06-29-surya-spell-checker-bias.md) |
