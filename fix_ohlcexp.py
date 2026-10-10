#!/usr/bin/env python3
# The OHLC file's expiry dates are one day early (Mon/Wed instead of Tue/Thu), which made
# Cross Expiry roll on the wrong days. OHLC rows now supply ONLY High/Low; the expiry is
# taken from the /slice row for the same minute (or the weekly calendar if none).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*OHLCEXP*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
("const OHLC_SEEN = new Set();", "const OHLC_SEEN = new Map(); /*OHLCEXP*/"),
("  const exp = r.expiry || '';", "  const exp = OHLC_MODE ? '' : String(r.expiry || '').slice(0,10);   // OHLC expiry is unreliable -> ignore"),
("  if (OHLC_MODE) { OHLC_SEEN.add(bkey); } else if (OHLC_SEEN.has(bkey)) { droppedDup++; return; }",
 "  if (!OHLC_MODE && OHLC_SEEN.has(bkey)) { const o = OHLC_SEEN.get(bkey); if (o && !o.exp && exp) o.exp = exp; droppedDup++; return; }"),
("  GROUPED[date][r.instrument][r.strike].push({ time, ce: r.ce_ltp, pe: r.pe_ltp, ce_h: r.ce_h, ce_l: r.ce_l, pe_h: r.pe_h, pe_l: r.pe_l, spot: r.spot, exp });",
 "  const _row = { time, ce: r.ce_ltp, pe: r.pe_ltp, ce_h: r.ce_h, ce_l: r.ce_l, pe_h: r.pe_h, pe_l: r.pe_l, spot: r.spot, exp };\n  GROUPED[date][r.instrument][r.strike].push(_row);\n  if (OHLC_MODE) OHLC_SEEN.set(bkey, _row);"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
for a, b in R:
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak6")
io.open(P, "w", encoding="utf-8").write(s)
print("OHLC expiry fixed.")
