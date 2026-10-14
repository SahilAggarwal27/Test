#!/usr/bin/env python3
# Cross Expiry — reference window as traded live (Sahil, Oct 2026):
#  - strikes of BOTH indices fixed at 10:05 (ATM at 10:05)
#  - entry trigger = LOW of the 09:20-10:05 window (lowest candle low), SL = HIGH of 09:20-10:05
#  - entries/re-entries only after 10:05 (both sides allowed, re-entry after SL as before)
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CE1005*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
 ("  const a=parseTime('09:20'), b=parseTime('10:03');\n  let hi=null;",
  "  const a=parseTime('09:20'), b=parseTime('10:05');   /*CE1005*/\n  let hi=null;"),
 ("  morn = morn || '10:03';", "  morn = morn || '10:05';"),
 ("  const ref = { CE:{lo:c0.l, hi:wHi(ce)}, PE:{lo:p0.l, hi:wHi(pe)} };",
  "  const wLo = leg => { const a=parseTime('09:20'), b=parseTime(morn); let l=null; for(const r of leg){ const m=parseTime(r.time); if(m>=a && m<=b && (l===null || r.l<l)) l=r.l; } return l; };\n"
  "  const ref = { CE:{lo:wLo(ce), hi:wHi(ce)}, PE:{lo:wLo(pe), hi:wHi(pe)} };   // trigger = 09:20-10:05 window LOW"),
 ("  const MORN=(params.morningTime||'10:03');", "  const MORN=(params.morningTime||'10:05');"),
 ("          for(const r of L){ const m=parseTime(r.time); if(m>=w0 && m<=mornM && (hi===null||r.h>hi)) hi=r.h; }\n"
  "          ref[sd]=(a0 && hi!==null && hi>a0.l)?{lo:a0.l,hi}:null; }",
  "          let lo=null; for(const r of L){ const m=parseTime(r.time); if(m>=w0 && m<=mornM){ if(hi===null||r.h>hi) hi=r.h; if(lo===null||r.l<lo) lo=r.l; } }\n"
  "          ref[sd]=(a0 && hi!==null && lo!==null && hi>lo)?{lo,hi}:null; }   // trigger = 09:20-10:05 window LOW"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor count %d: %s" % (s.count(a), a[:60])); sys.exit(1)
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak22")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry: strikes at 10:05, trigger = 09:20-10:05 low, SL = 09:20-10:05 high.")
