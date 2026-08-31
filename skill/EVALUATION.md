# Evaluation — `new-im-programs`

End-to-end live test on **2026-08-29**: an independent agent, given only this skill, drove a
real browser against ACGME ADS and fetched newly-accredited categorical IM programs.

## Result: PASS
- **Fetch worked** via Report 8 (newly accredited) + Report 1 (pre-accreditation watchlist) +
  Program Search → Detail (enrichment). No CAPTCHA / WAF encountered.
- **64 Initial-Accreditation IM programs** in the 24-month window: **21 apply-now-first-class**,
  **43 apply-now-still-new**, **0 watchlist** (no IM program in Pre-Accreditation/Applicant
  status on that date — expected, not a failure).
- Report 1 roster cross-check (~680 IM programs): Initial 87, Continued 587, Probationary 2
  (excluded) — consistent with "a few dozen new."
- **Known-sample confirmed**: Three Crosses Regional Hospital (orgCode 1403400002, Las Cruces
  NM) present, still Initial Accreditation (2025-01-24), 24 approved / 16 filled — matches the
  reference exactly.

## Corrections the eval surfaced (all now folded into `references/acgme-ads.md`)
1. ADS reports return **PDFs** (POST `/ads/Public/Reports/ReportRun`), not HTML DataTables — the
   original doc said to read a grid with `read_page`. Report 8 is **one academic year per run**.
2. Detail pages need a **Search-POST session unlock** (specialtyId=18 + token) first; a bare GET
   returns a "please return to search" stub. The old "cookies ride along automatically" was wrong.
3. `SpecialtyCode` is a **Select2 cascade** — a raw `<select>` set submits empty (ReportRun 404).
4. The orgCode does **not** encode state — use the report/Detail State field (verified
   counterexamples).
5. **Effective-date ambiguity**: key newness off Report 8 / Detail "Original Accreditation Date";
   Report 1's Effective Date can be a status-action (warning) date.
6. **Soft-throttling** on bulk detail fetches → enrich in priority order, throttle, small batches.

Confirmed-good as written: specialty code 140 / specialtyId=18, the tier date-band logic, the
drop-Continued/Probationary/Withdrawn rule, the field ranking, and the known-good validation
sample (a second first-class anchor, UC Irvine, was added).

## Notes
- Core list fields (name, state, PD, accreditation date) come from the Report 8 PDF and are
  authoritative; per-program contact/positions/city are detail-page enrichment done in priority
  order (throttling makes enriching all 64 in one pass impractical — enrich apply-now first).
- The renderer (`scripts/render_html.py`) is unit-checked against a fixture and the live 64-row
  dataset.
