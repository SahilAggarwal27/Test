#!/usr/bin/env python3
# Plain-language labels for the Strategy / Scenario dropdowns and the compare screen.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*LABELS*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
 # Strategy list
 ('>Time-Based Short Straddle (sell at entry, exit at exit time)</option>', '>Fixed Time \u2014 sell at a set time, exit at a set time</option>'),
 ('>Range Breakout (Sell Below Low, SL = High)</option>', '>Range Breakout \u2014 sell when price falls below the morning low</option>'),
 ('>Cross Expiry (Tue/Thu 14:00 \u2014 next expiry, other index)</option>', '>Cross Expiry \u2014 on expiry day, switch to the next expiry at 2 PM</option>'),
 ('      <label>Scenario</label>\n', '      <label>Scenario \u2014 what happens on expiry day (Tue/Thu)</label>\n'),
 # Scenario dropdown
 (r"['rb:carry','Tue/Thu square 15:25']", r"['rb:carry','Exit at 3:25 PM']"),
 (r"['rb:sq14','Tue/Thu square 14:00']", r"['rb:sq14','Exit at 2:00 PM']"),
 (r"['rb:compare','\u2696\ufe0f Compare both (15:25 vs 14:00)']", r"['rb:compare','\u2696\ufe0f Compare: 3:25 PM vs 2:00 PM']"),
 (r"['ce:sq14','1) Square all positions at 14:00 (no next-expiry position)']", r"['ce:sq14','1) Exit everything at 2 PM \u2014 no new trade']"),
 (r"['ce:roll1525','2) 14:00 next-expiry position, square 15:25']", r"['ce:roll1525','2) Exit at 2 PM + new next-expiry trade, exit it at 3:25 PM']"),
 (r"['ce:roll1003','3) 14:00 next-expiry position, carry, square next day 10:03']", r"['ce:roll1003','3) Exit at 2 PM + new next-expiry trade, exit it next day 10:03 AM']"),
 (r"['ce:compare','\u2696\ufe0f Compare all 3 scenarios']", r"['ce:compare','\u2696\ufe0f Compare all 3']"),
 # Compare column names
 (r"const MODES = [['carry','RB \u2014 Tue/Thu sq 15:25'],['sq14','RB \u2014 Tue/Thu sq 14:00'],['roll14','RB \u2014 Tue/Thu 14:00 roll']];",
  r"const MODES = [['carry','Range Breakout \u2014 exit 3:25 PM'],['sq14','Range Breakout \u2014 exit 2:00 PM'],['roll14','Range Breakout \u2014 2 PM next-expiry trade']];"),
 ("const CEM = [['sq14','CE 1) square all 14:00'],['roll1525','CE 2) next-expiry, sq 15:25'],['roll1003','CE 3) next-expiry, next day 10:03']];",
  "const CEM = [['sq14','1) Exit all at 2 PM'],['roll1525','2) New trade, exit 3:25 PM'],['roll1003','3) New trade, exit next day 10:03']];"),
 # Compare screen metric labels
 (r"(net P&L)</div>", "(profit after costs)</div>"),
 (r"Ranking for ${fmtD(base.dateFrom)}", r"Best to worst, ${fmtD(base.dateFrom)}"),
 ("${row('Net P&L','net',money)}${row('Max Drawdown','mdd',money)}${row('Win % (days)','winPct',pct)}",
  "${row('Profit after costs','net',money)}${row('Biggest fall from a peak','mdd',money)}${row('Winning days %','winPct',pct)}"),
 ("${row('Trades','trades',n,false)}${row('SL hits','sl',n,false)}${row('Costs','costs',fmt,false)}",
  "${row('Number of trades','trades',n,false)}${row('Stop-loss hits','sl',n,false)}${row('Brokerage + slippage','costs',fmt,false)}"),
 (r"text:'Cumulative P&L (gross) \u2014 all strategies'", r"text:'Total profit over time (before costs)'"),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor count %d: %s" % (s.count(a), a[:60])); sys.exit(1)
    s = s.replace(a, b)
s = s.replace("</script>\n</body>", "/*LABELS*/\n</script>\n</body>", 1)
shutil.copyfile(P, P + ".bak20")
io.open(P, "w", encoding="utf-8").write(s)
print("Plain-language labels applied.")
