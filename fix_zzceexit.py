#!/usr/bin/env python3
# Cross Expiry: the 14:00 roll leg (next expiry, other index) is squared the NEXT trading day at the
# morning anchor (10:03) instead of being held to its own expiry day's 14:00. SL logic unchanged
# (09:20-10:03 window high, gap fill at market on the next-day open, 15:15 freeze on Tue/Thu).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CENEXT1003*/" in s:
    print("Already fixed."); sys.exit(0)
A1 = ("      const isSquareDay=(exp[pos.inst]===date);\n"
      "      const endM=isSquareDay?E:CLOSE;\n")
N1 = ("      const nxtDay=(date!==pos.entryDate);   /*CENEXT1003*/ // roll leg squares the NEXT trading day at the morning anchor (10:03)\n"
      "      const isSquareDay=nxtDay || (exp[pos.inst]===date);\n"
      "      const sqM=nxtDay?parseTime(MORN):E;\n"
      "      const endM=isSquareDay?sqM:CLOSE;\n")
A2 = ("        const cand=ser.filter(r=>parseTime(r.time)<=E);\n"
      "        const bar=cand.length?cand[cand.length-1]:null;\n"
      "        if(bar) closeOut(date, bar.time, bar.p, (parseTime(bar.time) < E-5) ? 'DATAGAP' : 'ROLL'); else { carrySkips++; pos=null; }\n")
N2 = ("        const cand=ser.filter(r=>parseTime(r.time)<=sqM);\n"
      "        const bar=cand.length?cand[cand.length-1]:null;\n"
      "        if(bar) closeOut(date, bar.time, bar.p, (parseTime(bar.time) < sqM-5) ? 'DATAGAP' : (nxtDay ? 'SQ1003' : 'ROLL')); else { carrySkips++; pos=null; }\n")
A3 = "off after 15:15)</option>"
for a in (A1, A2, A3):
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
s = s.replace(A1, N1).replace(A2, N2).replace(A3, "off after 15:15; roll leg exits next day 10:03)</option>")
shutil.copyfile(P, P + ".bak14")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry: roll leg squares next day at 10:03.")
