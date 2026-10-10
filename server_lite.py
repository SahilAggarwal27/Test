#!/usr/bin/env python3
# /slice diet: send only what the strategies use, so long ranges (months/years) load fast:
#   - NIFTY + SENSEX only
#   - nearest expiry per index per day (the contract every strategy trades)
#   - strikes within +-8 steps of spot (rows returned in time order)
# ~84k rows/day -> ~10k rows/day. Self-testing: times before/after, auto-reverts on failure.
import io, re, sys, time, shutil, subprocess, py_compile, urllib.request
BASE = "/root/kite"; P = f"{BASE}/cloud_server.py"; SVC = "cloudserver.service"
URL = "http://127.0.0.1:8080/slice?from=2026-03-02&to=2026-03-06"
src = io.open(P, encoding="utf-8").read()
if "# LITESLICE" in src:
    print("Already applied."); sys.exit(0)
OLD = "              AND (spot IS NULL OR abs(strike - spot) <= 10 * (CASE WHEN instrument = 'NIFTY' THEN 50 ELSE 100 END))\n"
NEW = ("              AND instrument IN ('NIFTY','SENSEX')\n"
       "              AND (spot IS NULL OR abs(strike - spot) <= 8 * (CASE WHEN instrument = 'NIFTY' THEN 50 ELSE 100 END))\n"
       "            QUALIFY dense_rank() OVER (PARTITION BY instrument, substr(datetime,1,10) ORDER BY expiry) = 1\n"
       "            ORDER BY datetime\n")
if src.count(OLD) != 1:
    sys.exit("ABORT: run server_fast.py first (fast query not found) - nothing changed")
newsrc = src.replace(OLD, NEW).rstrip("\n") + "\n# LITESLICE\n"

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

t0, n0 = timed(); print(f"BEFORE: {t0 and round(t0,1)}s, {n0} lines")
shutil.copyfile(P, P + ".bak_lite")
io.open(P, "w", encoding="utf-8").write(newsrc)
try:
    py_compile.compile(P, doraise=True)
except Exception as e:
    shutil.copyfile(P + ".bak_lite", P); sys.exit("ABORT: syntax error, reverted: %s" % e)
restart()
t1, n1 = timed(); print(f"AFTER:  {t1 and round(t1,1)}s, {n1} lines")
if t1 is None or not isinstance(n1, int) or n1 < 1000:
    shutil.copyfile(P + ".bak_lite", P); restart()
    sys.exit("New query failed -> REVERTED. Send me this output.")
print("OK - /slice slimmed. Revert:  cp cloud_server.py.bak_lite cloud_server.py && systemctl restart cloudserver.service")
