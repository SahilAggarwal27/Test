#!/usr/bin/env python3
# Cross Expiry strikes as seen in the contract notes: fixed at 10:05 per side —
#   CE = first strike AT/ABOVE spot (ceil), PE = first strike AT/BELOW spot (floor)
#   e.g. spot 22,575 -> CE 22600 / PE 22550 (not one common ATM strike)
# Applies to the daily morning leg, the expiry-day morning leg and the 2 PM next-expiry leg.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CESTRIKE*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
 ("function ceAtm(date, inst, time){",
  "/*CESTRIKE*/ function ceStrike(date, inst, time, side){\n"
  "  const g = GROUPED[date] && GROUPED[date][inst]; const spec=SPECS[inst];\n"
  "  if(!g||!spec) return null;\n"
  "  for(const s of Object.keys(g)){ const row=g[s].find(r=>r.time===time); if(row&&row.spot!=null){ const q=row.spot/spec.step;\n"
  "    return (side==='CE' ? Math.ceil(q-1e-9) : Math.floor(q+1e-9))*spec.step; } }\n"
  "  return null;\n"
  "}\n"
  "function ceAtm(date, inst, time){"),
 ("  const atm  = ceAtm(date, inst, morn); if(atm===null) return {side:null, trades:[]};\n"
  "  const ce = ceLeg(date, inst, atm, nexp, 'CE');\n"
  "  const pe = ceLeg(date, inst, atm, nexp, 'PE');",
  "  const kC = ceStrike(date, inst, morn, 'CE'), kP = ceStrike(date, inst, morn, 'PE'); if(kC===null||kP===null) return {side:null, trades:[]};\n"
  "  const ce = ceLeg(date, inst, kC, nexp, 'CE');\n"
  "  const pe = ceLeg(date, inst, kP, nexp, 'PE');"),
 ("          trades.push({date, exitDate:date, instrument:cur, leg:mt.side, strike:matm,",
  "          trades.push({date, exitDate:date, instrument:cur, leg:mt.side, strike:ceStrike(date, cur, MORN, mt.side),"),
 ("      const atm=inst?ceAtm(date,inst,MORN):null;",
  "      const atm=inst?ceAtm(date,inst,MORN):null; const K=inst?{CE:ceStrike(date,inst,MORN,'CE'), PE:ceStrike(date,inst,MORN,'PE')}:null;"),
 ("        const legs={CE:ceLeg(date,inst,atm,best,'CE'), PE:ceLeg(date,inst,atm,best,'PE')}, ref={}, w0=parseTime('09:20');",
  "        const legs={CE:ceLeg(date,inst,K.CE,best,'CE'), PE:ceLeg(date,inst,K.PE,best,'PE')}, ref={}, w0=parseTime('09:20');"),
 ("dpos={inst, side:sd, strike:atm, exp:best,", "dpos={inst, side:sd, strike:K[sd], exp:best,"),
 ("        const nexp=ceNearestExp(date, nxt), strike=ceAtm(date, nxt, MORN);   /*ROLLSTRIKE*/",
  "        const nexp=ceNearestExp(date, nxt), strike=ceStrike(date, nxt, MORN, side);   /*ROLLSTRIKE*/"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor count %d: %s" % (s.count(a), a[:60])); sys.exit(1)
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak23")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry strikes: CE = strike above spot, PE = strike below spot, at 10:05.")
