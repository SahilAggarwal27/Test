#!/usr/bin/env python3
# Cross Expiry realism fixes (why backtest showed profit while live lost):
#  1. Load candle High/Low (kite_ohlc_data.csv) on Run again - without it every
#     candle had High=Low, so morning SLs cost 0 and re-entries were free.
#  2. Morning leg SL = 09:20->anchor window HIGH (locked spec), trigger = anchor low;
#     zero-width ranges never trigger.
#  3. Overnight gap above SL fills at the next-day price, not the SL level.
# Safe: .bak3 backup, idempotent, aborts if any anchor missing.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CEFIX3*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
("const OHLC_SEEN = new Set(); let OHLC_MODE = false;",
 "const OHLC_SEEN = new Set(); let OHLC_MODE = false; let RANGE_FROM = null, RANGE_TO = null; /*CEFIX3*/"),
("  const time = sp[1].slice(0,5);\n  const exp = r.expiry || '';",
 "  if (RANGE_FROM && (date < RANGE_FROM || date > RANGE_TO)) return;   // keep only the selected range in memory\n  const time = sp[1].slice(0,5);\n  const exp = r.expiry || '';"),
("  resetData();\n  $('status').textContent = `Loading data ${from} \u2192 ${to}\u2026`;\n  setBar(5);\n  await streamCsv(`/slice?from=${from}&to=${to}`, 'range');",
 "  resetData();\n  OHLC_SEEN.clear(); RANGE_FROM = from; RANGE_TO = to;\n  $('status').textContent = `Loading data ${from} \u2192 ${to}\u2026`;\n  setBar(5);\n  OHLC_MODE = true;   // candle High/Low first (SL/trigger need real highs/lows)\n  await streamCsv('http://168.144.122.216:8080/data/kite_ohlc_data.csv', 'OHLC (high/low)');\n  OHLC_MODE = false;\n  await streamCsv(`/slice?from=${from}&to=${to}`, 'range');"),
("  const ref = { CE:{lo:c0.l, hi:c0.h}, PE:{lo:p0.l, hi:p0.h} };",
 "  // Trigger = anchor-candle LOW; SL = 09:20->anchor window HIGH (locked spec, same as the roll leg).\n  const wHi = leg => { const a=parseTime('09:20'), b=parseTime(morn); let h=null; for(const r of leg){ const m=parseTime(r.time); if(m>=a && m<=b && (h===null || r.h>h)) h=r.h; } return h; };\n  const ref = { CE:{lo:c0.l, hi:wHi(ce)}, PE:{lo:p0.l, hi:wHi(pe)} };\n  for(const k of ['CE','PE']) if(!(ref[k].hi > ref[k].lo)) ref[k].lo = -Infinity;   // zero-width range -> never trigger"),
("      let done=false;\n      for(const r of ser){ const m=parseTime(r.time); if(m<startM||m>endM) continue;",
 "      let done=false, first=true;\n      for(const r of ser){ const m=parseTime(r.time); if(m<startM||m>endM) continue;"),
("        if(m<=slCutoff && r.h>=pos.sl){ closeOut(date, r.time, pos.sl, 'SL'); done=true; break; } }",
 "        if(m<=slCutoff && r.h>=pos.sl){ const fx=(date!==pos.entryDate && first) ? Math.max(pos.sl, r.p) : pos.sl;   // overnight gap -> fill at market\n          closeOut(date, r.time, fx, 'SL'); done=true; break; }\n        first=false; }"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found:\n" + a[:80]); sys.exit(1)
for a, b in R:
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak3")
io.open(P, "w", encoding="utf-8").write(s)
print("Fixed. Hard-refresh (Ctrl+Shift+R) and re-run Cross Expiry.")
