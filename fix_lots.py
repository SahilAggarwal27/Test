#!/usr/bin/env python3
# NIFTY lot sizes: 75 from 26-Dec-2024, 65 from 31-Dec-2025 (matches contract notes: 2015 qty = 31 lots).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*LOTFIX*/" in s:
    print("Already fixed."); sys.exit(0)
OLD = "NIFTY:     [['2021-07-22',75], ['2024-04-25',50], ['2025-12-26',25], ['2025-12-30',75], ['9999-12-31',75]],"
NEW = "NIFTY:     [['2021-07-22',75], ['2024-04-25',50], ['2024-12-26',25], ['2025-12-30',75], ['9999-12-31',65]], /*LOTFIX*/"
if s.count(OLD) != 1:
    print("ABORT: lot table not found."); sys.exit(1)
shutil.copyfile(P, P + ".bak4")
io.open(P, "w", encoding="utf-8").write(s.replace(OLD, NEW))
print("Lots fixed.")
