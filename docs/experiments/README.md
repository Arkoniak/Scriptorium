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
