#!/usr/bin/env python3
# Trade Log + CSV: show the exit DATE next to the exit time (carried trades exit on a later day).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*EXITDATE*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
 ('      <th>Exit</th><th class="right">XP</th>\n      <th>Reason</th><th class="right">P&L</th>',
  '      <th>Exit date</th><th>Exit</th><th class="right">XP</th>\n      <th>Reason</th><th class="right">P&L</th>'),
 ('        <td>${t.xt}</td><td class="right">${fmt2(t.xp)}</td>\n        <td>${t.reason}</td>',
  '        <td>${fmtD(t.exitDate||t.date)}</td><td>${t.xt}</td><td class="right">${fmt2(t.xp)}</td>\n        <td>${t.reason}</td>'),
 ("lines.push([fmtD(t.date),t.instrument,t.leg,t.strike,t.et,t.ep,t.xt,t.xp,t.reason,Math.round(t.pnl)].map(csvCell).join(','));",
  "lines.push([fmtD(t.date),t.instrument,t.leg,t.strike,t.et,t.ep,fmtD(t.exitDate||t.date)+' '+t.xt,t.xp,t.reason,Math.round(t.pnl)].map(csvCell).join(','));"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor count %d: %s" % (s.count(a), a[:60])); sys.exit(1)
    s = s.replace(a, b)
s = s.replace("</script>\n</body>", "/*EXITDATE*/\n</script>\n</body>", 1)
shutil.copyfile(P, P + ".bak24")
io.open(P, "w", encoding="utf-8").write(s)
print("Trade Log shows exit date.")
