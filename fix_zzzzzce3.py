#!/usr/bin/env python3
# Cross Expiry — 3 scenarios (params.ceMode), everything else on Tue/Thu squares at 14:00 as before:
#  sq14     = 1) square all positions at 14:00, no next-expiry position
#  roll1525 = 2) at 14:00 open the next-expiry position (other index) and square it at 15:25 (exit time)
#  roll1003 = 3) at 14:00 open the next-expiry position, carry it, square next trading day at 10:03
# Next-expiry position = "assume the morning trigger": on the next-expiry contract (ATM at 10:03) run the
# 10:03 morning-trigger logic up to 14:00; the side live at 14:00 is taken and SOLD AT THE ACTUAL 14:00
# MARKET PRICE (as tradable live), SL = its 09:20-10:03 high (15:15 freeze on Tue/Thu).
# Strategy dropdown rebuilt: old Cross Expiry / Compare-with-Cross-Expiry options removed.
import io, os, re, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CE3*/" in s:
    print("Already fixed."); sys.exit(0)
def must(a, n=1):
    if s.count(a) != n:
        print("ABORT: anchor count %d != %d: %s" % (s.count(a), n, a[:70])); sys.exit(1)

# 1) side + entry price from the NEXT-expiry contract's morning trigger
A1 = "      const side=morning.side;\n      if(side){\n"
must(A1)
s = s.replace(A1,
"      const ceM = params.ceMode || 'roll1003';   /*CE3*/\n"
"      const nxM = (ceM === 'sq14') ? {side:null} : ceMorningLeg(date, nxt, ENTRY, 1, MORN);   // morning trigger on the next-expiry contract\n"
"      const side = nxM.side;\n"
"      if(side){\n")
A2 = "            pos={inst:nxt, side, strike, exp:nexp, et:eb.time, ep:eb.p, sl, entryDate:date};\n"
must(A2)
s = s.replace(A2,
"            pos={inst:nxt, side, strike, exp:nexp, et:eb.time, ep:eb.p, sl, entryDate:date};   // entry = actual 2 PM market price\n")
# 2) entry-day scan: scenario 2 squares at the exit time (15:25)
A3 = ("            for(const r of ceLeg(date, nxt, strike, nexp, side)){ const m=parseTime(r.time);\n"
      "              if(m<E || m>CLOSE) continue;\n"
      "              if(m<=slCut && r.h>=pos.sl){ closeOut(date, r.time, pos.sl, 'SL'); break; } }\n")
must(A3)
s = s.replace(A3,
"            const endR=(ceM==='roll1525') ? parseTime(params.exitTime||'15:25') : CLOSE; let lastB=null;\n"
"            for(const r of ceLeg(date, nxt, strike, nexp, side)){ const m=parseTime(r.time);\n"
"              if(m<E || m>endR) continue; lastB=r;\n"
"              if(m<=slCut && r.h>=pos.sl){ closeOut(date, r.time, pos.sl, 'SL'); break; } }\n"
"            if(pos && ceM==='roll1525'){ if(lastB) closeOut(date, lastB.time, lastB.p, 'SQ1525'); else { carrySkips++; pos=null; } }\n")

# 3) ceMode param from the selected Strategy option
A4 = "    rbExpMode: ($('rbExpMode') ? $('rbExpMode').value : 'carry'),\n"
must(A4, 2)
s = s.replace(A4, A4 + "    ceMode: (function(){ const o=$('strategy').options[$('strategy').selectedIndex]; return (o && o.dataset.ce) || 'roll1003'; })(),\n")

# 4) Strategy dropdown rebuilt
m = re.search(r'(<select id="strategy">\n)(.*?)(    </select>)', s, re.S)
if not m:
    print("ABORT: strategy select not found"); sys.exit(1)
OPTS = (
'      <option value="time_based" selected>Time-Based Short Straddle (sell at entry, exit at exit time)</option>\n'
'      <option value="breakdown" data-rb="carry">Range Breakout (Sell Below Low, SL = High)</option>\n'
'      <option value="cross_expiry" data-ce="sq14">Cross Expiry \u2014 1) Square all positions at 14:00 (no next-expiry position)</option>\n'
'      <option value="cross_expiry" data-ce="roll1525">Cross Expiry \u2014 2) 14:00 next-expiry position, square 15:25</option>\n'
'      <option value="cross_expiry" data-ce="roll1003">Cross Expiry \u2014 3) 14:00 next-expiry position, carry, square next day 10:03</option>\n'
'      <option value="compare_ce">\u2696\ufe0f Compare: Cross Expiry \u2014 all 3 scenarios</option>\n'
'      <option value="compare_rb">\u2696\ufe0f Compare: Range Breakout \u2014 Tue/Thu square 15:25 vs 14:00</option>\n')
s = s[:m.start(2)] + OPTS + s[m.end(2):]

shutil.copyfile(P, P + ".bak18")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry 3 scenarios added; dropdown rebuilt.")
