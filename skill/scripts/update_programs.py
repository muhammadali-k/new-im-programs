#!/usr/bin/env python3
"""Merge an ADS snapshot (from fetch_ads.py) into programs.json and write a changes file.

Usage:
    python3 update_programs.py <ads_snapshot.json> <programs.json> --run-date YYYY-MM-DD
                               [--changes changes.json] [--months 24]

- Re-anchors new_cutoff / first_class_cutoff to the run date and re-tiers every program.
- Adds programs that are new (first_seen = run date, visa Unknown, is_new_since_last_run).
- Preserves every existing field (visa_*, first_seen, enrichment) for programs already tracked.
- Enriches blanks (city, phone, coordinator_email) from the Report 1 roster.
- Removes programs that aged out (> 24 months), moved to Continued/Probationary/Withdrawn,
  or vanished from ADS — recorded in the changes file, never silently.
- Writes programs.json (schema in SKILL.md) and a changes JSON the digest is built from.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}

EMPTY = {
    "program_name": "", "org_code": "", "program_id": "", "sponsoring_institution": "", "city": "",
    "state": "", "accreditation_status": "", "original_accreditation_date": "", "effective_date": "",
    "approved_positions": None, "filled_positions": None, "length_of_training": "",
    "program_director": "", "pd_first_appointed": "", "coordinator_email": "", "program_website": "",
    "phone": "", "next_site_visit": "", "visa_sponsorship": "Unknown", "visa_confidence": "",
    "visa_evidence": [], "visa_checked_date": "", "tier": "", "detail_url": "", "history_url": "",
    "first_seen": "", "last_seen": "", "is_new_since_last_run": False,
}


def months_ago(d, months):
    y, m = d.year, d.month - months
    while m <= 0:
        y, m = y - 1, m + 12
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    day = min(d.day, [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(y, m, day)


def tier_for(status, orig_date, new_cutoff, first_class_cutoff):
    s = (status or "").lower()
    if "pre-accreditation" in s or "applicant" in s:
        return "watchlist-preaccreditation"
    if not s.startswith("initial"):
        return None  # continued / probationary / withdrawn → not tracked
    if not orig_date:
        return None
    if orig_date >= first_class_cutoff:
        return "apply-now-first-class"
    if orig_date >= new_cutoff:
        return "apply-now-still-new"
    return None  # aged out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("programs")
    ap.add_argument("--run-date", required=True)
    ap.add_argument("--changes")
    ap.add_argument("--months", type=int, default=24)
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.run_date)
    new_cutoff = months_ago(today, a.months).isoformat()
    first_class_cutoff = months_ago(today, 12).isoformat()
    snap = json.loads(Path(a.snapshot).read_text())
    roster = snap.get("roster") or {}

    ppath = Path(a.programs)
    old = json.loads(ppath.read_text()) if ppath.exists() else {"programs": []}
    old_by = {p["org_code"]: p for p in old.get("programs", [])}
    prev_run = old.get("run_date", "")

    changes = {"run_date": today.isoformat(), "previous_run_date": prev_run, "new_cutoff": new_cutoff,
               "first_class_cutoff": first_class_cutoff, "academic_years": snap.get("academic_years", []),
               "fetch_errors": snap.get("errors", []), "new": [], "removed": [], "changed": [],
               "counts": {}, "roster_size": len(roster), "first_run": not old_by}

    fetched = {}
    for r in snap.get("report8", []) + snap.get("watchlist", []):
        t = tier_for(r["accreditation_status"], r.get("original_accreditation_date", ""), new_cutoff, first_class_cutoff)
        if not t:
            continue
        fetched[r["org_code"]] = (r, t)

    # Refuse to touch the list on a broken/partial fetch: Report 8 must have succeeded for every
    # academic year (a missing year would silently "age out" real programs).
    if not snap.get("fetch_ok", bool(fetched) and not snap.get("errors")):
        print("[update_programs] fetch produced nothing and reported errors — leaving programs.json untouched", file=sys.stderr)
        for e in snap["errors"]:
            print("  ! " + e, file=sys.stderr)
        if a.changes:
            changes["aborted"] = True
            Path(a.changes).write_text(json.dumps(changes, indent=2))
        return 2

    programs = []
    for code, (r, tier) in fetched.items():
        ro = roster.get(code, {})
        if code in old_by:
            p = dict(EMPTY, **old_by[code])
            p["is_new_since_last_run"] = False
            diffs = []
            for k_new, k_old in (("accreditation_status", "accreditation_status"), ("program_director", "program_director")):
                if r.get(k_new) and p.get(k_old) and r[k_new] != p[k_old]:
                    diffs.append({"field": k_old, "from": p[k_old], "to": r[k_new]})
            if r.get("original_accreditation_date") and p.get("original_accreditation_date") and \
                    r["original_accreditation_date"] != p["original_accreditation_date"]:
                diffs.append({"field": "original_accreditation_date", "from": p["original_accreditation_date"], "to": r["original_accreditation_date"]})
            if p.get("tier") and p["tier"] != tier:
                diffs.append({"field": "tier", "from": p["tier"], "to": tier})
            if diffs:
                changes["changed"].append({"org_code": code, "program_name": r["program_name"] or p["program_name"],
                                           "state": p.get("state") or r.get("state"), "diffs": diffs})
        else:
            p = dict(EMPTY)
            p["first_seen"] = today.isoformat()
            p["is_new_since_last_run"] = not changes["first_run"]
            p["detail_url"] = f"https://apps.acgme.org/ads/Public/Programs/Detail?orgCode={code}"

        # ADS-authoritative fields always refresh from the snapshot
        p["org_code"] = code
        p["program_name"] = r["program_name"] or p["program_name"]
        p["program_director"] = r["program_director"] or p["program_director"]
        p["accreditation_status"] = r["accreditation_status"] or p["accreditation_status"]
        if r.get("original_accreditation_date"):
            p["original_accreditation_date"] = r["original_accreditation_date"]
            p["effective_date"] = p.get("effective_date") or r["original_accreditation_date"]
        st = r.get("state") or ""
        p["state"] = STATE_ABBR.get(st, st) or p["state"]
        p["tier"] = tier
        p["last_seen"] = today.isoformat()
        # Enrichment from the Report 1 roster — only fills blanks
        if ro:
            p["city"] = p["city"] or ro.get("city", "")
            p["phone"] = p["phone"] or ro.get("phone", "")
            p["coordinator_email"] = p["coordinator_email"] or ro.get("coordinator_email", "")
            if not p["state"] and ro.get("state_abbr"):
                p["state"] = STATE_ABBR.get(ro["state_abbr"], ro["state_abbr"])
            if not p.get("effective_date") and ro.get("effective_date"):
                p["effective_date"] = ro["effective_date"]
            p["offers_prelim"] = ro.get("offers_prelim", p.get("offers_prelim", ""))
        programs.append(p)
        if p["is_new_since_last_run"]:
            changes["new"].append({k: p.get(k) for k in ("org_code", "program_name", "state", "city", "program_director",
                                                        "accreditation_status", "original_accreditation_date", "tier",
                                                        "coordinator_email", "phone", "detail_url", "visa_sponsorship")})

    # Removed programs (present last run, not in the tracked set now)
    for code, p in old_by.items():
        if code in fetched:
            continue
        ro = roster.get(code)
        if ro and ro.get("accreditation_status"):
            s = ro["accreditation_status"]
            reason = "aged out of the 24-month window" if s.lower().startswith("initial") else f"status now: {s}"
        elif roster:
            reason = "no longer listed on ADS Report 1 (withdrawn / closed?)"
        else:
            reason = "not in Report 8 this run (roster unavailable to explain why)"
        changes["removed"].append({"org_code": code, "program_name": p.get("program_name"), "state": p.get("state"),
                                   "original_accreditation_date": p.get("original_accreditation_date"),
                                   "tier_was": p.get("tier"), "reason": reason})

    # newest first, then by name
    programs.sort(key=lambda p: ((p["original_accreditation_date"] or ""), p["program_name"]), reverse=True)

    out = {
        "generated": today.isoformat(), "run_date": today.isoformat(),
        "source": "ACGME ADS (apps.acgme.org)", "specialty": "Internal Medicine (categorical)",
        "new_cutoff": new_cutoff, "first_class_cutoff": first_class_cutoff,
        "previous_run_date": prev_run, "academic_years": snap.get("academic_years", []),
        "programs": programs,
    }
    tiers = {t: sum(1 for p in programs if p["tier"] == t) for t in
             ("apply-now-first-class", "apply-now-still-new", "watchlist-preaccreditation")}
    visas = {}
    for p in programs:
        visas[p.get("visa_sponsorship") or "Unknown"] = visas.get(p.get("visa_sponsorship") or "Unknown", 0) + 1
    changes["counts"] = {"total": len(programs), "tiers": tiers, "visa": visas,
                         "new": len(changes["new"]), "removed": len(changes["removed"]), "changed": len(changes["changed"])}

    ppath.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    if a.changes:
        Path(a.changes).write_text(json.dumps(changes, indent=2, ensure_ascii=False))
    print(f"[update_programs] {today}: tracked={len(programs)} {tiers} new={len(changes['new'])} "
          f"removed={len(changes['removed'])} changed={len(changes['changed'])} (prev run {prev_run or 'none'})")
    for n in changes["new"]:
        print(f"  + NEW {n['org_code']} {n['program_name']} ({n['state']}) accredited {n['original_accreditation_date']}")
    for r in changes["removed"]:
        print(f"  - REMOVED {r['org_code']} {r['program_name']}: {r['reason']}")
    for c in changes["changed"]:
        print(f"  ~ CHANGED {c['org_code']} {c['program_name']}: " + "; ".join(f"{d['field']} {d['from']} → {d['to']}" for d in c["diffs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
