#!/usr/bin/env python3
"""Merge visa-verification results into programs.json.

Usage:
    python3 merge_visa.py <programs.json> <visa_results.json> <checked_date YYYY-MM-DD>

<visa_results.json> is the workflow output: {"results": [{org_code, visa_status,
confidence, website, evidence:[{source,url,quote}], notes}, ...]}.

Writes programs.json in place, setting per program:
  visa_sponsorship  = one of J-1 / J-1+H-1B / H-1B-only / None / Unknown
  visa_confidence   = high | medium | low | ""
  visa_evidence     = [{source,url,quote}, ...]
  visa_checked_date = the checked_date
  program_website   = filled from result.website if previously empty
Programs with no result are left Unknown (honest default).
"""
import json
import sys
from pathlib import Path

VALID = {"J-1", "J-1+H-1B", "H-1B-only", "None", "Unknown"}


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    pj = Path(argv[1]).expanduser()
    rj = Path(argv[2]).expanduser()
    checked = argv[3]
    data = json.loads(pj.read_text(encoding="utf-8"))
    res = json.loads(rj.read_text(encoding="utf-8"))
    results = res.get("results", res if isinstance(res, list) else [])
    by = {r.get("org_code"): r for r in results if r.get("org_code")}

    counts = {}
    for p in data.get("programs", []):
        r = by.get(p.get("org_code"))
        if not r:
            status = "Unknown"
            p.setdefault("visa_confidence", "")
            p.setdefault("visa_evidence", [])
        else:
            status = r.get("visa_status", "Unknown")
            if status not in VALID:
                status = "Unknown"
            p["visa_confidence"] = r.get("confidence", "")
            ev = r.get("evidence") or []
            p["visa_evidence"] = [
                {"source": e.get("source", ""), "url": e.get("url", ""), "quote": e.get("quote", "")}
                for e in ev if isinstance(e, dict)
            ]
            if r.get("notes"):
                p["visa_notes"] = r["notes"]
            if r.get("website") and not p.get("program_website"):
                p["program_website"] = r["website"]
        p["visa_sponsorship"] = status
        p["visa_checked_date"] = checked
        counts[status] = counts.get(status, 0) + 1

    pj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("merged. visa status counts:", json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
