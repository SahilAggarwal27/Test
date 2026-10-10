#!/usr/bin/env python3
# One-time setup of the server backtest engine (safe to re-run):
#  1. installs Node.js if missing   2. fetches engine.js from GitHub
#  3. runs it as a service (bt-engine, port 8090, auto-restart, starts on boot)
#  4. opens port 8090 in ufw if ufw is on   5. self-test: runs a real Compare job on your data
import os, re, sys, json, time, shutil, subprocess, urllib.request
BASE = "/root/kite"; ENG = f"{BASE}/engine"; REPO = "SahilAggarwal27/Test"
def sh(cmd, check=False):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode: sys.exit(f"FAILED: {cmd}\n{r.stdout}{r.stderr}")
    return r
# 1. node
v = sh("node --version").stdout.strip()
if not re.match(r"v(1[6-9]|[2-9]\d)\.", v):
    print("installing Node.js (1-2 min)...")
    sh("DEBIAN_FRONTEND=noninteractive apt-get update -y", True)
    sh("DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs", True)
    v = sh("node --version").stdout.strip()
print("node", v)
node = shutil.which("node") or "/usr/bin/node"
# 2. engine.js (exact latest commit, no CDN cache)
sha = sh(f"git ls-remote https://github.com/{REPO} refs/heads/main").stdout.split()[0]
os.makedirs(ENG, exist_ok=True)
src = urllib.request.urlopen(f"https://raw.githubusercontent.com/{REPO}/{sha}/engine.js", timeout=60).read()
open(f"{ENG}/engine.js", "wb").write(src)
print("engine.js", len(src), "bytes @", sha[:7])
# 3. service (heap sized to the droplet's RAM)
mem_mb = int(re.search(r"MemTotal:\s+(\d+)", open("/proc/meminfo").read()).group(1)) // 1024
heap = max(700, min(2500, int(mem_mb * 0.6)))
open("/etc/systemd/system/bt-engine.service", "w").write(f"""[Unit]
Description=Backtest engine (backtester.html strategies, server side)
After=network.target

[Service]
WorkingDirectory={BASE}
ExecStart={node} --max-old-space-size={heap} {ENG}/engine.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""")
sh("systemctl daemon-reload", True); sh("systemctl enable bt-engine", True); sh("systemctl restart bt-engine", True)
print(f"service bt-engine started (RAM {mem_mb} MB, heap {heap} MB)")
# 4. firewall
if "Status: active" in sh("ufw status").stdout:
    sh("ufw allow 8090/tcp"); print("ufw: port 8090 opened")
# 5. self-test on real data
def get(u): return json.loads(urllib.request.urlopen(u, timeout=30).read())
for _ in range(20):
    try: h = get("http://127.0.0.1:8090/health"); break
    except Exception: time.sleep(1)
else: sys.exit("engine did not start - run:  journalctl -u bt-engine -n 30")
print("health:", h)
params = {"dateFrom": "2026-10-05", "dateTo": "2026-10-09", "lots": 1, "brokerage": 1, "slippage": 1, "capital": 200000,
          "refStart": "09:20", "refEnd": "10:03", "entryTime": "10:03", "exitTime": "15:25", "slPct": 0.33,
          "dayMap": {"0": "NIFTY", "1": "NIFTY", "2": "SENSEX", "3": "SENSEX", "4": "NIFTY"}, "autoExpiry": True, "tradeAll": False,
          "candidateInsts": ["NIFTY", "SENSEX"], "expiryType": "nearest", "ceOffset": 0, "peOffset": 0, "carry": "nextday",
          "carryExitTime": "10:03", "reentryMode": "none", "reentrySL": "pct", "maxReentries": 2}
req = urllib.request.Request("http://127.0.0.1:8090/run", data=json.dumps({"kind": "compare", "params": params}).encode(), headers={"Content-Type": "application/json"})
jid = json.loads(urllib.request.urlopen(req, timeout=30).read())["id"]
t0 = time.time()
while True:
    time.sleep(2); j = get(f"http://127.0.0.1:8090/job/{jid}")
    if j["status"] in ("done", "error"): break
    if time.time() - t0 > 600: sys.exit("self-test timed out")
if j["status"] == "error": sys.exit("self-test FAILED: " + str(j.get("error")))
for k, name in (("ce", "Cross Expiry"), ("rb", "Range Breakout")):
    r = j["result"][k]; pnl = sum(x["pnl"] for x in r["dailyPnl"]) - r["costs"]
    print(f"self-test 05-09 Oct  {name}: {len(r['dailyPnl'])} days, {len(r['trades'])} trades, net {pnl:,.0f}")
print("\nDONE. Check from your PC:  http://168.144.122.216:8090/health  -> should show ok:true")
print("Then open the backtester fresh: it says 'Server engine connected' and every Run/Compare runs here.")
