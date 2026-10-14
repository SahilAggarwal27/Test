#!/usr/bin/env python3
# Cross Expiry scenario "As traded live (contract notes)" = ceMode 'live' (default):
#  - Expiry day (Tue/Thu): expiring index's morning-trigger leg squared at 14:00 (or SL)
#  - 14:00: the SAME side that is live on the expiring index is sold on the other index's next expiry,
#    ATM at 10:03, at the actual 14:00 market price; SL = that contract's 09:20-10:03 high (15:15 freeze Tue/Thu)
#  - That position is HELD (not squared next day) until SL or 14:00 on its own expiry day
#  - Daily morning-trigger leg (Mon/Wed/Fri) runs independently and carries overnight, as before
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CELIVE*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
 ("      const nxtDay=(date!==pos.entryDate);   /*CENEXT1003*/",
  "      const nxtDay=(date!==pos.entryDate) && ((params.ceMode||'live')!=='live');   /*CENEXT1003*/ /*CELIVE*/ // live: hold to SL / its expiry day"),
 ("      const ceM = params.ceMode || 'roll1003';   /*CE3*/",
  "      const ceM = params.ceMode || 'live';   /*CE3*/"),
 ("      const nxM = (ceM === 'sq14') ? {side:null} : ceMorningLeg(date, nxt, ENTRY, 1, MORN);",
  "      const nxM = (ceM === 'sq14') ? {side:null} : (ceM === 'live' ? morning : ceMorningLeg(date, nxt, ENTRY, 1, MORN));"),
 ("  const CEM = [['sq14','1) Exit all at 2 PM'],",
  "  const CEM = [['live','As traded live (contract notes)'],['sq14','1) Exit all at 2 PM'],"),
 (r"    cross_expiry: [['ce:sq14','1) Exit everything at 2 PM \u2014 no new trade'],",
  r"    cross_expiry: [['ce:live','As traded live \u2014 2 PM same-side next-expiry trade, held till SL / its expiry (contract notes)'],"
  "\n" r"                   ['ce:sq14','1) Exit everything at 2 PM \u2014 no new trade'],"),
 (r"['ce:compare','\u2696\ufe0f Compare all 3']", r"['ce:compare','\u2696\ufe0f Compare all']"),
 ("return (o && o.dataset.ce) || 'roll1003'; })(),", "return (o && o.dataset.ce) || 'live'; })(),"),
]
for a, b in R:
    n = s.count(a)
    if n < 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak21")
io.open(P, "w", encoding="utf-8").write(s)
print("Cross Expiry 'As traded live (contract notes)' scenario added (default).")
