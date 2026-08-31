# Secondary / lead sources — use to catch programs early, then VERIFY against ADS

None of these is authoritative. Every credible "new program" list ultimately derives from
ACGME ADS. Treat the sources below as *leads*: if one surfaces a program, confirm it on the
ADS Detail page (status + original accreditation date) before adding it to `programs.json`.
The HTML tracker's data comes from ADS only.

| Source | Value | How to use | Caution |
|---|---|---|---|
| **FREIDA** (freida.ama-assn.org) | Application/contact/size detail once a program exists | Enrichment only; JS-only shell (needs a browser), batch-updated Aug/Oct/Feb | No "new" flag; brand-new programs often missing entirely |
| **X/Twitter** IMG accounts (e.g. @imghelpinghand) | Occasionally post accurate "new IM programs 20XX-XX" lists | Human-skim for leads | Paywalled API; unverified; verify each against ADS |
| **Reddit** r/IMGreddit, r/Residency, r/medicalschool | Crowd-sourced Google Sheets of new/IMG-friendly programs | Human-skim for leads | Ephemeral, self-reported, frequently inaccurate |
| **NRMP** | Confirms a program participates in the Match | Confirmatory | No public new-program roster; login-gated |
| **ERAS / ResidencyExplorer** | Established-program comparison | Not for discovery | Login-gated; new programs sparse/absent |
| **acgmecloud.org** ("Explore Public Data") | Possible sanctioned/cleaner ADS alternative | Worth evaluating as a primary path | Verify it returns the same status/date fields before relying on it |

Rule of thumb: **signal = ADS** (and FREIDA for enrichment); everything else is a lead to
confirm, not a source to trust.
