#!/usr/bin/env python3
"""Build the daily e-mail digest (HTML + plain text + subject) from a changes JSON
written by update_programs.py.

Usage:
    python3 digest.py <changes.json> <programs.json> --html out.html --text out.txt --subject out.subject
                      [--tracker-url URL]

The digest is honest by construction: when nothing changed it says so in one line and
lists what was checked. It never pads with "suggested" programs.
"""
import argparse
import html
import json
from pathlib import Path

TRACKER_URL = "https://muhammadali-k.github.io/new-im-programs/"
TIER_LABEL = {"apply-now-first-class": "first class — apply now",
              "apply-now-still-new": "still new (12–24 mo)",
              "watchlist-preaccreditation": "watchlist — pre-accreditation"}


def esc(s):
    return html.escape(str(s or ""))


def prog_line_html(n):
    bits = [f"<b>{esc(n['program_name'])}</b> — {esc(n.get('city') or '')}{', ' if n.get('city') else ''}{esc(n.get('state'))}"]
    bits.append(f"Accredited {esc(n.get('original_accreditation_date'))} · {esc(n.get('accreditation_status'))} · "
                f"<i>{esc(TIER_LABEL.get(n.get('tier'), n.get('tier')))}</i>")
    pd_ = n.get("program_director")
    if pd_:
        bits.append(f"PD: {esc(pd_)}")
    contact = " · ".join(x for x in (n.get("coordinator_email"), n.get("phone")) if x)
    if contact:
        bits.append(f"Contact: {esc(contact)}")
    bits.append(f"Visa: <b>{esc(n.get('visa_sponsorship') or 'Unknown')}</b> — verify on the program site / FREIDA before applying")
    bits.append(f'<a href="{esc(n.get("detail_url"))}">ADS detail</a> · org code {esc(n.get("org_code"))}')
    return "<br>".join(bits)


def prog_line_text(n):
    loc = ", ".join(x for x in (n.get("city"), n.get("state")) if x)
    s = [f"- {n['program_name']} — {loc}",
         f"  Accredited {n.get('original_accreditation_date')} · {n.get('accreditation_status')} · {TIER_LABEL.get(n.get('tier'), n.get('tier'))}"]
    if n.get("program_director"):
        s.append(f"  PD: {n['program_director']}")
    contact = " · ".join(x for x in (n.get("coordinator_email"), n.get("phone")) if x)
    if contact:
        s.append(f"  Contact: {contact}")
    s.append(f"  Visa: {n.get('visa_sponsorship') or 'Unknown'} — verify before applying")
    s.append(f"  {n.get('detail_url')}")
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("changes")
    ap.add_argument("programs")
    ap.add_argument("--html", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--tracker-url", default=TRACKER_URL)
    a = ap.parse_args()

    ch = json.loads(Path(a.changes).read_text())
    progs = json.loads(Path(a.programs).read_text()).get("programs", [])
    run = ch["run_date"]
    prev = ch.get("previous_run_date") or "—"
    c = ch.get("counts", {})
    tiers = c.get("tiers", {})
    visa = c.get("visa", {})
    n_new, n_rem, n_chg = len(ch.get("new", [])), len(ch.get("removed", [])), len(ch.get("changed", []))
    aborted = ch.get("aborted", False)
    errors = ch.get("fetch_errors", [])

    if aborted:
        subject = f"New IM programs — {run}: fetch FAILED (no update)"
    else:
        subject = f"New IM programs — {run}: {n_new} new" + (f", {n_rem} removed" if n_rem else "") + (f", {n_chg} changed" if n_chg else "")

    sponsors = sum(v for k, v in visa.items() if k in ("J-1", "J-1+H-1B", "H-1B-only"))
    first_class_sponsors = [p for p in progs if p.get("tier") == "apply-now-first-class"
                            and p.get("visa_sponsorship") in ("J-1", "J-1+H-1B", "H-1B-only")]

    # ---------------- HTML
    H = [f"<div style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.45;color:#222'>"]
    H.append(f"<h2 style='margin:0 0 6px'>Newly accredited Internal Medicine programs — {esc(run)}</h2>")
    H.append(f"<p style='margin:0 0 12px;color:#555'>Source: ACGME ADS, checked {esc(run)} (academic years {esc(', '.join(ch.get('academic_years', [])) or '—')}). "
             f"Previous run: {esc(prev)}. <a href='{esc(a.tracker_url)}'>Open the live tracker</a>.</p>")
    if aborted:
        H.append("<p style='color:#b00'><b>The ADS fetch failed, so the tracker was NOT updated today.</b></p>")
    elif n_new == 0:
        H.append("<p><b>No new IM programs since the last check.</b></p>")
    else:
        H.append(f"<h3 style='margin:14px 0 6px'>🆕 {n_new} new program{'s' if n_new != 1 else ''}</h3><ol>")
        for n in ch["new"]:
            H.append(f"<li style='margin-bottom:10px'>{prog_line_html(n)}</li>")
        H.append("</ol>")
    if n_chg:
        H.append(f"<h3 style='margin:14px 0 6px'>✏️ {n_chg} changed</h3><ul>")
        for x in ch["changed"]:
            d = "; ".join(f"{esc(dd['field'])}: {esc(dd['from'])} → {esc(dd['to'])}" for dd in x["diffs"])
            H.append(f"<li><b>{esc(x['program_name'])}</b> ({esc(x.get('state'))}): {d}</li>")
        H.append("</ul>")
    if n_rem:
        H.append(f"<h3 style='margin:14px 0 6px'>➖ {n_rem} dropped from the list</h3><ul>")
        for x in ch["removed"]:
            H.append(f"<li><b>{esc(x['program_name'])}</b> ({esc(x.get('state'))}) — {esc(x['reason'])}</li>")
        H.append("</ul>")
    if not aborted:
        H.append("<h3 style='margin:14px 0 6px'>📊 Tracker status</h3>")
        H.append("<table style='border-collapse:collapse;font-size:14px'>")
        rows = [("Programs tracked (accredited in last 24 mo)", c.get("total", len(progs))),
                ("First class — apply now", tiers.get("apply-now-first-class", 0)),
                ("Still new (12–24 months)", tiers.get("apply-now-still-new", 0)),
                ("Watchlist — pre-accreditation", tiers.get("watchlist-preaccreditation", 0)),
                ("Confirmed visa sponsors", sponsors),
                ("Visa unknown — verify", visa.get("Unknown", 0)),
                ("No visa sponsorship", visa.get("None", 0))]
        for k, v in rows:
            H.append(f"<tr><td style='padding:2px 12px 2px 0;color:#555'>{esc(k)}</td><td style='padding:2px 0'><b>{v}</b></td></tr>")
        H.append("</table>")
        if first_class_sponsors:
            H.append(f"<p style='margin:10px 0 4px;color:#555'>First-class programs with confirmed visa sponsorship ({len(first_class_sponsors)}):</p><ul style='margin-top:0'>")
            for p in sorted(first_class_sponsors, key=lambda p: p["program_name"]):
                H.append(f"<li>{esc(p['program_name'])} ({esc(p.get('state'))}) — {esc(p.get('visa_sponsorship'))}</li>")
            H.append("</ul>")
    if errors:
        H.append("<p style='color:#b00;font-size:13px'><b>Fetch warnings:</b><br>" + "<br>".join(esc(e) for e in errors) + "</p>")
    H.append("<p style='font-size:12px;color:#777;margin-top:16px'>Accreditation data is from ACGME ADS only. Visa labels are best-effort and must be re-confirmed in MyERAS/FREIDA before paying a fee or spending a signal. "
             "\"New programs are easier to match into\" is practitioner consensus, not proven fact.</p></div>")

    # ---------------- text
    T = [f"Newly accredited Internal Medicine programs — {run}",
         f"Source: ACGME ADS (AYs {', '.join(ch.get('academic_years', [])) or '—'}). Previous run: {prev}.",
         f"Live tracker: {a.tracker_url}", ""]
    if aborted:
        T.append("The ADS fetch FAILED — tracker not updated today.")
    elif n_new == 0:
        T.append("No new IM programs since the last check.")
    else:
        T.append(f"{n_new} NEW program(s):")
        T += [prog_line_text(n) for n in ch["new"]]
    if n_chg:
        T.append(""); T.append(f"{n_chg} changed:")
        for x in ch["changed"]:
            T.append(f"- {x['program_name']} ({x.get('state')}): " + "; ".join(f"{d['field']} {d['from']} -> {d['to']}" for d in x["diffs"]))
    if n_rem:
        T.append(""); T.append(f"{n_rem} dropped:")
        T += [f"- {x['program_name']} ({x.get('state')}) — {x['reason']}" for x in ch["removed"]]
    if not aborted:
        T += ["", f"Tracked: {c.get('total', len(progs))} | first class {tiers.get('apply-now-first-class', 0)} | still new {tiers.get('apply-now-still-new', 0)} | "
                  f"watchlist {tiers.get('watchlist-preaccreditation', 0)} | confirmed visa sponsors {sponsors} | unknown {visa.get('Unknown', 0)} | none {visa.get('None', 0)}"]
    if errors:
        T += ["", "Fetch warnings:"] + [f"  ! {e}" for e in errors]

    Path(a.html).write_text("\n".join(H))
    Path(a.text).write_text("\n".join(T) + "\n")
    Path(a.subject).write_text(subject + "\n")
    print(subject)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
