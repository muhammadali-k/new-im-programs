# New Internal Medicine Residency Program Tracker — Visa Sponsorship

A sortable, filterable tracker of **newly ACGME-accredited categorical Internal Medicine
residency programs** in the United States, **grouped by visa sponsorship** — built for a
visa-needing IMG applicant who wants to catch brand-new ("first-class") programs early, since
they cast a wider net and tend to be more IMG-friendly.

**Live tracker:** https://muhammadali-k.github.io/new-im-programs/

## What it tracks
The primary axis is **visa sponsorship**. Each program is labelled and sorted into three
sections:

| Section | Meaning |
|---|---|
| ✅ **Confirmed visa sponsors** | A source confirms `J-1`, `J-1+H-1B`, or `H-1B-only` sponsorship. Your apply-now set. |
| ❓ **Visa status unknown** | No website/FREIDA/ECFMG source confirmed a policy. *Not* a rejection list — website silence ≠ no sponsorship; verify directly. |
| 🚫 **Not for visa applicants** | A source states US citizens / permanent residents only. Kept, de-emphasized. |

Within each section a program keeps its **newness tier**, based on its original ACGME
accreditation date (re-anchored to the run date each update):

| Tier | Meaning |
|---|---|
| `apply-now-first-class` | Initial Accreditation within the last 12 months — likely still filling its first class |
| `apply-now-still-new` | Initial Accreditation in the 12–24 month band |
| `watchlist-preaccreditation` | Pre-Accreditation / Applicant for Initial — not yet recruitable |

Programs that pass 24 months since accreditation age out of the list.

## Visa data & honesty
Accreditation is from ACGME ADS (authoritative). **Visa** status is best-effort, gathered
from each program's website plus AMA FREIDA and ECFMG — websites are often silent, so every
non-`Unknown` label carries a clickable source and a confidence dot, and anything unconfirmed
is honestly left `Unknown` (never guessed). **Always re-confirm visa sponsorship in
MyERAS/FREIDA before paying a fee or spending a program signal.** See
`skill/references/visa-sources.md`.

## Data source
The **only** authoritative source is the ACGME Accreditation Data System (ADS,
`apps.acgme.org`). Everything shown in the tracker comes from ADS Report 8 (newly
accredited programs, per academic year) and Report 1 (pre-accreditation watchlist).
Commercial trackers, FREIDA, and social media are used only as human-checked leads, never
as authoritative data.

## Files
- `index.html` — the rendered tracker (served by GitHub Pages)
- `programs.json` — the underlying data (schema documented in `skill/SKILL.md`)
- `skill/` — the Claude Code skill that fetches ADS, diffs against the cache, and renders
  the HTML. Fully reproducible.

## How it updates
The `new-im-programs` Claude Code skill runs (on a daily schedule) to:
1. Fetch the apply-now set from ADS Report 8 across the academic years overlapping the last
   24 months, and the pre-accreditation watchlist from Report 1.
2. Diff against `programs.json` (preserving `first_seen`), flagging new and status-changed
   programs and anything that aged out.
3. Re-render `index.html` and publish to this repo (see `skill/scripts/publish.sh`).

## Honesty note
"New programs are easier to match into" is presented as **practitioner consensus**, not
proven fact. Real risks apply: you are the test class, possible program-director turnover,
an upcoming first ACGME site visit, and any "with Warning" flag. Where ADS does not list a
field (e.g. visa sponsorship), it is recorded as `"unknown"` — never guessed.
