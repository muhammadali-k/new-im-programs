# Cloud routine — "New IM programs — daily 8 AM e-mail"

Created 2026-09-02 via the Claude Code remote-trigger API. Re-create with the same values if
it is ever deleted (routines are managed at https://claude.ai/code/routines).

| Setting | Value |
|---|---|
| Name | New IM programs — daily 8 AM e-mail |
| Schedule | `0 15 * * *` (UTC) = **08:00 America/Phoenix every day** (no DST in Arizona, so it never drifts) |
| Model | `claude-opus-4-8` |
| Environment | Default Anthropic cloud (`env_01UnLGxvEXW88TxLRLjxDq6T`) — *Network access must be **Full*** (apps.acgme.org is not on the "Trusted" allowlist) |
| Repository | https://github.com/muhammadali-k/new-im-programs (the tracker repo; the skill is vendored at `skill/`, data at `programs.json`, site at `index.html`) |
| Connectors | Gmail (permitted: `send_message`, `create_draft`) |
| Routine id | `trig_01QghpE8XFETcv8NZFn9cWPf` |

## What the run does (all deterministic scripts; the model only orchestrates + e-mails)
1. `bash skill/scripts/daily_run.sh .` → `fetch_ads.py` (≈7 throttled HTTP requests: ADS Report 8 for each
   academic year in the 24-month window + Report 1 with pre-accreditation rows) → `update_programs.py`
   (diff against `programs.json`, preserve visa labels + `first_seen`, enrich city/phone/email from Report 1)
   → `render_html.py` (`new-im-programs.html`) → `digest.py` (`runs/digest_<date>.{html,txt,subject}`).
2. E-mail the digest to **kmuhammadali0224@gmail.com** via the Gmail connector — every day, including
   "0 new" days (one-line summary + tracker counts).
3. Copy `new-im-programs.html` → `index.html`, commit `programs.json`, `index.html`, `runs/` and push to
   `main` (GitHub Pages refreshes the live tracker at https://muhammadali-k.github.io/new-im-programs/).

Visa lookups for brand-new programs are **not** done by the routine (they need ~60 web lookups and
human-checked quotes). New programs arrive labelled `Unknown`; run `/new-im-programs` locally to
research and label them (Step 5 of SKILL.md), which then persists through subsequent routine runs.

## Prompt (verbatim)

```
You are running the daily scan of the `new-im-programs` skill. The repository (muhammadali-k/new-im-programs) is checked out at the working directory: the skill lives in `skill/` (read `skill/SKILL.md` §"Daily 8 AM e-mail" and `skill/ROUTINE.md` first), the data is `programs.json`, and the published tracker is `index.html`.

Goal: refresh the list of newly ACGME-accredited categorical Internal Medicine residency programs from ACGME ADS, e-mail the applicant what changed since yesterday, and publish the refreshed tracker. Every step is a script; do not re-implement any of it.

Steps — do all of them, in order:
1. `export RUN_DATE=$(TZ=America/Phoenix date +%F)` and `git pull --ff-only origin main || true`.
2. `bash skill/scripts/daily_run.sh .` — it fetches ADS (a handful of throttled report requests), merges into `programs.json`, renders `new-im-programs.html`, and writes `runs/digest_$RUN_DATE.html`, `runs/digest_$RUN_DATE.txt`, `runs/digest_$RUN_DATE.subject`. Read its output. Exit code 2 means the ADS fetch failed and `programs.json` was deliberately left untouched — still continue (the digest says so).
3. E-mail the digest with the Gmail connector's send_message tool (load it with ToolSearch `select:mcp__Gmail__send_message` if needed): to `kmuhammadali0224@gmail.com`, subject = the contents of `runs/digest_$RUN_DATE.subject`, body = the contents of `runs/digest_$RUN_DATE.html` sent as HTML (fall back to the `.txt` as plain text only if HTML is refused). Send it verbatim — never add programs, dates, or visa claims that are not in the file. Send even when it says 0 new.
4. Publish: `cp new-im-programs.html index.html && git config user.email noreply@anthropic.com && git config user.name Claude && git add programs.json index.html new-im-programs.html runs/ && git commit -m "Daily scan $RUN_DATE: <subject line>" && git push origin HEAD:main`. If nothing changed, `git commit` will say so — that is fine. Never force-push; never edit files under `skill/`. If the push is refused (403), say so in the run note; do not retry.
5. Final message: paste `runs/digest_$RUN_DATE.txt` verbatim, then a run note: fetch result line from daily_run.sh, whether the e-mail send succeeded (quote the tool result) and whether the push succeeded. If Gmail refused, say so plainly — do not claim delivery.

Rules: accreditation facts come only from ACGME ADS via the scripts; never invent programs, dates, or visa sponsorship; do not browse program websites or FREIDA in this run (visa research is done separately from the laptop). If `daily_run.sh` fails before the digest exists, e-mail a short plain-text failure notice with the error output instead, subject "New IM programs — $RUN_DATE: run FAILED". The applicant is a non-US IMG applying Internal Medicine in ERAS 2027 who needs visa sponsorship.
```

## Test run 2026-09-02 (session cse_01742M2vXgYn5woJCX2EytEH)
- **Worked:** clone, scripts, failure handling (exit 2 → `programs.json` untouched, digest says "fetch FAILED"),
  **Gmail send succeeded** (message id 1a060efc429e1c72 to kmuhammadali0224@gmail.com), push notification.
- **Blocked (user must fix, same two items as the im-open-houses routine):**
  1. `apps.acgme.org` refused by the cloud egress proxy ("Tunnel connection failed: 403"). Fix: claude.ai/code →
     Environments → Default → *Network access* = **Full**. Until then every morning's e-mail will say "fetch FAILED".
  2. `git push` refused (403, "Claude doesn't have GitHub access to muhammadali-k/new-im-programs"). Fix: install the
     Claude GitHub App for the `muhammadali-k` account with access to this repo
     (https://github.com/apps/claude/installations/select_target) or reconnect GitHub at
     https://claude.ai/customize/connectors?auth_start=github. Until then the tracker site only refreshes from the
     laptop (`publish.sh`) and a new program is re-reported as "new" each morning.

## Notes
- Run history: https://claude.ai/code/routines/trig_01QghpE8XFETcv8NZFn9cWPf; each run is a session the user can open.
- To run it now: `/schedule` → Run, or RemoteTrigger `{action:"run", trigger_id:"trig_01QghpE8XFETcv8NZFn9cWPf"}`.
- The same pipeline runs locally with `bash ~/.claude/skills/new-im-programs/scripts/daily_run.sh`
  (writes to the Dropbox output folder) followed by `scripts/publish.sh`.
- Known cloud-environment prerequisites (same as the im-open-houses routine): network access **Full**,
  and the Claude GitHub App installed for `muhammadali-k/new-im-programs` so the push is accepted.
  If the push is refused, the tracker/site still updates on the next local `publish.sh`; the e-mail is
  unaffected, but a new program will be re-reported as "new" each morning until the state is pushed.

Routine id: `trig_01QghpE8XFETcv8NZFn9cWPf`
