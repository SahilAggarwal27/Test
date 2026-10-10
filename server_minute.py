#!/usr/bin/env python3
# /slice: one row per minute instead of every tick (the data has several ticks per minute).
#   close = last tick of the minute, High/Low = max/min of the minute's ticks (or stored H/L)
# -> ~4-5x fewer rows AND real candle High/Low for every year, not just since Sep-2026.
# Self-testing: times before/after, auto-reverts on failure.
import io, re, sys, time, shutil, subprocess, py_compile, urllib.request
BASE = "/root/kite"; P = f"{BASE}/cloud_server.py"; SVC = "cloudserver.service"
URL = "http://127.0.0.1:8080/slice?from=2026-03-02&to=2026-03-06"
src = io.open(P, encoding="utf-8").read()
if "# MINUTESLICE" in src:
    print("Already applied."); sys.exit(0)
if "# LITESLICE" not in src:
    sys.exit("ABORT: run server_lite.py first - nothing changed")
m = re.search(r'f"""SELECT instrument, datetime, spot.*?"""', src, re.S)
if not m or "QUALIFY" not in m.group(0): sys.exit("ABORT: slim query not found - nothing changed")
old = m.group(0)
frm = re.search(r"FROM read_parquet\(.*?\)\n", old).group(0)
where = re.search(r"(WHERE .*?)\n\s*QUALIFY", old, re.S).group(1)
new = ('f"""SELECT instrument, dtm AS datetime, spot, strike, expiry, ce_ltp, pe_ltp, ce_h, ce_l, pe_h, pe_l FROM (\n'
       "              SELECT instrument, substr(datetime,1,16) AS dtm, arg_max(spot, datetime) AS spot, strike, expiry,\n"
       "                     arg_max(ce_ltp, datetime) AS ce_ltp, arg_max(pe_ltp, datetime) AS pe_ltp,\n"
       "                     max(coalesce(ce_h, ce_ltp)) AS ce_h, min(coalesce(ce_l, ce_ltp)) AS ce_l,\n"
       "                     max(coalesce(pe_h, pe_ltp)) AS pe_h, min(coalesce(pe_l, pe_ltp)) AS pe_l\n"
       f"              {frm}"
       f"              {where}\n"
       "              GROUP BY instrument, substr(datetime,1,16), strike, expiry)\n"
       "            QUALIFY dense_rank() OVER (PARTITION BY instrument, substr(dtm,1,10) ORDER BY expiry) = 1\n"
       '            ORDER BY dtm"""')
newsrc = src.replace(old, new).rstrip("\n") + "\n# MINUTESLICE\n"

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

if __name__ == "__main__":
    t0, n0 = timed(); print(f"BEFORE: {t0 and round(t0,1)}s, {n0} lines")
    shutil.copyfile(P, P + ".bak_minute")
    io.open(P, "w", encoding="utf-8").write(newsrc)
    try:
        py_compile.compile(P, doraise=True)
    except Exception as e:
        shutil.copyfile(P + ".bak_minute", P); sys.exit("ABORT: syntax error, reverted: %s" % e)
    restart()
    t1, n1 = timed(); print(f"AFTER:  {t1 and round(t1,1)}s, {n1} lines")
    if t1 is None or not isinstance(n1, int) or n1 < 500:
        shutil.copyfile(P + ".bak_minute", P); restart()
        sys.exit("New query failed -> REVERTED. Send me this output.")
    print("OK - one row per minute. Revert:  cp cloud_server.py.bak_minute cloud_server.py && systemctl restart cloudserver.service")
