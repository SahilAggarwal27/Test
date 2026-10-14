#!/usr/bin/env python3
# Default re-entry = "Re-enter (original price / re-sell below the Low)", max re-entries 50.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*REDEFAULT*/" in s:
    print("Already fixed."); sys.exit(0)
R = [('      <option value="none" selected>Off', '      <option value="none">Off'),
     ('      <option value="original">Re-enter (Time-Based', '      <option value="original" selected>Re-enter (Time-Based'),
     ('<input type="number" id="maxReentries" value="2"', '<input type="number" id="maxReentries" value="50"')]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:50]); sys.exit(1)
    s = s.replace(a, b)
s = s.replace("</script>\n</body>", "/*REDEFAULT*/\n</script>\n</body>", 1)
shutil.copyfile(P, P + ".bak17")
io.open(P, "w", encoding="utf-8").write(s)
print("Re-entry default set to original price, max 50.")
