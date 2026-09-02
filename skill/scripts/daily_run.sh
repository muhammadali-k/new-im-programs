#!/usr/bin/env bash
# One-shot daily scan: fetch ADS → merge into programs.json → render HTML → build the e-mail digest.
# Works on the laptop and inside the cloud routine (no browser needed).
#
# Usage: daily_run.sh [OUTPUT_DIR]            (env: RUN_DATE=YYYY-MM-DD, default = today in America/Phoenix)
#   OUTPUT_DIR holds programs.json and new-im-programs.html and gets a runs/ folder with the per-day
#   snapshot, changes, and digest files. Default: ~/Library/CloudStorage/Dropbox/IM-Residency-New-Programs
#
# Exit codes: 0 ok · 2 fetch failed (programs.json untouched; digest says so) · other = script error
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HOME/Library/CloudStorage/Dropbox/IM-Residency-New-Programs}"
RUN_DATE="${RUN_DATE:-$(TZ=America/Phoenix date +%F)}"
RUNS="$OUT/runs"
mkdir -p "$RUNS"

# PDF text extraction: pypdf preferred; install it if neither pypdf nor pdftotext is available.
if ! python3 -c "import pypdf" 2>/dev/null && ! command -v pdftotext >/dev/null; then
  python3 -m pip install --quiet --user pypdf 2>/dev/null || python3 -m pip install --quiet pypdf || true
fi

SNAP="$RUNS/ads_snapshot_$RUN_DATE.json"
CHG="$RUNS/changes_$RUN_DATE.json"
echo "== fetch ADS ($RUN_DATE)"
python3 "$HERE/fetch_ads.py" --out "$SNAP" --run-date "$RUN_DATE"
echo "== merge into programs.json"
python3 "$HERE/update_programs.py" "$SNAP" "$OUT/programs.json" --run-date "$RUN_DATE" --changes "$CHG"
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "== render tracker"
  python3 "$HERE/render_html.py" "$OUT/programs.json" "$OUT/new-im-programs.html"
fi
echo "== digest"
python3 "$HERE/digest.py" "$CHG" "$OUT/programs.json" \
  --html "$RUNS/digest_$RUN_DATE.html" --text "$RUNS/digest_$RUN_DATE.txt" --subject "$RUNS/digest_$RUN_DATE.subject"
echo "== done: subject=$(cat "$RUNS/digest_$RUN_DATE.subject")"
echo "   digest html: $RUNS/digest_$RUN_DATE.html"
echo "   digest text: $RUNS/digest_$RUN_DATE.txt"
exit "$rc"
