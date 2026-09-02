#!/usr/bin/env python3
"""Headless fetch of the ACGME ADS public reports for categorical Internal Medicine.

Fetches exactly what a person clicking "View Report" would fetch — a handful of PDFs —
and parses them into JSON. This is NOT a crawler: 1 form GET + N report POSTs for
Report 8 (one per academic year in the window, usually 3-4) and 1 GET + 1 POST for
Report 1. Requests are throttled. Total ≈ 6-7 HTTP requests per run.

Usage:
    python3 fetch_ads.py --out ads_snapshot.json [--run-date YYYY-MM-DD] [--months 24]
                         [--pdf-dir DIR] [--skip-roster]

Output JSON:
{
  "run_date": "YYYY-MM-DD", "fetched_at": "...", "new_cutoff": "YYYY-MM-DD",
  "academic_years": ["2024-2025", ...],
  "report8": [ {org_code, program_name, program_director, accreditation_status,
                original_accreditation_date, state, academic_year} ... ],
  "watchlist": [ same shape, from Report 1 rows in Pre-Accreditation / Applicant status ],
  "roster": { org_code: {program_name, program_director, accreditation_status,
                         effective_date, city, state_abbr, phone, coordinator_email,
                         sponsor_line, offers_prelim} },   # every IM program on Report 1
  "errors": [ "..." ]
}

PDF text extraction: uses `pdftotext -layout` (poppler) when present, else the `pypdf`
package's layout mode (`pip install pypdf`). Stdlib only otherwise.
"""
import argparse
import datetime as dt
import http.cookiejar
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://apps.acgme.org"
REPORT_URL = BASE + "/ads/Public/Reports/Report/{id}"
RUN_URL = BASE + "/ads/Public/Reports/ReportRun"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 new-im-programs/1.0")
IM_SPECIALTY_CODE = "140"
THROTTLE_S = 2.0

DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
ROW_RE = re.compile(r"^\[(\d{10})\]\s*(.*)$")
STATUS_RE = re.compile(
    r"(Initial Accreditation with Warning|Initial Accreditation|Continued Accreditation with Warning|"
    r"Continued Accreditation without Outcomes|Continued Accreditation|Pre-Accreditation|"
    r"Applicant for Initial Accreditation|Probationary Accreditation|Accreditation Withheld|"
    r"Withdrawal|Withdrawn|Voluntary Withdrawal|Administrative Withdrawal)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"Ph:\s*([\(\d][\d\)\s.-]{7,})")
CITY_RE = re.compile(r"^(.*?),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?\s*$")


# ----------------------------------------------------------------------------- HTTP
class Session:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.last = 0.0

    def _throttle(self):
        wait = THROTTLE_S - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()

    def get(self, url):
        self._throttle()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with self.opener.open(req, timeout=60) as r:
            return r.read()

    def post(self, url, data, referer):
        self._throttle()
        body = urllib.parse.urlencode(data, doseq=True).encode()
        req = urllib.request.Request(url, data=body, headers={
            "User-Agent": UA, "Referer": referer,
            "Content-Type": "application/x-www-form-urlencoded"})
        with self.opener.open(req, timeout=120) as r:
            return r.read(), r.headers.get("Content-Type", "")


def token_from(html):
    m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
    if not m:
        raise RuntimeError("no __RequestVerificationToken on the report form")
    return m.group(1)


# ----------------------------------------------------------------------------- PDF
PDF_EXTRACTOR = "auto"  # auto | pypdf | pdftotext


def pdf_text(pdf_bytes, pdf_path=None):
    """Return layout-preserving text. Prefer pypdf's layout mode (cleaner column gaps on
    these ADS PDFs); fall back to `pdftotext -layout` (poppler)."""
    use_pypdf = PDF_EXTRACTOR in ("auto", "pypdf")
    if use_pypdf:
        try:
            from pypdf import PdfReader  # type: ignore
            import io
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join(pg.extract_text(extraction_mode="layout") for pg in reader.pages)
        except ImportError:
            if PDF_EXTRACTOR == "pypdf":
                raise RuntimeError("pypdf not installed: pip install pypdf")
    if shutil.which("pdftotext"):
        p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf_bytes,
                           capture_output=True, check=True)
        return p.stdout.decode("utf-8", "replace")
    raise RuntimeError("need `pip install pypdf` or `pdftotext` (poppler) to read the ADS PDFs")


def col_spans(header_line, labels):
    """Return [(start, end)] spans for each column, from the header label positions.
    Column i spans from its label start to the next label's start (last: to EOL).
    Data cells are assigned by *overlap* with these spans, so a value that starts a couple
    of characters before its header (common in ADS PDFs) still lands in the right column."""
    starts, cursor = [], 0
    for lab in labels:
        i = header_line.find(lab, cursor)
        if i < 0:
            raise ValueError(f"header label {lab!r} not found in: {header_line!r}")
        starts.append(i)
        cursor = i + len(lab)
    return [(starts[i], starts[i + 1] if i + 1 < len(starts) else 10_000) for i in range(len(starts))]


CELL_RE = re.compile(r"\S+(?: \S+)*")  # runs of text separated by 2+ spaces


def _split_at_boundaries(cs, txt, spans):
    """A text run that straddles a column boundary (pdftotext sometimes leaves a single
    space between two columns) is split at the space closest to that boundary, provided
    both sides keep ≥ 3 characters in their own column."""
    pieces = [(cs, txt)]
    for (_s, e) in spans[:-1]:
        out = []
        for start, t in pieces:
            end = start + len(t)
            if start + 3 <= e <= end - 3 and " " in t:
                # candidate split points = spaces; choose the one nearest the boundary
                idx = [i for i, ch in enumerate(t) if ch == " "]
                k = min(idx, key=lambda i: abs((start + i) - e))
                left, right = t[:k].rstrip(), t[k + 1:].lstrip()
                if left and right:
                    out.append((start, left))
                    out.append((start + k + 1 + (len(t[k + 1:]) - len(right)), right))
                    continue
            out.append((start, t))
        pieces = out
    return pieces


def assign_cells(line, spans):
    """Split a layout line into cells (2+ spaces = separator, plus column-boundary
    splitting) and put each cell in the column whose span it overlaps most."""
    cells = [""] * len(spans)
    for m in CELL_RE.finditer(line):
        for cs, txt in _split_at_boundaries(m.start(), m.group(0), spans):
            ce = cs + len(txt)
            best, best_ov = 0, -1
            for i, (s, e) in enumerate(spans):
                ov = min(ce, e) - max(cs, s)
                if ov > best_ov:
                    best, best_ov = i, ov
            if best_ov <= 0:
                best = min(range(len(spans)), key=lambda i: abs(spans[i][0] - cs))
            cells[best] = (cells[best] + " " + txt).strip()
    return cells


SKIP_RE = re.compile(r"^\s*(©|Page \d+ of \d+|Academic Year|United States|List of |Internal Medicine Programs|"
                     r"\d+ newly accredited programs found|0 newly accredited)")
HEADER_CONT_RE = re.compile(r"^\s*(Status|Director|Positions|Date|Effective Date|Preliminary)\s*$")


def iter_rows(text, header_labels):
    """Yield (org_code, cols) where cols[i] is the list of line-cells for column i."""
    spans = None
    block, code = [], None

    def flush():
        if code and spans:
            cols = [[] for _ in spans]
            for ln in block:
                for i, c in enumerate(assign_cells(ln, spans)):
                    if c:
                        cols[i].append(c)
            yield code, cols

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if header_labels[0] in line:
            spans = col_spans(line, header_labels)
            continue
        if SKIP_RE.match(line):
            continue
        m = ROW_RE.match(line.lstrip()) if line.lstrip().startswith("[") else None
        if m and spans:
            yield from flush()
            code, block = m.group(1), [line]
            continue
        if code:
            # header continuation lines ("Status", "Effective Date"...) right after a page
            # header only appear before the first row of the page; inside a row block they
            # are data, unless they are *exactly* a header word.
            if HEADER_CONT_RE.match(line) and not block:
                continue
            block.append(line)
    yield from flush()


def us_date(s):
    m = DATE_RE.search(s or "")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""


def norm_status(s):
    m = STATUS_RE.search(re.sub(r"\s+", " ", s or ""))
    return m.group(1).title().replace("With ", "with ").replace("Without ", "without ").replace(" For ", " for ") if m else re.sub(r"\s+", " ", s or "").strip()


# ----------------------------------------------------------------------------- Report 8
R8_LABELS = ["Program Code / Name", "Program Director", "Accreditation", "Accreditation", "Specialty", "State"]


def parse_report8(text, academic_year):
    out = []
    for code, cols in iter_rows(text, R8_LABELS):
        cols = [" ".join(c) for c in cols]
        name, pd_, status, date, specialty, state = (cols + [""] * 6)[:6]
        name = re.sub(r"^\[\d{10}\]\s*", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        st = norm_status(status) or norm_status(" ".join(cols))
        out.append({
            "org_code": code,
            "program_name": name,
            "program_director": re.sub(r"\s+", " ", pd_).strip(),
            "accreditation_status": st,
            "original_accreditation_date": us_date(date) or us_date(" ".join(cols)),
            "specialty": re.sub(r"\s+", " ", specialty).strip() or "Internal medicine",
            "state": re.sub(r"\s+", " ", state).strip(),
            "academic_year": academic_year,
        })
    return out


# ----------------------------------------------------------------------------- Report 1
R1_LABELS = ["Program Number / Name", "Address", "Program", "Accreditation", "Effective", "Offers"]


def parse_report1(text):
    roster = {}
    for code, cols in iter_rows(text, R1_LABELS):
        addr_lines = cols[1] if len(cols) > 1 else []
        cols = [" ".join(c) for c in cols]
        name, addr, pd_, status, eff, offers = (cols + [""] * 6)[:6]
        name = re.sub(r"\s+", " ", re.sub(r"^\[\d{10}\]\s*", "", name)).strip()
        # Address column lines: sponsor/program line, street(s), "City, ST ZIP", "Ph: ...", email.
        email = (EMAIL_RE.search(addr) or EMAIL_RE.search(" ".join(cols)))
        phone = PHONE_RE.search(addr)
        city, st_abbr = "", ""
        for ln in addr_lines:
            cm = CITY_RE.match(ln.strip())
            if cm:
                city, st_abbr = cm.group(1).strip(), cm.group(2)
                break
        first_line = addr_lines[0].strip() if addr_lines else ""
        roster[code] = {
            "program_name": name,
            "program_director": re.sub(r"\s+", " ", pd_).strip(),
            "accreditation_status": norm_status(status),
            "effective_date": us_date(eff),
            "city": city,
            "state_abbr": st_abbr,
            "phone": re.sub(r"\s+", " ", phone.group(1)).strip() if phone else "",
            "coordinator_email": email.group(0) if email else "",
            "sponsor_line": first_line,
            "offers_prelim": offers.strip(),
        }
    return roster


# ----------------------------------------------------------------------------- main
def academic_years(new_cutoff, today):
    """AY label value = starting calendar year; AY runs Jul 1 → Jun 30. Include the AY
    containing new_cutoff through the AY *after* today's (future-dated accreditations)."""
    def ay(d):
        return d.year if d.month >= 7 else d.year - 1
    return list(range(ay(new_cutoff), ay(today) + 2))


def months_ago(d, months):
    y, m = d.year, d.month - months
    while m <= 0:
        y, m = y - 1, m + 12
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(y, m, day)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-date", default=dt.date.today().isoformat())
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--pdf-dir", help="keep the fetched PDFs here (debugging)")
    ap.add_argument("--skip-roster", action="store_true", help="skip Report 1 (watchlist + enrichment)")
    ap.add_argument("--extractor", choices=["auto", "pypdf", "pdftotext"], default="auto")
    a = ap.parse_args()
    global PDF_EXTRACTOR
    PDF_EXTRACTOR = a.extractor

    today = dt.date.fromisoformat(a.run_date)
    new_cutoff = months_ago(today, a.months)
    pdf_dir = Path(a.pdf_dir) if a.pdf_dir else None
    if pdf_dir:
        pdf_dir.mkdir(parents=True, exist_ok=True)

    snap = {"run_date": today.isoformat(), "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
            "new_cutoff": new_cutoff.isoformat(), "academic_years": [], "report8": [], "watchlist": [],
            "roster": {}, "errors": []}
    s = Session()

    # --- Report 8: newly accredited, one academic year per POST
    try:
        form = s.get(REPORT_URL.format(id=8)).decode("utf-8", "replace")
        tok = token_from(form)
        for ay in academic_years(new_cutoff, today):
            label = f"{ay}-{ay + 1}"
            try:
                pdf, ctype = s.post(RUN_URL, {
                    "__RequestVerificationToken": tok, "ReportId": "8",
                    "SpecialtyCode": IM_SPECIALTY_CODE, "AcademicYearName": str(ay)},
                    referer=REPORT_URL.format(id=8))
                if "pdf" not in ctype.lower() and not pdf.startswith(b"%PDF"):
                    raise RuntimeError(f"Report 8 AY {label}: expected PDF, got {ctype!r} ({len(pdf)} bytes)")
                if pdf_dir:
                    (pdf_dir / f"report8_{label}.pdf").write_bytes(pdf)
                text = pdf_text(pdf)
                rows = parse_report8(text, label)
                if "0 newly accredited programs found" not in text and not rows:
                    snap["errors"].append(f"Report 8 AY {label}: parsed 0 rows but PDF is not the empty template")
                snap["report8"].extend(rows)
                snap["academic_years"].append(label)
            except Exception as e:  # keep going with other years
                snap["errors"].append(f"Report 8 AY {label}: {e}")
    except Exception as e:
        snap["errors"].append(f"Report 8 form: {e}")

    # --- Report 1: full roster with pre-accreditation rows (watchlist + enrichment)
    if not a.skip_roster:
        try:
            form = s.get(REPORT_URL.format(id=1)).decode("utf-8", "replace")
            tok = token_from(form)
            pdf, ctype = s.post(RUN_URL, {
                "__RequestVerificationToken": tok, "ReportId": "1",
                "SpecialtyCode": IM_SPECIALTY_CODE,
                "IncludePreAccreditation": ["true", "false"]},
                referer=REPORT_URL.format(id=1))
            if "pdf" not in ctype.lower() and not pdf.startswith(b"%PDF"):
                raise RuntimeError(f"Report 1: expected PDF, got {ctype!r} ({len(pdf)} bytes)")
            if pdf_dir:
                (pdf_dir / "report1.pdf").write_bytes(pdf)
            roster = parse_report1(pdf_text(pdf))
            if len(roster) < 300:
                snap["errors"].append(f"Report 1: only {len(roster)} programs parsed (expected ~600+); parser drift?")
            snap["roster"] = roster
            for code, r in roster.items():
                if re.search(r"pre-accreditation|applicant", r["accreditation_status"], re.I):
                    snap["watchlist"].append({
                        "org_code": code, "program_name": r["program_name"],
                        "program_director": r["program_director"],
                        "accreditation_status": r["accreditation_status"],
                        "original_accreditation_date": "",  # Report 1's date is NOT the original accreditation date
                        "effective_date": r["effective_date"],
                        "specialty": "Internal medicine", "state": r["state_abbr"],
                        "academic_year": "",
                    })
        except Exception as e:
            snap["errors"].append(f"Report 1: {e}")

    # de-dup report8 by org code (a program can appear in two AY reports only if re-dated)
    seen, dedup = set(), []
    for r in snap["report8"]:
        if r["org_code"] in seen:
            continue
        seen.add(r["org_code"])
        dedup.append(r)
    snap["report8"] = dedup

    Path(a.out).write_text(json.dumps(snap, indent=2))
    n_init = sum(1 for r in snap["report8"] if r["accreditation_status"].startswith("Initial"))
    print(f"[fetch_ads] run_date={snap['run_date']} new_cutoff={snap['new_cutoff']} "
          f"AYs={snap['academic_years']} report8={len(snap['report8'])} (Initial={n_init}) "
          f"watchlist={len(snap['watchlist'])} roster={len(snap['roster'])} errors={len(snap['errors'])}")
    for e in snap["errors"]:
        print("  ! " + e)
    return 1 if (not snap["report8"] and snap["errors"]) else 0


if __name__ == "__main__":
    sys.exit(main())
