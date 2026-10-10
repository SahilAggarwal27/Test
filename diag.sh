#!/bin/bash
# Data diagnostic: where does each month of 2026 live? (read-only, changes nothing)
cd /root/kite
echo "### files"; ls /root/kite
for f in $(ls *.csv data/*.csv 2>/dev/null); do
  echo; echo "== $f  ($(du -h "$f" | cut -f1))"
  head -1 "$f" | cut -c1-150
  echo "first: $(sed -n 2p "$f" | cut -c1-120)"
  echo "last:  $(tail -1 "$f" | cut -c1-120)"
done
echo; echo "### 2026 rows per month in small CSVs (<400MB)"
for f in $(ls *.csv data/*.csv 2>/dev/null); do
  [ "$(stat -c%s "$f")" -lt 400000000 ] || continue
  c=$(grep -o "2026-[0-9][0-9]-" "$f" | sort | uniq -c | tr '\n' ' ')
  echo "$f: $c"
done
echo; echo "### parquet index (what /slice serves)"
grep -n "PQ *=" cloud_server.py | head -3
python3 - <<'PY'
import re, glob
src = open('/root/kite/cloud_server.py').read()
m = re.search(r"PQ\s*=\s*(?:Path\()?['\"]([^'\"]+)['\"]", src)
pq = m.group(1) if m else None
print("PQ path:", pq)
try:
    import duckdb
    if pq:
        q = f"SELECT substr(datetime,1,7) m, count(*) FROM read_parquet('{pq}/*/*.parquet', hive_partitioning=true) WHERE yr>=2025 GROUP BY 1 ORDER BY 1"
        for r in duckdb.sql(q).fetchall(): print(r)
except Exception as e:
    print("duckdb error:", e)
PY
