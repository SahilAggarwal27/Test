#!/usr/bin/env python3
# Range Breakout / Time-Based with Next-Day carry skipped every EXPIRY day (the contract
# has no next-day data) and days where the stored expiry was a day off. Now:
#  - on the contract's expiry day the carry squares off at the exit time instead of skipping
#  - on the last loaded day the open position is marked at the close (same as Cross Expiry)
#  - rows whose stored expiry is within 1 day of the chosen one are accepted
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*RBEXP*/" in s:
    print("Already fixed."); sys.exit(0)
OLD = ("        if (!day2.length) { carrySkips++; continue; }   // no next-day data -> skip, do NOT fake a same-day exit\n"
       "        tradeWin = day1.concat(day2);")
NEW = ("        let sqTo = null;   /*RBEXP*/\n"
       "        if (!day2.length) {\n"
       "          const expToday = (tgt && tgt <= date) || (typeof ceCalendarExp === 'function' && ceCalendarExp(date, inst) === date);\n"
       "          if (expToday) sqTo = exitMin;                                                  // contract expires today -> square at exit time\n"
       "          else if (dates.indexOf(date) === dates.length - 1) sqTo = parseTime('15:30');  // last loaded day -> mark at close (like Cross Expiry)\n"
       "          else { carrySkips++; continue; }                                               // genuinely missing next-day data -> skip\n"
       "        }\n"
       "        tradeWin = day2.length ? day1.concat(day2) : day1.filter(r => parseTime(r.time) <= sqTo);")
OKE = "      const okE = r => (!r.exp || !tgt || r.exp === tgt);"
OKE2 = "      const okE = r => (!r.exp || !tgt || r.exp === tgt || Math.abs((new Date(r.exp) - new Date(tgt)) / 86400000) <= 1);"
if s.count(OLD) != 2 or s.count(OKE) != 1:
    print("ABORT: anchors not found (%d, %d)" % (s.count(OLD), s.count(OKE))); sys.exit(1)
s = s.replace(OLD, NEW).replace(OKE, OKE2)
shutil.copyfile(P, P + ".bak12")
io.open(P, "w", encoding="utf-8").write(s)
print("Range Breakout trades every day (expiry-day carry squares off).")
