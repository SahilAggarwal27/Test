#!/usr/bin/env python3
# Builds data_days.json: for every date, rows per index in the /slice index (master_pq)
# + live files, and how many rows carry candle High/Low. Read by the page's Data Calendar.
# Installs a nightly cron (16:55 Mon-Fri, after the 16:45 archive) on first run.
import duckdb, json, os, time, subprocess
BASE = os.environ.get("KITE_DIR", "/root/kite")
PQ = BASE + "/master_pq"
con = duckdb.connect(); con.execute("SET memory_limit='1500MB'"); con.execute("SET threads=1")
days = {}
def add(rows, hl_from_count=False):
    for inst, d, n, hl in rows:
        if not inst or not d or len(d) < 10: continue
        e = days.setdefault(d, {}).setdefault(inst, [0, 0])
        e[0] += int(n); e[1] += int(n if hl_from_count else (hl or 0))
idx = f"read_parquet('{PQ}/*/*.parquet', hive_partitioning=true, union_by_name=true)"
cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {idx} LIMIT 0").fetchall()}
hl = "count(ce_h)" if "ce_h" in cols else "0"
t0 = time.time()
add(con.execute(f"SELECT instrument, substr(CAST(datetime AS VARCHAR),1,10) d, count(*), {hl} FROM {idx} GROUP BY 1,2").fetchall())
for f, isohlc in (("kite_live_data.csv", False), ("kite_ohlc_data.csv", True)):
    p = f"{BASE}/{f}"
    if os.path.isfile(p):
        add(con.execute(f"SELECT instrument, substr(datetime,1,10) d, count(*), 0 FROM read_csv_auto('{p}', header=true, all_varchar=true) GROUP BY 1,2").fetchall(), isohlc)
out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "days": dict(sorted(days.items()))}
for name in ("data_days.json",):
    json.dump(out, open(f"{BASE}/{name}", "w"), separators=(",", ":"))
print(f"data_days.json: {len(days)} dates ({min(days)} -> {max(days)}) in {time.time()-t0:.0f}s")
cron = f"55 16 * * 1-5 cd {BASE} && python3 {BASE}/coverage_build.py >> {BASE}/coverage.log 2>&1"
cur = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
if "coverage_build.py" not in cur and not os.environ.get("KITE_DIR"):
    subprocess.run("crontab -", shell=True, input=cur.rstrip("\n") + "\n" + cron + "\n", text=True)
    print("nightly calendar refresh installed (16:55 Mon-Fri)")
