#!/usr/bin/env python3
"""Render newly-accredited IM programs (programs.json) into a self-contained,
sortable/filterable HTML tracker, grouped by VISA-SPONSORSHIP status.

Usage:
    python3 render_html.py <programs.json> [output.html]

If output.html is omitted, writes new-im-programs.html next to the JSON.
The input schema is documented in ../SKILL.md.

The tracker is built for visa-needing (IMG) applicants, so programs are split
into three sections by their `visa_sponsorship` value:
  * Confirmed sponsors  (J-1 / J-1+H-1B / H-1B-only)
  * Visa status unknown (no source confirmed a policy — verify directly)
  * Not for visa applicants (a source confirmed no sponsorship — de-emphasized)
Within each section a program keeps its newness tier (first class / still new).
"""
import html
import json
import sys
from datetime import date
from pathlib import Path

TIER_LABELS = {
    "apply-now-first-class": ("Apply now · first class", "tier-first"),
    "apply-now-still-new": ("Apply now · still new", "tier-new"),
    "watchlist-preaccreditation": ("Watchlist · pre-accreditation", "tier-watch"),
}
TIER_ORDER = ["apply-now-first-class", "apply-now-still-new", "watchlist-preaccreditation"]

# Visa status -> (display label, css class, group key). Group keys drive the
# three sections. Anything unrecognised / empty is treated as Unknown.
VISA_META = {
    "J-1+H-1B": ("J-1 + H-1B", "visa-both", "sponsor"),
    "J-1": ("J-1", "visa-j1", "sponsor"),
    "H-1B-only": ("H-1B only", "visa-h1b", "sponsor"),
    "Unknown": ("Unknown", "visa-unknown", "unknown"),
    "None": ("No sponsorship", "visa-none", "none"),
}
# Section order + headings. `sponsor` first (the point of the tracker).
GROUPS = [
    ("sponsor", "✅ Confirmed visa sponsors",
     "ACGME-accredited and a source confirms J-1 and/or H-1B sponsorship. Your apply-now set."),
    ("unknown", "❓ Visa status unknown — verify directly",
     "No official site, FREIDA, or ECFMG source confirmed a visa policy during the scan. "
     "Website silence ≠ no sponsorship — most IM programs do sponsor J-1. Confirm in MyERAS / "
     "FREIDA / by emailing the coordinator before ruling these out."),
    ("none", "🚫 Not for visa applicants",
     "A source states this program does not sponsor visas (US citizens / permanent residents only). "
     "Shown for completeness, de-emphasized."),
]
# Visa sort order within a section (best first).
VISA_SORT = {"J-1+H-1B": 0, "J-1": 1, "H-1B-only": 2, "Unknown": 3, "None": 4}

COLUMNS = [
    ("program_name", "Program", "col-name"),
    ("visa_sponsorship", "Visa", "col-visa"),
    ("tier", "Tier", "col-tier"),
    ("state", "State", "col-state"),
    ("original_accreditation_date", "Accredited", "col-date"),
    ("approved_positions", "Positions", "col-num"),
    ("sponsoring_institution", "Sponsor", "col-sponsor"),
    ("program_director", "Program director", "col-pd"),
    ("coordinator_email", "Coordinator", "col-email"),
]


def esc(v):
    if v is None or v == "":
        return ""
    return html.escape(str(v))


def norm_visa(prog):
    raw = (prog.get("visa_sponsorship") or "").strip()
    for key in VISA_META:
        if raw.lower() == key.lower():
            return key
    return "Unknown"


def visa_group(prog):
    return VISA_META[norm_visa(prog)][2]


def first_evidence(prog):
    ev = prog.get("visa_evidence") or []
    if isinstance(ev, list) and ev:
        e = ev[0]
        if isinstance(e, dict):
            return e.get("url", ""), e.get("quote", ""), e.get("source", "")
    return "", "", ""


def cell_html(prog, key):
    val = prog.get(key)
    if key == "program_name":
        name = esc(val) or "(unnamed program)"
        url = esc(prog.get("detail_url"))
        badge = ' <span class="newflag" title="New since your last check">NEW</span>' if prog.get("is_new_since_last_run") else ""
        inner = f'<a href="{url}" target="_blank" rel="noopener">{name}</a>' if url else name
        return f"{inner}{badge}"
    if key == "tier":
        label, cls = TIER_LABELS.get(val, (esc(val), "tier-other"))
        return f'<span class="tier {cls}">{esc(label)}</span>'
    if key == "visa_sponsorship":
        status = norm_visa(prog)
        label, cls, _ = VISA_META[status]
        conf = (prog.get("visa_confidence") or "").strip()
        url, quote, source = first_evidence(prog)
        title = ""
        if quote or source:
            title = f' title="{esc(source)}: {esc(quote)[:160]}"'
        dot = f'<span class="conf conf-{esc(conf)}" title="confidence: {esc(conf) or "n/a"}"></span>' if conf else ""
        badge = f'<span class="visa {cls}"{title}>{esc(label)}</span>{dot}'
        if url:
            return f'<a href="{esc(url)}" target="_blank" rel="noopener" class="visa-link">{badge}</a>'
        return badge
    if key == "coordinator_email":
        e = esc(val)
        return f'<a href="mailto:{e}">{e}</a>' if e else ""
    if key in ("approved_positions", "filled_positions"):
        return "" if val in (None, "") else esc(val)
    return esc(val)


def sort_value(prog, key):
    val = prog.get(key)
    if key == "tier":
        return str(TIER_ORDER.index(val)) if val in TIER_ORDER else "9"
    if key == "visa_sponsorship":
        return str(VISA_SORT.get(norm_visa(prog), 9))
    if key in ("approved_positions", "filled_positions"):
        try:
            return f"{int(val):09d}"
        except (TypeError, ValueError):
            return ""
    if key == "original_accreditation_date":
        return esc(val)
    return (esc(val) or "").lower()


def row_html(p):
    tds = []
    for key, header, cls in COLUMNS:
        tds.append(f'<td class="{cls}" data-sort="{esc(sort_value(p, key))}">{cell_html(p, key)}</td>')
    haystack = " ".join(
        esc(p.get(k)) for k in
        ("program_name", "sponsoring_institution", "city", "state", "program_director",
         "accreditation_status", "coordinator_email")
    ).lower()
    return (
        f'<tr data-tier="{esc(p.get("tier"))}" data-state="{esc(p.get("state"))}" '
        f'data-visa="{esc(norm_visa(p))}" data-search="{haystack}">' + "".join(tds) + "</tr>"
    )


def section_html(gkey, heading, blurb, progs, tbl_index):
    ths = []
    for i, (key, header, cls) in enumerate(COLUMNS):
        ths.append(f'<th class="{cls}" data-col="{i}" onclick="sortBy({tbl_index},{i})">{esc(header)}<span class="arrow"></span></th>')
    thead = "<tr>" + "".join(ths) + "</tr>"
    rows = "\n".join(row_html(p) for p in progs)
    return f"""
  <section class="group group-{gkey}" data-group="{gkey}">
    <h2 class="ghead">{esc(heading)} <span class="gcount" id="gcount-{gkey}">{len(progs)}</span></h2>
    <p class="gblurb">{esc(blurb)}</p>
    <div class="tablewrap">
      <table class="ptable" data-tbl="{tbl_index}">
        <thead>{thead}</thead>
        <tbody>{rows}</tbody>
      </table>
      <div class="empty" style="display:none">No programs in this section match your filters.</div>
    </div>
  </section>"""


def build(data):
    programs = list(data.get("programs", []))
    programs.sort(key=lambda p: (p.get("original_accreditation_date") or ""), reverse=True)
    programs.sort(key=lambda p: TIER_ORDER.index(p.get("tier")) if p.get("tier") in TIER_ORDER else 9)
    programs.sort(key=lambda p: VISA_SORT.get(norm_visa(p), 9))

    gen = esc(data.get("generated") or data.get("run_date") or date.today().isoformat())
    states = sorted({p.get("state") for p in programs if p.get("state")})
    n_new = sum(1 for p in programs if p.get("is_new_since_last_run"))

    grouped = {g: [] for g, _, _ in GROUPS}
    for p in programs:
        grouped[visa_group(p)].append(p)

    vcount = {k: sum(1 for p in programs if norm_visa(p) == k) for k in VISA_META}
    n_sponsor = len(grouped["sponsor"])
    n_unknown = len(grouped["unknown"])
    n_none = len(grouped["none"])

    sections = "".join(
        section_html(gkey, head, blurb, grouped[gkey], i)
        for i, (gkey, head, blurb) in enumerate(GROUPS)
    )

    state_opts = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in states)
    visa_opts = "".join(
        f'<option value="{k}">{esc(VISA_META[k][0])} ({vcount[k]})</option>'
        for k in ["J-1+H-1B", "J-1", "H-1B-only", "Unknown", "None"] if vcount[k]
    )
    tier_opts = "".join(
        f'<option value="{t}">{esc(TIER_LABELS[t][0])}</option>' for t in TIER_ORDER
    )

    summary = (
        f'<b>{n_sponsor}</b> visa sponsors '
        f'({vcount["J-1+H-1B"]} J-1+H-1B, {vcount["J-1"]} J-1'
        + (f', {vcount["H-1B-only"]} H-1B-only' if vcount["H-1B-only"] else "")
        + f') · <b>{n_unknown}</b> unknown · <b>{n_none}</b> non-sponsor'
    )
    new_line = (f'<span class="new-since">{n_new} new since your last check</span>'
                if n_new else '<span class="muted">No change since your last check</span>')

    return TEMPLATE.format(
        generated=gen,
        total=len(programs),
        summary=summary,
        new_line=new_line,
        state_opts=state_opts,
        visa_opts=visa_opts,
        tier_opts=tier_opts,
        sections=sections,
        source=esc(data.get("source", "ACGME ADS")),
        specialty=esc(data.get("specialty", "Internal Medicine (categorical)")),
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Newly Accredited IM Programs · Visa Tracker</title>
<style>
  :root {{
    --bg:#f7f8fa; --card:#ffffff; --ink:#1a1d21; --muted:#6b7280; --line:#e5e7eb;
    --accent:#1d4ed8; --first:#0f766e; --new:#b45309; --watch:#7c3aed; --newflag:#dc2626;
    --head:#f0f2f5;
    --both:#047857; --j1:#1d4ed8; --h1b:#7c3aed; --vunknown:#6b7280; --vnone:#9ca3af;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0e1116; --card:#171b21; --ink:#e6e8eb; --muted:#9aa4b2; --line:#2a3038;
      --accent:#7aa2ff; --first:#5eded0; --new:#f0b658; --watch:#c4a6ff; --newflag:#ff6b6b;
      --head:#1e242c;
      --both:#34d399; --j1:#7aa2ff; --h1b:#c4a6ff; --vunknown:#9aa4b2; --vnone:#6b7280;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1250px; margin:0 auto; padding:24px 18px 60px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); margin:0 0 18px; }}
  .sub b {{ color:var(--ink); }}
  .new-since {{ color:var(--new); font-weight:600; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:12px; margin-bottom:14px; position:sticky; top:0; z-index:5; }}
  .controls input, .controls select {{ font:inherit; color:var(--ink); background:var(--bg);
    border:1px solid var(--line); border-radius:8px; padding:8px 10px; }}
  .controls input[type=search] {{ flex:1; min-width:200px; }}
  .count {{ color:var(--muted); margin-left:auto; white-space:nowrap; }}
  .group {{ margin:22px 0 0; }}
  .ghead {{ font-size:16px; margin:0 0 2px; display:flex; align-items:center; gap:8px; }}
  .gcount {{ font-size:12px; font-weight:700; color:var(--muted); background:var(--head);
    border:1px solid var(--line); border-radius:999px; padding:1px 9px; }}
  .gblurb {{ color:var(--muted); font-size:12.5px; margin:0 0 10px; max-width:900px; }}
  .group-none {{ opacity:.62; }}
  .tablewrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; background:var(--card); }}
  table {{ border-collapse:collapse; width:100%; min-width:900px; }}
  th, td {{ text-align:left; padding:9px 11px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ background:var(--head); position:sticky; top:0; cursor:pointer; user-select:none;
    font-weight:600; white-space:nowrap; }}
  th .arrow {{ font-size:10px; color:var(--muted); margin-left:4px; }}
  tbody tr:hover {{ background:rgba(125,140,170,.08); }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .col-name {{ min-width:230px; }}
  .col-sponsor {{ min-width:170px; }}
  .col-num {{ text-align:right; white-space:nowrap; }}
  .col-date, .col-state {{ white-space:nowrap; }}
  .muted {{ color:var(--muted); }}
  .tier {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;
    font-weight:600; white-space:nowrap; border:1px solid transparent; }}
  .tier-first {{ color:var(--first); border-color:var(--first); }}
  .tier-new {{ color:var(--new); border-color:var(--new); }}
  .tier-watch {{ color:var(--watch); border-color:var(--watch); }}
  .visa {{ display:inline-block; padding:2px 8px; border-radius:6px; font-size:12px;
    font-weight:700; white-space:nowrap; color:#fff; }}
  .visa-link {{ text-decoration:none; }}
  .visa-both {{ background:var(--both); }}
  .visa-j1 {{ background:var(--j1); }}
  .visa-h1b {{ background:var(--h1b); }}
  .visa-unknown {{ background:transparent; color:var(--vunknown); border:1px dashed var(--vunknown); font-weight:600; }}
  .visa-none {{ background:transparent; color:var(--vnone); border:1px solid var(--vnone); font-weight:600; }}
  .conf {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-left:5px;
    vertical-align:middle; }}
  .conf-high {{ background:#16a34a; }}
  .conf-medium {{ background:#d97706; }}
  .conf-low {{ background:#9ca3af; }}
  .newflag {{ background:var(--newflag); color:#fff; font-size:10px; font-weight:700;
    padding:1px 5px; border-radius:4px; margin-left:4px; vertical-align:middle; }}
  .note {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-top:18px; color:var(--muted); font-size:13px; }}
  .note b {{ color:var(--ink); }}
  .legend {{ display:flex; flex-wrap:wrap; gap:10px; margin:12px 0 0; align-items:center; }}
  .empty {{ padding:22px; text-align:center; color:var(--muted); }}
  footer {{ margin-top:22px; color:var(--muted); font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Newly ACGME-Accredited IM Programs — Visa Sponsorship Tracker</h1>
  <p class="sub">
    {specialty} · source: <b>{source}</b> · generated <b>{generated}</b><br>
    <b>{total}</b> programs — {summary}. {new_line}
  </p>

  <div class="controls">
    <input type="search" id="q" placeholder="Search program, sponsor, state, director…" oninput="applyFilters()">
    <select id="visa" onchange="applyFilters()"><option value="">All visa statuses</option>{visa_opts}</select>
    <select id="tier" onchange="applyFilters()"><option value="">All tiers</option>{tier_opts}</select>
    <select id="state" onchange="applyFilters()"><option value="">All states</option>{state_opts}</select>
    <span class="count" id="count"></span>
  </div>

  <div class="legend">
    <span class="visa visa-both">J-1 + H-1B</span>
    <span class="visa visa-j1">J-1</span>
    <span class="visa visa-h1b">H-1B only</span>
    <span class="visa visa-unknown">Unknown</span>
    <span class="visa visa-none">No sponsorship</span>
    <span class="muted" style="font-size:12px">· badge links to its source; dot = confidence (green high / amber medium / grey low)</span>
  </div>

  {sections}

  <div class="note">
    <b>How this reads.</b> You are a visa-needing (IMG) applicant, so programs are grouped by
    whether they sponsor a visa. <span class="visa visa-both">J-1 + H-1B</span> means a source
    confirms both; <span class="visa visa-j1">J-1</span> is the standard ECFMG-sponsored
    residency visa; <span class="visa visa-h1b">H-1B only</span> is rare. The
    <b>Unknown</b> section is <i>not</i> a rejection list — most IM programs sponsor J-1, but
    brand-new programs rarely state it on a thin website, so confirm directly (FREIDA, the
    coordinator, or MyERAS) before dropping them. <span class="visa visa-none">No sponsorship</span>
    means a source explicitly said US citizens/permanent residents only.
    <br><br>
    <b>Accuracy caveat.</b> Visa status here is best-effort, gathered automatically from each
    program's website plus AMA FREIDA and ECFMG. Websites are often silent or out of date, so
    every non-Unknown label carries a source you can click and a confidence dot — <b>always
    re-verify in MyERAS/FREIDA before paying a fee or spending a program signal.</b> Where no
    source was found, the value is honestly left <b>Unknown</b>, never guessed.
    <br><br>
    New programs are widely considered easier to match into (broad interviewing, community/hospital
    skew, often no published USMLE cutoff) — practitioner consensus, not proven fact. The trade-off
    is real: you would be part of the test class, PDs can turn over, and each program still faces its
    first ACGME site visit (~2 years in).
  </div>

  <footer>
    Accreditation data from the ACGME public Accreditation Data System only; visa data from program
    websites + AMA FREIDA + ECFMG. Community/social lists are early leads, not authoritative.
    Generated by the <b>new-im-programs</b> skill.
  </footer>
</div>

<script>
  var sortState = {{}};
  function applyFilters() {{
    var q = document.getElementById('q').value.trim().toLowerCase();
    var visa = document.getElementById('visa').value;
    var tier = document.getElementById('tier').value;
    var state = document.getElementById('state').value;
    var total = 0;
    document.querySelectorAll('section.group').forEach(function(sec) {{
      var rows = sec.querySelectorAll('table.ptable tbody tr');
      var shown = 0;
      rows.forEach(function(r) {{
        var ok = (!visa || r.dataset.visa === visa)
              && (!tier || r.dataset.tier === tier)
              && (!state || r.dataset.state === state)
              && (!q || r.dataset.search.indexOf(q) !== -1);
        r.style.display = ok ? '' : 'none';
        if (ok) shown++;
      }});
      total += shown;
      var gk = sec.dataset.group;
      var gc = document.getElementById('gcount-' + gk);
      if (gc) gc.textContent = shown;
      var emptyEl = sec.querySelector('.empty');
      if (emptyEl) emptyEl.style.display = shown ? 'none' : '';
      // hide the whole section when nothing matches
      sec.style.display = shown ? '' : (rows.length ? 'none' : '');
    }});
    document.getElementById('count').textContent = total + ' shown';
  }}
  function sortBy(tbl, col) {{
    var table = document.querySelector('table.ptable[data-tbl="' + tbl + '"]');
    if (!table) return;
    var tbody = table.querySelector('tbody');
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var st = sortState[tbl] || {{ col: -1, dir: 1 }};
    st.dir = (st.col === col) ? -st.dir : 1;
    st.col = col;
    sortState[tbl] = st;
    rows.sort(function(a, b) {{
      var av = a.children[col].getAttribute('data-sort') || '';
      var bv = b.children[col].getAttribute('data-sort') || '';
      if (av < bv) return -1 * st.dir;
      if (av > bv) return 1 * st.dir;
      return 0;
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
    table.querySelectorAll('th .arrow').forEach(function(s) {{ s.textContent = ''; }});
    var arrow = table.querySelectorAll('th')[col].querySelector('.arrow');
    if (arrow) arrow.textContent = st.dir > 0 ? '\\u25B2' : '\\u25BC';
  }}
  applyFilters();
</script>
</body>
</html>
"""


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    src = Path(argv[1]).expanduser()
    if not src.exists():
        print(f"error: {src} not found", file=sys.stderr)
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    out = Path(argv[2]).expanduser() if len(argv) > 2 else src.with_name("new-im-programs.html")
    out.write_text(build(data), encoding="utf-8")
    print(f"wrote {out} ({len(data.get('programs', []))} programs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
