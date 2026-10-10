#!/usr/bin/env python3
# Adds collected option data that is NOT yet in the /slice index (master_pq) into it.
# Sources: recent_data.csv + kite_live_data.csv. Only rows missing from the index are added
# (matched on instrument+datetime+strike), written as new parquet files in the matching
# yr=YYYY folder with the SAME columns as the existing files, so /slice keeps working.
#   python3 archive_live.py        -> dry run: shows what would be added, writes nothing
#   python3 archive_live.py go     -> writes, then installs a nightly cron (16:45 IST Mon-Fri)
import duckdb, glob, os, sys, time, subprocess
BASE = os.environ.get("KITE_DIR", "/root/kite")
PQ = BASE + "/master_pq"
GO = len(sys.argv) > 1 and sys.argv[1] == "go"
SRCS = [f for f in ("recent_data.csv", "kite_live_data.csv") if os.path.isfile(f"{BASE}/{f}")]
KEYS = ["instrument", "datetime", "strike", "expiry", "spot", "ce_ltp", "pe_ltp"]

parts = sorted(d for d in glob.glob(PQ + "/*") if os.path.isdir(d))
if not parts: sys.exit("ABORT: no partitions in " + PQ)
pref = os.path.basename(parts[-1]).split("=")[0]           # e.g. 'yr'
sample = sorted(glob.glob(parts[-1] + "/*.parquet"))[0]
con = duckdb.connect(); con.execute("SET memory_limit='1500MB'"); con.execute("SET threads=1")
schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{sample}', hive_partitioning=false)").fetchall()
fcols = [(r[0], r[1]) for r in schema]                        # physical file columns + types
print("index partitions:", os.path.basename(parts[0]), "...", os.path.basename(parts[-1]))
print("file columns:", fcols)
for k in ("instrument", "datetime", "strike", "ce_ltp", "pe_ltp"):
    if k not in dict(fcols): sys.exit("ABORT: index has no column " + k)
if not SRCS: sys.exit("ABORT: no source CSVs")

def src_sql(f):
    hdr = con.execute(f"SELECT * FROM read_csv_auto('{BASE}/{f}', header=true, all_varchar=true) LIMIT 0").description
    have = {d[0] for d in hdr}
    sel = []
    for c, t in fcols:
        sel.append(f"TRY_CAST(NULLIF(\"{c}\",'') AS {t}) AS \"{c}\"" if c in have else f"CAST(NULL AS {t}) AS \"{c}\"")
    return f"SELECT {', '.join(sel)} FROM read_csv_auto('{BASE}/{f}', header=true, all_varchar=true)"

con.execute("CREATE TEMP TABLE newrows AS " + " UNION ALL ".join(src_sql(f) for f in SRCS))
con.execute("DELETE FROM newrows WHERE instrument IS NULL OR datetime IS NULL OR strike IS NULL")
tot, bad = con.execute("SELECT count(*), count(*) FILTER (WHERE ce_ltp IS NULL AND pe_ltp IS NULL) FROM newrows").fetchone()
if tot and bad > 0.05 * tot: sys.exit(f"ABORT: {bad}/{tot} rows lost their prices converting to the index types - nothing written")
miny = con.execute("SELECT min(substr(CAST(datetime AS VARCHAR),1,4)) FROM newrows").fetchone()[0]
idx = f"read_parquet('{PQ}/*/*.parquet', hive_partitioning=true)"
con.execute(f"""CREATE TEMP TABLE add AS
  SELECT DISTINCT ON (n.instrument, CAST(n.datetime AS VARCHAR), n.strike) n.* FROM newrows n
  WHERE NOT EXISTS (SELECT 1 FROM {idx} o WHERE o.{pref} >= {int(miny)}
     AND o.instrument = n.instrument AND CAST(o.datetime AS VARCHAR) = CAST(n.datetime AS VARCHAR) AND o.strike = n.strike)""")
summary = con.execute("SELECT substr(CAST(datetime AS VARCHAR),1,7) m, count(*) FROM add GROUP BY 1 ORDER BY 1").fetchall()
print("rows to add per month:", summary if summary else "none (index already complete)")
if not GO:
    print("DRY RUN - nothing written. Run:  python3 archive_live.py go"); sys.exit(0)
ts = time.strftime("%Y%m%d_%H%M%S")
for (y,) in con.execute("SELECT DISTINCT substr(CAST(datetime AS VARCHAR),1,4) FROM add ORDER BY 1").fetchall():
    d = f"{PQ}/{pref}={int(y)}"; os.makedirs(d, exist_ok=True)
    out = f"{d}/added_{ts}.parquet"
    con.execute(f"COPY (SELECT * FROM add WHERE substr(CAST(datetime AS VARCHAR),1,4)='{y}' ORDER BY datetime) TO '{out}' (FORMAT parquet)")
    print("wrote", out)
# check /slice-style read still works across all files
n = con.execute(f"SELECT count(*) FROM {idx} WHERE {pref} >= {int(miny)}").fetchone()[0]
print("index readable OK, rows since", miny, "=", n)
cron = f"45 16 * * 1-5 cd {BASE} && python3 {BASE}/archive_live.py go >> {BASE}/archive.log 2>&1"
cur = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
if "archive_live.py" not in cur:
    subprocess.run("crontab -", shell=True, input=cur.rstrip("\n") + "\n" + cron + "\n", text=True)
    print("nightly archive cron installed (16:45 Mon-Fri)")
