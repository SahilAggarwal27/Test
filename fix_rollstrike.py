#!/usr/bin/env python3
# Roll-leg strike = ATM at the morning anchor (10:03), matching live trading and the
# SL (that strike's 09:20-10:03 high). Was ATM at 14:00 -> wrong strike, meaningless SL.
# Also flags a roll square-up on a data gap (strike left ATM+-5 coverage) as DATAGAP.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*ROLLSTRIKE*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
("const nexp=ceNearestExp(date, nxt), strike=ceAtm(date, nxt, ENTRY);",
 "const nexp=ceNearestExp(date, nxt), strike=ceAtm(date, nxt, MORN);   /*ROLLSTRIKE*/ // strike = ATM at the morning anchor (as traded live)"),
("if(bar) closeOut(date, bar.time, bar.p, 'ROLL');",
 "if(bar) closeOut(date, bar.time, bar.p, (parseTime(bar.time) < E-5) ? 'DATAGAP' : 'ROLL');"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
for a, b in R:
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak5")
io.open(P, "w", encoding="utf-8").write(s)
print("Roll strike fixed.")
