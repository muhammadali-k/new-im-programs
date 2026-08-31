# ACGME ADS — endpoints, codes, fields, and tier logic

Verified live end-to-end on 2026-08-29/30, **including corrections from a real fetch run**.
ADS is a server-rendered ASP.NET app. Drive it with a real browser (`mcp__Claude_Browser__*`);
do not write a bulk `curl`/`requests` scraper (robots.txt disallows automated agents, and a
dormant reCAPTCHA can turn on — a real browser session handles both).

## Endpoints
| Purpose | URL | Returns |
|---|---|---|
| Newly accredited programs report | `https://apps.acgme.org/ads/Public/Reports/Report/8` | form page → **PDF** |
| Programs roster report (pre-accreditation toggle) | `https://apps.acgme.org/ads/Public/Reports/Report/1` | form page → **PDF** |
| Report runner (the POST target both reports submit to) | `https://apps.acgme.org/ads/Public/Reports/ReportRun` | **PDF stream** |
| Program search | `https://apps.acgme.org/ads/Public/Programs/Search` | HTML list |
| Program detail (enrichment fields live here) | `https://apps.acgme.org/ads/Public/Programs/Detail?orgCode={10-digit}` | HTML (gated — see below) |

## Internal Medicine codes (categorical)
- `specialtyId = 18` — the value the **Program Search** form uses.
- `SpecialtyCode = 140` — the value the **Report** forms use; also the 3-digit prefix of every
  IM program's 10-digit orgCode (e.g. `1403400002`).
- The rest of the orgCode is a program sequence, **not** a state code — do **not** infer state
  from it (verified counterexamples: `1403800001/2/3/4` → WV/PA/OH/OH). Read the **State column**
  from the report/detail instead.
- (Out of scope here: Med-Peds `specialtyId=113` / prefix `700`.)

## Report mechanics — IMPORTANT (this is where a naive run fails)
The reports are **NOT HTML DataTables grids.** Clicking "View Report" POSTs the form to
`/ads/Public/Reports/ReportRun`, which **streams a PDF**. `read_page`/`get_page_text` come back
empty or show a PDF-render error. So:

1. **Navigate** to Report 8 (or Report 1). This loads the form and establishes the session.
2. **Set Specialty via the real dropdown.** `SpecialtyCode` is a **Select2 cascade** — setting
   the native `<select>` with `form_input` submits *empty* and `ReportRun` 404s. Open the Select2
   control and pick "Internal medicine" (140) through the UI, or set the value **and fire its
   `change` event**. On Report 8 also pick the **Academic Year** (see next point); on Report 1
   tick **Include Pre-Accreditation status**.
3. **Report 8 is one academic year per run** — there is no multi-year select. **Loop** the
   academic years overlapping your 24-month window (typically the last three: e.g. 2024-2025,
   2025-2026, 2026-2027) and union the results.
4. **Submit and capture the PDF.** Either click View Report and read the resulting PDF, or POST
   the form from the page (`ReportId`, `SpecialtyCode=140`, `AcademicYearName=YYYY-YYYY` /
   `IncludePreAccreditation=true`, `__RequestVerificationToken`) and read the PDF bytes. Parse the
   PDF text (in-browser you can inflate the FlateDecode streams via `DecompressionStream`; on
   disk, `pdftotext -layout` works). Each row gives **org code, program name, state, program
   director, and the accreditation date** — enough to build the list without any detail page.

The Report 8 PDF is the **authoritative list of newly accredited programs** and its date column
is the **original accreditation date** — key all newness decisions off it.

## Detail pages — the session unlock (also easy to get wrong)
A bare `GET Detail?orgCode=...` returns a **"Please return to the search page" stub (HTTP 200)**
even mid-session. The gate only opens after you **POST the Program Search form** in the same
session:
1. `navigate` to `Programs/Search`; grab the hidden `__RequestVerificationToken`.
2. POST the search with `specialtyId=18` (+ token). This sets a server-session flag.
3. Now `GET Detail?orgCode=...&ReturnUrl=x` returns the full page for the rest of the session.
Note: the "Search by Code" box does **not** accept the 10-digit orgCode — search by Specialty
(+ State) instead if you need to find a program interactively.

Only enrich detail pages for the programs you actually need (top-priority / apply-now first),
and **throttle** (~1 request / 1–2 s, small batches): after many rapid detail GETs ADS soft-
throttles to >10 s/response and large fetch batches hit the 45 s tool timeout. Core list fields
already come from the Report 8 PDF, so detail enrichment is optional polish (positions, contact,
PD-appointed date, website, next site visit).

## Fields to extract (ranked by usefulness to an applicant)
From the **Report 8 PDF** (all programs): program name, org code, **state**, program director,
**accreditation date** (= original accreditation date), status (all rows are Initial here).
From the **Detail** page (enrichment): **Accreditation Status** (Initial vs Initial-with-Warning
vs Continued vs Pre-Accreditation/Applicant vs Probationary/Withdrawn), **Original Accreditation
Date** + **Effective Date**, **Total Approved / Filled positions**, **Sponsoring Institution**
`[code] Name`, **city**, program director + **first-appointed** date, **coordinator email**,
**website**, **phone**, **length of training**, **next site visit (approx)**. Visa sponsorship is
rarely listed for new programs → record `"unknown"`, never guess.

## Newness / effective-date caveat
Use **Report 8's date** (= original accreditation date) or the Detail **Original Accreditation
Date** for the newness window. Do **NOT** use **Report 1's "Effective Date"** — for an
"Initial Accreditation with Warning" row that is the *status-action* (warning) date, which looks
recent even though the program is not newly accredited.

## Tier logic (anchored to run date `today`)
- `new_cutoff = today − 24 months`; `first_class_cutoff = today − 12 months`.
- **apply-now-first-class**: status ∈ {Initial Accreditation, Initial Accreditation with Warning}
  AND original accreditation date ≥ `first_class_cutoff`.
- **apply-now-still-new**: same status, date in [`new_cutoff`, `first_class_cutoff`).
- **watchlist-preaccreditation**: status ∈ {Pre-Accreditation, Applicant for Initial}. This tier
  is often **empty** (it was 0 IM programs on 2026-08-29) — that's normal, not a bug.
- **Exclude**: Continued Accreditation (aged out), Probationary/Withdrawn (adverse/exiting) —
  unless the user explicitly asks for "everything recent".

## Validation samples (a correct run must reproduce these)
```
# still-new anchor
1403400002  Three Crosses Regional Hospital Program — Internal medicine — Las Cruces, NM
  Accreditation Status: Initial Accreditation | Original/Effective: 2025-01-24
  Approved 24 / Filled 16 | 3 years | PD Ali Hassan, MD (first appointed 2025-01-24)
  Sponsoring: [340030] Three Crosses Regional Hospital | programId 58424

# first-class anchor (AY 2025-2026 path)
1400500023  University of California (Irvine)/Irvine Medical Center Program — CA
  Accreditation Status: Initial Accreditation | Original/Effective: 2025-09-12
  Approved 54 / Filled 17 | PD Maria Barsky, MD (first appointed 2025-09-12)
  Sponsoring: [050564] University of California (Irvine)
```
Expected national scale in a 24-month window: a few dozen Initial-Accreditation IM programs
(64 on 2026-08-29: 21 first-class + 43 still-new + 0 watchlist).
