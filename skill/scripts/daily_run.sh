#!/usr/bin/env bash
# One-shot daily scan: fetch ADS → merge into programs.json → render HTML → build the e-mail digest.
# Works on the laptop and inside the cloud routine (no browser needed).
#
# Usage: daily_run.sh [OUTPUT_DIR]            (env: RUN_DATE=YYYY-MM-DD, default = today in America/Phoenix)
#   OUTPUT_DIR holds programs.json and new-im-programs.html and gets a runs/ folder with the per-day
#   snapshot, changes, and digest files. Default: ~/Library/CloudStorage/Dropbox/IM-Residency-New-Programs
#
# Exit codes: 0 ok · 2 ADS fetch failed (programs.json untouched; digest says so) · other = script error
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HOME/Library/CloudStorage/Dropbox/IM-Residency-New-Programs}"
RUN_DATE="${RUN_DATE:-$(TZ=America/Phoenix date +%F)}"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

SNAP="$RUNS/ads_snapshot_$RUN_DATE.json"
CHG="$RUNS/changes_$RUN_DATE.json"
# Never reuse a snapshot from an earlier run of the same date (runs/ is committed to the repo).
rm -f "$SNAP" "$CHG"

# PDF text extraction: pypdf preferred; try to install it if neither pypdf nor pdftotext works.
if ! python3 -c "import sys; sys.modules['cryptography']=None; import pypdf" 2>/dev/null && ! command -v pdftotext >/dev/null; then
  python3 -m pip install --quiet --user pypdf 2>/dev/null || python3 -m pip install --quiet pypdf 2>/dev/null || true
fi

echo "== fetch ADS ($RUN_DATE)"
python3 "$HERE/fetch_ads.py" --out "$SNAP" --run-date "$RUN_DATE"
fetch_rc=$?
if [ ! -s "$SNAP" ]; then
  # fetch_ads.py died before writing anything — synthesize a failed snapshot so the digest is honest
  python3 - "$SNAP" "$RUN_DATE" "$fetch_rc" <<'PY'
import json, sys
json.dump({"run_date": sys.argv[2], "academic_years": [], "report8": [], "watchlist": [], "roster": {},
           "errors": [f"fetch_ads.py crashed (exit {sys.argv[3]}) before writing a snapshot"], "fetch_ok": False},
          open(sys.argv[1], "w"), indent=2)
PY
fi
echo "== merge into programs.json"
python3 "$HERE/update_programs.py" "$SNAP" "$OUT/programs.json" --run-date "$RUN_DATE" --changes "$CHG"
rc=$?
if [ "$fetch_rc" -ne 0 ] && [ "$rc" -eq 0 ]; then rc=2; fi
if [ "$rc" -eq 0 ]; then
  echo "== render tracker"
  python3 "$HERE/render_html.py" "$OUT/programs.json" "$OUT/new-im-programs.html"
fi
echo "== digest"
python3 "$HERE/digest.py" "$CHG" "$OUT/programs.json" \
  --html "$RUNS/digest_$RUN_DATE.html" --text "$RUNS/digest_$RUN_DATE.txt" --subject "$RUNS/digest_$RUN_DATE.subject"
echo "== done (fetch_rc=$fetch_rc rc=$rc): subject=$(cat "$RUNS/digest_$RUN_DATE.subject")"
echo "   digest html: $RUNS/digest_$RUN_DATE.html"
echo "   digest text: $RUNS/digest_$RUN_DATE.txt"
exit "$rc"
