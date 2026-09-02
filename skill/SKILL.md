---
name: new-im-programs
description: >-
  Fetch newly ACGME-accredited Internal Medicine residency programs from the
  authoritative ACGME ADS public data system and produce a sortable, filterable
  HTML tracker of them. Use this WHENEVER the user asks about new / newly
  accredited / brand-new IM (internal medicine) residency programs, "which new
  programs can I apply to", checking for new residency programs this cycle,
  tracking programs that just got ACGME accreditation, or invokes
  /new-im-programs — even if they don't name the skill. Built for an IMG
  applicant who wants to catch first-class programs early (they cast a wider net
  and are more IMG-friendly). Pulls Initial-Accreditation programs (apply-now)
  plus a pre-accreditation watchlist, classifies each by newness, tracks what's
  changed since the last run, and renders an HTML file. A cloud routine runs the
  headless version every day at 8 AM (America/Phoenix) and e-mails the digest to
  kmuhammadali0224@gmail.com (config in ROUTINE.md). Do NOT use for
  established-program comparison, non-IM specialties, or general residency advice.
---

# New Internal Medicine Residency Program Tracker

## What this does
Finds **newly ACGME-accredited categorical Internal Medicine residency programs** and
renders a sortable/filterable HTML tracker **grouped by visa sponsorship**. New programs
are a strategic edge for an applicant (especially an IMG): they fill a first class from
scratch, interview more broadly, skew community/hospital (the most IMG-friendly type), and
often launch with no published USMLE cutoff.

Because the user is a **visa-needing IMG applicant**, the tracker's primary axis is visa
sponsorship. Each program is labelled `J-1`, `J-1+H-1B`, `H-1B-only`, `None`, or `Unknown`
and sorted into three sections: **Confirmed sponsors** (apply-now), **Unknown — verify
directly** (silence ≠ no sponsorship — most IM programs sponsor J-1), and **Not for visa
applicants** (confirmed non-sponsors, de-emphasized). Visa determination and its honesty
rules live in **`references/visa-sources.md`**.

The **only** authoritative data source is the ACGME Accreditation Data System (ADS).
Everything else (FREIDA, Reddit, X/Twitter, commercial trackers) is a lagging copy — use
those as human-checked *leads only*, always verified against ADS. See
`references/lead-sources.md`.

## Access method: browser-assisted (important)
ADS's `robots.txt` asks automated agents not to crawl the site, and a reCAPTCHA is wired
in (currently dormant). So fetch the data the way a person would: **drive a real browser**
(the in-app Browser tools, `mcp__Claude_Browser__*`) to open the public ADS pages, read
the rendered tables, and open detail pages only for the programs that are actually new.
This keeps the footprint tiny (one report + a few dozen detail pages at most) and handles
the CAPTCHA naturally if it turns on. Do **not** write a bulk `curl`/`requests` scraper.

All ADS endpoints, the Internal Medicine specialty codes, the exact fields to extract, and
the tier/date logic are in **`references/acgme-ads.md` — read it before fetching.**

## Two ways to run it
| Mode | When | What |
|---|---|---|
| **Daily 8 AM e-mail** (cloud routine, automatic) | every day 08:00 America/Phoenix | `scripts/daily_run.sh` — headless ADS report fetch → diff → render → digest → **e-mail to kmuhammadali0224@gmail.com** → push to the tracker repo. Config + prompt in `ROUTINE.md`. |
| **Full local run** (`/new-im-programs`) | on request, or when the e-mail reports new programs | the Workflow below: browser-assisted enrichment + **visa research** (Step 5) for anything still `Unknown`, then render + publish. |

The daily run uses `scripts/fetch_ads.py`, which POSTs the same two report forms a person would
(Report 8 per academic year + Report 1) and parses the returned PDFs — about seven throttled
requests, no crawling, no detail-page scraping. It is what keeps the tracker and the e-mail current;
the local workflow is what adds visa labels and detail-page enrichment. Both share `programs.json`.

## Workflow

1. **Set the run date and windows.** Today's date anchors everything. Compute:
   - `new_cutoff = today − 24 months` (original accreditation effective date on/after this = "new")
   - `first_class_cutoff = today − 12 months` (on/after this = likely still filling first class)
   These re-anchor automatically every run, so the skill stays correct across cycles.

2. **Fetch the apply-now set (Report 8).** Shortcut: `python3 scripts/fetch_ads.py --out snap.json`
   does Steps 2–3 headlessly (then `scripts/update_programs.py snap.json programs.json --run-date <today>`
   does Step 7) — use the browser route below only if the headless fetch errors. These reports return a **PDF**, not an HTML table —
   read `references/acgme-ads.md` §"Report mechanics" first; it's the step naive runs get wrong.
   In the browser open ADS **Report 8**, set **Specialty = Internal medicine** via the Select2
   dropdown (setting the raw select submits empty), pick an **Academic Year**, submit, and parse
   the returned PDF. Report 8 is **one academic year per run**, so **loop** the AYs overlapping
   the 24-month window (usually the last three) and union them. Each PDF row gives org code,
   program name, state, program director, and the **original accreditation date** (the newness key).

3. **Fetch the watchlist (Report 1).** Open ADS **Report 1**, set Internal medicine, enable
   **"Include Pre-Accreditation status"**, submit, parse the PDF. Capture Pre-Accreditation /
   Applicant-for-Initial programs (often **zero** — that's normal). Do not use Report 1's
   "Effective Date" as the accreditation date (it can be a warning-action date).

4. **Enrich (optional polish, throttle!).** Core fields already come from the Report 8 PDF. For
   the programs you want richer data on (apply-now first), open **Detail** pages — but mind the
   session gate: first POST the Program Search form (`specialtyId=18` + token) in the same
   session, *then* `Detail?orgCode=...&ReturnUrl=x` works (a bare GET returns a "please return to
   search" stub). Throttle (~1 req/1-2 s, small batches) or ADS soft-throttles. Extract the
   enrichment fields in `references/acgme-ads.md` §Fields (positions, sponsor, city, PD-appointed
   date, coordinator email, website, phone, length, next site visit). ADS never lists visa —
   that comes from Step 5.

5. **Determine visa sponsorship (the primary axis — read `references/visa-sources.md`).**
   For **every** program, determine whether it sponsors visas, from the source hierarchy:
   the program's own website (eligibility / how-to-apply / international page) → **AMA
   FREIDA**'s structured "Visas Accepted" field → **ECFMG/EVSP** (J-1 sponsor of record).
   Assign `visa_sponsorship` ∈ {`J-1`, `J-1+H-1B`, `H-1B-only`, `None`, `Unknown`} and store
   `visa_confidence` + `visa_evidence` (source, url, short quote). **Only label with a cited
   quote; default to `Unknown` otherwise — never infer J-1 from base rates.** Adversarially
   re-verify every `None` / `H-1B-only` / `J-1+H-1B` before trusting it (downgrade rules in
   the reference). Because this means ~60+ web lookups, run it as a **Workflow** (batched
   research agents + a verify pass over the flagged verdicts), then merge:
   ```bash
   python3 ~/.claude/skills/new-im-programs/scripts/merge_visa.py <output_dir>/programs.json <visa_results.json> <today>
   ```
   Cache: only (re)check programs that are new or still `Unknown`; carry forward confirmed
   labels with their `visa_checked_date`.

6. **Classify each program into a tier** (newness — the secondary axis; see reference):
   - `apply-now-first-class` — Initial Accreditation, original accreditation date ≥ first_class_cutoff
   - `apply-now-still-new` — Initial Accreditation, original accreditation date in the 12–24 mo band
   - `watchlist-preaccreditation` — Pre-Accreditation / Applicant for Initial (not yet recruitable)
   Drop anything with `Continued Accreditation` (aged out) unless the user asked for "everything recent".
   The renderer groups by **visa** first, then shows this tier badge within each visa section.

7. **Diff against the cache.** Load `programs.json` from the output folder if it exists.
   Preserve each program's `first_seen` (and any still-valid `visa_*` fields); set
   `last_seen = today`. Mark `is_new_since_last_run = true` for org codes not present last
   run, and note any status changes (e.g., pre-accreditation → initial, or a visa label that
   changed). Report the count of new programs since the last run to the user.

8. **Write outputs.** Save the updated `programs.json` and run the renderer:
   ```bash
   python3 ~/.claude/skills/new-im-programs/scripts/render_html.py <output_dir>/programs.json <output_dir>/new-im-programs.html
   ```
   Default `<output_dir>`: `~/Library/CloudStorage/Dropbox/IM-Residency-New-Programs/`
   (create it if missing). Then surface `new-im-programs.html` to the user (SendUserFile)
   and offer to publish it as a shareable Artifact.

9. **Publish to GitHub (live tracker).** The tracker is hosted on GitHub Pages at
   **https://muhammadali-k.github.io/new-im-programs/** (repo `muhammadali-k/new-im-programs`,
   local clone at `~/Projects/new-im-programs`). After rendering, push the refreshed
   tracker + data + skill source:
   ```bash
   bash ~/.claude/skills/new-im-programs/scripts/publish.sh
   ```
   The script copies `new-im-programs.html` → `index.html`, copies `programs.json`, syncs the
   skill into `skill/`, then commits and pushes **only if something changed** (no-op on a
   quiet day). If the clone is missing it prints the `gh repo clone` command to recreate it.
   On a scheduled/no-change run this is a safe no-op — still run it so the site stays live.

## Daily 8 AM e-mail (cloud routine)
A cloud routine ("New IM programs — daily 8 AM e-mail", `0 15 * * *` UTC = 08:00 America/Phoenix,
model `claude-opus-4-8`, Gmail connector, repo `muhammadali-k/new-im-programs`) runs
`scripts/daily_run.sh` every morning and e-mails the digest to **kmuhammadali0224@gmail.com** —
also on days with **0 new** (a one-liner plus tracker counts, so silence never means "broken").
Exact configuration and the verbatim prompt are in **`ROUTINE.md`**; re-create from there if deleted.

What the e-mail contains: every program newly accredited since the previous run (name, city/state,
accreditation date + tier, PD, coordinator contact from ADS, ADS detail link, visa = `Unknown` until
researched), status/PD/tier changes, programs that aged out or were withdrawn, and the tracker
counts. When it reports new programs, run `/new-im-programs` locally to research their visa
sponsorship (Step 5) — the labels persist through later routine runs.

Run the same pipeline locally at any time:
```bash
bash ~/.claude/skills/new-im-programs/scripts/daily_run.sh          # → Dropbox output folder + runs/digest_<date>.*
bash ~/.claude/skills/new-im-programs/scripts/publish.sh            # → GitHub Pages
```
`daily_run.sh` exits 2 (and leaves `programs.json` untouched) if ADS could not be fetched; the digest
then says the run failed rather than reporting a suspicious "0 programs".

## Scripts
| Script | Role |
|---|---|
| `fetch_ads.py` | Headless ADS fetch (Report 8 × academic years + Report 1) → `ads_snapshot_<date>.json`. Needs `pypdf` (preferred) or `pdftotext`. |
| `update_programs.py` | Merge snapshot into `programs.json`; re-tier; preserve visa/enrichment; write `changes_<date>.json`. |
| `render_html.py` | `programs.json` → sortable/filterable tracker HTML grouped by visa. |
| `digest.py` | `changes_<date>.json` → e-mail digest (`.html`, `.txt`, `.subject`). |
| `daily_run.sh` | fetch → update → render → digest, in one command (used by the routine and locally). |
| `merge_visa.py` | Merge Workflow visa-research results into `programs.json` (local Step 5). |
| `publish.sh` | Copy tracker + data + skill into the GitHub Pages repo and push (local). |

## programs.json schema
```json
{
  "generated": "YYYY-MM-DD",
  "run_date": "YYYY-MM-DD",
  "source": "ACGME ADS (apps.acgme.org)",
  "specialty": "Internal Medicine (categorical)",
  "new_cutoff": "YYYY-MM-DD",
  "first_class_cutoff": "YYYY-MM-DD",
  "programs": [
    {
      "program_name": "", "org_code": "", "program_id": "",
      "sponsoring_institution": "", "city": "", "state": "",
      "accreditation_status": "", "original_accreditation_date": "YYYY-MM-DD",
      "effective_date": "YYYY-MM-DD", "approved_positions": null, "filled_positions": null,
      "length_of_training": "", "program_director": "", "pd_first_appointed": "",
      "coordinator_email": "", "program_website": "", "phone": "",
      "next_site_visit": "",
      "visa_sponsorship": "J-1|J-1+H-1B|H-1B-only|None|Unknown",
      "visa_confidence": "high|medium|low|",
      "visa_evidence": [{"source": "official-site|FREIDA|ECFMG|AAMC|other", "url": "", "quote": ""}],
      "visa_checked_date": "YYYY-MM-DD",
      "tier": "apply-now-first-class|apply-now-still-new|watchlist-preaccreditation",
      "detail_url": "", "history_url": "",
      "first_seen": "YYYY-MM-DD", "last_seen": "YYYY-MM-DD", "is_new_since_last_run": false
    }
  ]
}
```
The renderer only reads this file — keep the field names exact.

## Related skill
Once this skill surfaces the new programs, the natural next step is to **vet and rank
them into an apply list** — that's the `residency-program-finder` skill (website
verification, visa/roster checks, match tiering, program signals). This skill finds *what's
new*; that skill decides *where to apply*. Offer to hand off to it after generating the HTML.

## Honesty guardrails
- **Accreditation** data comes from **ADS only**. Lead sources are documented but never
  presented as authoritative.
- **Visa** data comes from program websites + FREIDA + ECFMG (Step 5). It is best-effort and
  often incomplete for brand-new programs. Every non-`Unknown` label must carry a cited
  `visa_evidence` quote+URL; if no source is found, the value stays `Unknown` — **never infer
  J-1 from base rates and never fabricate a quote**. `None` (which de-emphasizes a program)
  requires an *explicit* no-sponsorship statement, re-verified. Always tell the user to
  re-confirm visa status in MyERAS/FREIDA before paying a fee or spending a program signal.
- Frame the **Unknown** section as "verify directly," not "rejected" — website silence ≠ no
  sponsorship (most IM programs sponsor J-1).
- Present "new programs are easier to match into" as well-supported *practitioner
  consensus*, not proven fact, and surface the real risks (you are the test class, possible
  PD turnover, upcoming first site visit, any "with Warning" flag).
- If a field isn't on the ADS page, write `"unknown"` — do not fabricate.
