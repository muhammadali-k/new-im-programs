# Visa sponsorship — sources and rules

The tracker is built for visa-needing (IMG) applicants, so every program carries a
`visa_sponsorship` value. This file documents how to determine it honestly.

## Why this is hard
ADS does **not** publish visa sponsorship. Brand-new programs are the worst case: thin
websites, not yet in every aggregator, no alumni to ask. So many programs legitimately end
up **Unknown** — that is the correct, honest default, **not** a failure. Do not infer J-1
from base rates even though most US IM programs do sponsor it; a label needs a cited source.

## Source hierarchy (most to least authoritative)
1. **Program's own website** — the "eligibility", "how to apply", "international applicants",
   or "prerequisites" page. A program stating its own policy is `confidence: high`.
2. **AMA FREIDA** (`freida.ama-assn.org`) — has a structured "Visas Accepted: J-1 / H-1B"
   field. `confidence: medium`.
3. **ECFMG / EVSP** — ECFMG is the J-1 sponsor of record for residency; its context can
   confirm J-1 eligibility but not H-1B. `confidence: medium`.
4. **Other** (AAMC/MyERAS program notes, credible news) — `confidence: low`.

Prefer the program's own statement; note when only an aggregator supports a label.

## Labels
- `J-1+H-1B` — a source confirms BOTH are sponsored.
- `J-1` — J-1 supported; H-1B not mentioned or explicitly not offered (the common case).
- `H-1B-only` — H-1B supported and J-1 explicitly NOT offered (rare).
- `None` — a source **explicitly** says no visa sponsorship / must be authorized to work in
  the US / US citizens or permanent residents only. High-stakes: require an explicit
  statement, because this de-emphasizes the program.
- `Unknown` — nothing explicit found. The default.

## Verification (high-stakes verdicts)
Re-verify every `None`, `H-1B-only`, and `J-1+H-1B` before trusting it, adversarially:
- `None` unconfirmed by an explicit no-sponsorship statement → downgrade to `Unknown`
  (never de-emphasize a program on weak evidence).
- `J-1+H-1B` with H-1B unconfirmable → downgrade to `J-1` (or `Unknown`).
- `H-1B-only` where J-1 is actually sponsored → `J-1+H-1B`.

## Presentation rules (see render_html.py)
- **Confirmed sponsors** (J-1 / J-1+H-1B / H-1B-only) — the main apply-now section.
- **Unknown — verify directly** — separate section; explicitly framed as "verify", not
  "rejected", since silence ≠ no sponsorship.
- **Not for visa applicants** (`None`) — kept but de-emphasized.
- Every non-Unknown label stores `visa_evidence` (source + url + short quote) and a
  `visa_confidence`; the HTML badge links to the source and shows a confidence dot.
- Always tell the user to re-confirm in MyERAS/FREIDA before paying a fee or spending a
  program signal. Never fabricate a quote or URL.
