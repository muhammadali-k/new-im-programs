#!/usr/bin/env python3
"""Render newly-accredited IM programs (programs.json) into a self-contained,
sortable/filterable HTML tracker. Pure stdlib; no external dependencies.

Usage:
    python3 render_html.py <programs.json> [output.html]

If output.html is omitted, writes new-im-programs.html next to the JSON.
The input schema is documented in ../SKILL.md.
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
# Order used for the default sort and the tier filter dropdown.
TIER_ORDER = ["apply-now-first-class", "apply-now-still-new", "watchlist-preaccreditation"]

# Columns: (json_key, header, css-class). "program_name" gets special link treatment.
COLUMNS = [
    ("program_name", "Program", "col-name"),
    ("tier", "Tier", "col-tier"),
    ("state", "State", "col-state"),
    ("city", "City", "col-city"),
    ("accreditation_status", "Status", "col-status"),
    ("original_accreditation_date", "Accredited", "col-date"),
    ("approved_positions", "Positions", "col-num"),
    ("filled_positions", "Filled", "col-num"),
    ("sponsoring_institution", "Sponsor", "col-sponsor"),
    ("program_director", "Program director", "col-pd"),
    ("coordinator_email", "Coordinator", "col-email"),
    ("visa_sponsorship", "Visa", "col-visa"),
]


def esc(v):
    if v is None or v == "":
        return ""
    return html.escape(str(v))


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
    if key == "coordinator_email":
        e = esc(val)
        return f'<a href="mailto:{e}">{e}</a>' if e else ""
    if key in ("approved_positions", "filled_positions"):
        return "" if val in (None, "") else esc(val)
    if key == "visa_sponsorship":
        v = esc(val) or "unknown"
        return f'<span class="muted">{v}</span>' if v.lower() == "unknown" else v
    return esc(val)


def sort_value(prog, key):
    """Value used by the JS sorter (kept in a data-attr so sort is content-based)."""
    val = prog.get(key)
    if key == "tier":
        return str(TIER_ORDER.index(val)) if val in TIER_ORDER else "9"
    if key in ("approved_positions", "filled_positions"):
        try:
            return f"{int(val):09d}"
        except (TypeError, ValueError):
            return ""
    if key == "original_accreditation_date":
        return esc(val)  # ISO dates sort lexically
    return (esc(val) or "").lower()


def build(data):
    programs = list(data.get("programs", []))
    # Default order: group by tier, most-recent accreditation first within each tier.
    # (Python's sort is stable, so sort by date desc first, then by tier.)
    programs.sort(key=lambda p: (p.get("original_accreditation_date") or ""), reverse=True)
    programs.sort(key=lambda p: TIER_ORDER.index(p.get("tier")) if p.get("tier") in TIER_ORDER else 9)

    gen = esc(data.get("generated") or data.get("run_date") or date.today().isoformat())
    states = sorted({p.get("state") for p in programs if p.get("state")})
    counts = {t: sum(1 for p in programs if p.get("tier") == t) for t in TIER_ORDER}
    n_new = sum(1 for p in programs if p.get("is_new_since_last_run"))

    # header row
    ths = []
    for i, (key, header, cls) in enumerate(COLUMNS):
        ths.append(f'<th class="{cls}" data-col="{i}" onclick="sortBy({i})">{esc(header)}<span class="arrow"></span></th>')
    thead = "<tr>" + "".join(ths) + "</tr>"

    # body rows
    rows = []
    for p in programs:
        tds = []
        for key, header, cls in COLUMNS:
            tds.append(f'<td class="{cls}" data-sort="{esc(sort_value(p, key))}">{cell_html(p, key)}</td>')
        haystack = " ".join(
            esc(p.get(k)) for k in
            ("program_name", "sponsoring_institution", "city", "state", "program_director",
             "accreditation_status", "coordinator_email")
        ).lower()
        rows.append(
            f'<tr data-tier="{esc(p.get("tier"))}" data-state="{esc(p.get("state"))}" '
            f'data-search="{haystack}">' + "".join(tds) + "</tr>"
        )
    tbody = "\n".join(rows)

    state_opts = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in states)
    tier_opts = "".join(
        f'<option value="{t}">{esc(TIER_LABELS[t][0])} ({counts[t]})</option>' for t in TIER_ORDER
    )

    summary = " · ".join(
        f"{counts[t]} {esc(TIER_LABELS[t][0].split(' · ')[1] if ' · ' in TIER_LABELS[t][0] else TIER_LABELS[t][0])}"
        for t in TIER_ORDER
    )
    new_line = (f'<span class="new-since">{n_new} new since your last check</span>'
                if n_new else '<span class="muted">No change since your last check</span>')

    return TEMPLATE.format(
        generated=gen,
        total=len(programs),
        summary=esc(summary),
        new_line=new_line,
        state_opts=state_opts,
        tier_opts=tier_opts,
        thead=thead,
        tbody=tbody,
        source=esc(data.get("source", "ACGME ADS")),
        specialty=esc(data.get("specialty", "Internal Medicine (categorical)")),
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Newly Accredited IM Programs</title>
<style>
  :root {{
    --bg:#f7f8fa; --card:#ffffff; --ink:#1a1d21; --muted:#6b7280; --line:#e5e7eb;
    --accent:#1d4ed8; --first:#0f766e; --new:#b45309; --watch:#7c3aed; --newflag:#dc2626;
    --head:#f0f2f5;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0e1116; --card:#171b21; --ink:#e6e8eb; --muted:#9aa4b2; --line:#2a3038;
      --accent:#7aa2ff; --first:#5eded0; --new:#f0b658; --watch:#c4a6ff; --newflag:#ff6b6b;
      --head:#1e242c;
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
  .tablewrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; background:var(--card); }}
  table {{ border-collapse:collapse; width:100%; min-width:1050px; }}
  th, td {{ text-align:left; padding:9px 11px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ background:var(--head); position:sticky; top:0; cursor:pointer; user-select:none;
    font-weight:600; white-space:nowrap; }}
  th .arrow {{ font-size:10px; color:var(--muted); margin-left:4px; }}
  tbody tr:hover {{ background:rgba(125,140,170,.08); }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .col-name {{ min-width:230px; }}
  .col-sponsor {{ min-width:180px; }}
  .col-num {{ text-align:right; white-space:nowrap; }}
  .col-date, .col-state {{ white-space:nowrap; }}
  .muted {{ color:var(--muted); }}
  .tier {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;
    font-weight:600; white-space:nowrap; border:1px solid transparent; }}
  .tier-first {{ color:var(--first); border-color:var(--first); }}
  .tier-new {{ color:var(--new); border-color:var(--new); }}
  .tier-watch {{ color:var(--watch); border-color:var(--watch); }}
  .newflag {{ background:var(--newflag); color:#fff; font-size:10px; font-weight:700;
    padding:1px 5px; border-radius:4px; margin-left:4px; vertical-align:middle; }}
  .note {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-top:18px; color:var(--muted); font-size:13px; }}
  .note b {{ color:var(--ink); }}
  .legend {{ display:flex; flex-wrap:wrap; gap:14px; margin:10px 0 0; }}
  .empty {{ padding:26px; text-align:center; color:var(--muted); }}
  footer {{ margin-top:22px; color:var(--muted); font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Newly ACGME-Accredited Internal Medicine Programs</h1>
  <p class="sub">
    {specialty} · source: <b>{source}</b> · generated <b>{generated}</b><br>
    <b>{total}</b> programs — {summary}. {new_line}
  </p>

  <div class="controls">
    <input type="search" id="q" placeholder="Search program, sponsor, city, director…" oninput="applyFilters()">
    <select id="tier" onchange="applyFilters()"><option value="">All tiers</option>{tier_opts}</select>
    <select id="state" onchange="applyFilters()"><option value="">All states</option>{state_opts}</select>
    <span class="count" id="count"></span>
  </div>

  <div class="tablewrap">
    <table id="tbl">
      <thead>{thead}</thead>
      <tbody>{tbody}</tbody>
    </table>
    <div class="empty" id="empty" style="display:none">No programs match your filters.</div>
  </div>

  <div class="legend">
    <span class="tier tier-first">Apply now · first class</span>
    <span class="tier tier-new">Apply now · still new</span>
    <span class="tier tier-watch">Watchlist · pre-accreditation</span>
  </div>

  <div class="note">
    <b>How to read this.</b> <span class="tier tier-first">First class</span> programs
    gained Initial Accreditation within the last ~12 months — usually recruiting their very
    first cohort, so the most open. <span class="tier tier-new">Still new</span> are
    Initial-Accreditation programs 12–24 months old. <span class="tier tier-watch">Watchlist</span>
    programs are approved but not yet recruitable — track them for next cycle.
    <br><br>
    <b>New programs are widely considered easier to match into</b> (they interview broadly,
    skew community/hospital, often have no published USMLE cutoff) — this is strong
    practitioner consensus, not a proven fact. The trade-off is real risk: you would be part
    of the test class, program directors can turn over, and each program still faces its
    first full ACGME site visit (~2 years in). Verify current details on each program's ADS
    detail page before applying, and treat any "with Warning" status as a yellow flag.
    Visa sponsorship is often unlisted for brand-new programs (shown as "unknown").
  </div>

  <footer>
    Data pulled from the ACGME public Accreditation Data System only. Social-media and
    community lists are useful early leads but are not authoritative — always confirm
    against ADS. Generated by the <b>new-im-programs</b> skill.
  </footer>
</div>

<script>
  var sortState = {{ col: -1, dir: 1 }};
  function applyFilters() {{
    var q = document.getElementById('q').value.trim().toLowerCase();
    var tier = document.getElementById('tier').value;
    var state = document.getElementById('state').value;
    var rows = document.querySelectorAll('#tbl tbody tr');
    var shown = 0;
    rows.forEach(function(r) {{
      var ok = (!tier || r.dataset.tier === tier)
            && (!state || r.dataset.state === state)
            && (!q || r.dataset.search.indexOf(q) !== -1);
      r.style.display = ok ? '' : 'none';
      if (ok) shown++;
    }});
    document.getElementById('count').textContent = shown + ' shown';
    document.getElementById('empty').style.display = shown ? 'none' : '';
  }}
  function sortBy(col) {{
    var tbody = document.querySelector('#tbl tbody');
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    sortState.dir = (sortState.col === col) ? -sortState.dir : 1;
    sortState.col = col;
    rows.sort(function(a, b) {{
      var av = a.children[col].getAttribute('data-sort') || '';
      var bv = b.children[col].getAttribute('data-sort') || '';
      if (av < bv) return -1 * sortState.dir;
      if (av > bv) return 1 * sortState.dir;
      return 0;
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
    document.querySelectorAll('#tbl th .arrow').forEach(function(s) {{ s.textContent = ''; }});
    var arrow = document.querySelectorAll('#tbl th')[col].querySelector('.arrow');
    if (arrow) arrow.textContent = sortState.dir > 0 ? '\\u25B2' : '\\u25BC';
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
