#!/usr/bin/env python3
# Speeds up /slice (2-3 min per 2 weeks -> seconds):
#  - High/Low are read straight from the index (it already stores ce_h/ce_l/pe_h/pe_l)
#    instead of re-reading + joining kite_ohlc_data.csv on every request
#  - only strikes within +-10 steps of spot are sent (all any strategy uses)
# Self-testing: times a request before/after, auto-reverts if the new one fails.
import io, os, re, sys, time, shutil, subprocess, py_compile, urllib.request
BASE = "/root/kite"; P = f"{BASE}/cloud_server.py"; SVC = "cloudserver.service"
URL = "http://127.0.0.1:8080/slice?from=2026-03-02&to=2026-03-06"
src = io.open(P, encoding="utf-8").read()
if "/*FASTSLICE*/" in src or "# FASTSLICE" in src:
    print("Already applied."); sys.exit(0)
m = re.search(r"\ndef query_slice\b.*?(?=\n(?:def |class |@)|\Z)", src, re.S)
if not m: sys.exit("ABORT: query_slice() not found - nothing changed")
fn = m.group(0)
q = re.search(r'f?"""\s*SELECT.*?"""', fn, re.S | re.I)
if not q: sys.exit("ABORT: SELECT block not found - nothing changed")
old = q.group(0)
if old.count("?") != 4 or not re.search(r"yr\s+BETWEEN\s+\?\s+AND\s+\?", old, re.I):
    sys.exit("ABORT: unexpected query shape - nothing changed\n" + old)
order = re.search(r"ORDER\s+BY.*?(?=\"\"\")", old, re.S | re.I)
order = order.group(0).strip() if order else ""
order = re.sub(r"\b[po]\.", "", order)
pq = re.search(r"read_parquet\('([^']+)'", old)
pqexpr = pq.group(1) if pq else "{PQ.as_posix()}/*/*.parquet"
new = ('f"""SELECT instrument, datetime, spot, strike, expiry, ce_ltp, pe_ltp, ce_h, ce_l, pe_h, pe_l\n'
       f"            FROM read_parquet('{pqexpr}', hive_partitioning=true, union_by_name=true)\n"
       "            WHERE yr BETWEEN ? AND ?\n"
       "              AND substr(datetime,1,10) BETWEEN ? AND ?\n"
       "              AND (spot IS NULL OR abs(strike - spot) <= 10 * (CASE WHEN instrument = 'NIFTY' THEN 50 ELSE 100 END))\n"
       f'            {order}"""')
newsrc = src.replace(fn, fn.replace(old, new) + "\n# FASTSLICE", 1)

def timed():
    t = time.time()
    try:
        with urllib.request.urlopen(URL, timeout=600) as r: body = r.read().decode("utf-8", "ignore")
        return time.time() - t, body.count("\n")
    except Exception as e:
        return None, str(e)
def restart():
    r = subprocess.run(["systemctl", "restart", SVC], capture_output=True, text=True)
    if r.returncode: print("WARNING: could not restart", SVC, "-", (r.stderr or r.stdout).strip())
    time.sleep(6)

print("old query:\n" + old)
t0, n0 = timed(); print(f"BEFORE: {t0 and round(t0,1)}s, {n0} lines")
shutil.copyfile(P, P + ".bak_fast")
io.open(P, "w", encoding="utf-8").write(newsrc)
try:
    py_compile.compile(P, doraise=True)
except Exception as e:
    shutil.copyfile(P + ".bak_fast", P); sys.exit("ABORT: syntax error, reverted: %s" % e)
restart()
t1, n1 = timed(); print(f"AFTER:  {t1 and round(t1,1)}s, {n1} lines")
if t1 is None or not isinstance(n1, int) or n1 < 2 or (isinstance(n0, int) and n0 > 2 and n1 < 2):
    shutil.copyfile(P + ".bak_fast", P); restart()
    sys.exit("New query failed -> REVERTED to the old version. Send me this output.")
print("OK - /slice is faster. Revert any time:  cp cloud_server.py.bak_fast cloud_server.py && systemctl restart cloudserver.service")
