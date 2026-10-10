#!/usr/bin/env python3
# Expiry dates in the collected data are unreliable (some feeds are a day early ->
# Mon/Wed treated as expiry). Cross Expiry now ALWAYS uses the weekly calendar
# (NIFTY Tue, SENSEX Thu, holiday -> previous trading day) and accepts rows whose
# stored expiry is within 1 day of it.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CALEXP*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
("  return ne || ceCalendarExp(date, inst);",
 "  return ceCalendarExp(date, inst) || ne;   /*CALEXP*/ // calendar first: stored expiry can be a day early"),
("  return g.filter(r=>!r.exp||r.exp===exp)",
 "  return g.filter(r=>!r.exp||r.exp===exp||Math.abs((new Date(r.exp)-new Date(exp))/86400000)<=1)"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
for a, b in R:
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak8")
io.open(P, "w", encoding="utf-8").write(s)
print("Calendar expiry enforced.")
