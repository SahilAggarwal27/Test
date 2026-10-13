#!/usr/bin/env python3
# Range Breakout: Tue/Thu (expiry-day) handling, picked from a dropdown (rbExpMode):
#  carry   = current: carried position squares next day at the carry time (10:03); expiry-day entry squares at exit time
#  hold    = carried position is held through the expiry day and squared at the exit time (15:25)
#  sq14    = everything on the expiring contract squares at 14:00 on the expiry day, no roll
#  roll14  = on the expiry day everything on the expiring contract squares at 14:00; at 14:00 the live side is rolled
#            into the NEXT expiry (other index) exactly like Cross Expiry (ATM at 10:03, market entry, SL = 09:20-10:03
#            window high, 15:15 freeze on Tue/Thu) and squared the next trading day at 10:03
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*RBEXPMODE*/" in s:
    print("Already fixed."); sys.exit(0)

def must(a, n=1):
    if s.count(a) != n:
        print("ABORT: anchor count %d != %d: %s" % (s.count(a), n, a[:70])); sys.exit(1)

# 1) helpers inside the breakdown branch
A1 = "      const byTimeB = (a, b) => parseTime(a.time) - parseTime(b.time);\n"
must(A1)
s = s.replace(A1, A1 +
"      const rbx = params.rbExpMode || 'carry';   /*RBEXPMODE*/\n"
"      const rbRollM = parseTime(params.rbRollTime || '14:00');\n"
"      const rbIsExp = d => (typeof ceCalendarExp === 'function')\n"
"        ? (ceCalendarExp(d, inst) === d && (!tgt || Math.abs((new Date(tgt) - new Date(d)) / 86400000) <= 1))\n"
"        : (!!tgt && d === tgt);\n"
"      const rbCut = d => (rbx !== 'carry' && rbIsExp(d)) ? ((rbx === 'roll14' || rbx === 'sq14') ? rbRollM : exitMin) : parseTime(params.carryExitTime || params.exitTime);\n")

# 2) carried position: cut-off on the next day depends on whether that day is the contract's expiry
A2 = "          const same = mseries(nd).filter(r => parseTime(r.time) <= carryExitMin).slice().sort(byTimeB);"
must(A2)
s = s.replace(A2, "          const same = mseries(nd).filter(r => parseTime(r.time) <= rbCut(nd)).slice().sort(byTimeB);")

# 3) entry made on the expiry day itself: 14:00 in roll mode, else exit time (breakdown block = first occurrence)
A3 = "          if (expToday) sqTo = exitMin;"
must(A3, 2)
s = s.replace(A3, "          if (expToday) sqTo = (rbx === 'roll14' || rbx === 'sq14') ? rbRollM : exitMin;", 1)

# 4) same-day (intraday) mode on expiry day in roll mode -> 14:00
A4 = "          return tm > refEndMin && tm <= exitMin;"
must(A4)
s = s.replace(A4, "          return tm > refEndMin && tm <= (((rbx === 'roll14' || rbx === 'sq14') && rbIsExp(date)) ? rbRollM : exitMin);")

# 5) 14:00 roll into the next expiry (other index)
A5 = "    const reOpts = { reentryMode: params.reentryMode, reentrySL: params.reentrySL, maxReentries: params.maxReentries };\n"
must(A5)
ROLL = r"""    /*RBROLL*/ // Cross Expiry roll logic: live side at 14:00 on the expiring index -> same side, next expiry
    // (other index), ATM at 10:03, sold at market on the 14:00 bar; SL = 09:20-10:03 window high
    // (frozen after 15:15 on Tue/Thu); squared the NEXT trading day at 10:03.
    if (params.strategy === 'breakdown' && params.rbExpMode === 'roll14' && typeof ceCalendarExp === 'function' && ceCalendarExp(date, inst) === date) {
      const rollT = params.rbRollTime || '14:00', rollM = parseTime(rollT), morn = params.refEnd || '10:03', mornM = parseTime(morn);
      const side = ceMorningLeg(date, inst, rollT, 1, morn).side;
      let nx = null, nexp = null;
      for (const ix of ['NIFTY', 'SENSEX']) {
        if (ix === inst || !GROUPED[date][ix]) continue;
        const e = ceNearestExp(date, ix);
        if (e && e > date && (nexp === null || e < nexp)) { nexp = e; nx = ix; }
      }
      const strike = (side && nx) ? ceAtm(date, nx, morn) : null;
      const L0 = (strike !== null) ? ceLeg(date, nx, strike, nexp, side) : [];
      const eb = L0.find(r => parseTime(r.time) >= rollM);
      const wh = (strike !== null) ? ceWindowHigh(date, nx, strike, nexp, side) : null;
      const sl = (wh != null) ? wh : (eb ? eb.h : null);
      if (eb && sl != null) {
        const freeze = parseTime('15:15'), tt = [2, 4].includes(new Date(date).getDay());
        let x = null;
        for (const r of L0) { const m = parseTime(r.time); if (m < rollM) continue;
          if ((!tt || m <= freeze) && r.h >= sl) { x = { d: date, t: r.time, p: sl, why: 'SL' }; break; } }
        if (!x) {
          const di = dates.indexOf(date);
          for (let j = di + 1; j < dates.length && j <= di + 6 && !x; j++) {
            const L1 = ceLeg(dates[j], nx, strike, nexp, side).filter(r => parseTime(r.time) <= mornM);
            if (!L1.length) continue;
            const ft = [2, 4].includes(new Date(dates[j]).getDay());
            L1.forEach((r, k) => { if (!x && (!ft || parseTime(r.time) <= freeze) && r.h >= sl) x = { d: dates[j], t: r.time, p: k === 0 ? Math.max(sl, r.p) : sl, why: 'SL' }; });
            if (!x) { const b = L1[L1.length - 1]; x = { d: dates[j], t: b.time, p: b.p, why: 'SQ1003' }; }
          }
          if (!x && dates.indexOf(date) === dates.length - 1) { const b = L0[L0.length - 1]; x = { d: date, t: b.time, p: b.p, why: 'EOD' }; }
        }
        if (x) {
          const pnl = (eb.p - x.p) * lotFor(nx, x.d) * params.lots;
          trades.push({ reason: x.why, et: eb.time, ep: eb.p, xt: x.t, xp: x.p, pnl, fills: 1, date, exitDate: x.d, instrument: nx, leg: side, strike, roll: true });
          dailyPnl.push({ date, dow: ['Mon','Tue','Wed','Thu','Fri'][dayIdx], instrument: nx, atm: strike, pnl, nTrades: 1, slHits: x.why === 'SL' ? 1 : 0 });
        } else carrySkips++;
      }
    }
"""
s = s.replace(A5, A5 + ROLL)

# 6) params from both builders
for a in ("    carryExitTime: ($('carryExitHour') ? $('carryExitHour').value + ':' + $('carryExitMin').value : '15:25'),\n",
          "    carryExitTime: ($('carryExitHour')?$('carryExitHour').value+':'+$('carryExitMin').value:'15:25'),\n"):
    must(a)
    s = s.replace(a, a + "    rbExpMode: ($('rbExpMode') ? $('rbExpMode').value : 'carry'),\n")

# 7) UI dropdown under the carry controls
A7 = "set this to your exit time.</span>\n    </div>\n"
must(A7)
s = s.replace(A7, A7 +
"    <div style=\"margin-top:8px\">\n"
"      <label>Range Breakout \u2014 Tue/Thu (expiry day)</label>\n"
"      <select id=\"rbExpMode\" style=\"width:100%\">\n"
"        <option value=\"carry\">Carry squares at carry time (10:03); expiry-day entry at exit time</option>\n"
"        <option value=\"hold\">Hold to expiry \u2014 square everything at exit time (15:25)</option>\n"
"        <option value=\"sq14\">Square everything at 14:00 (no roll)</option>\n"
"        <option value=\"roll14\">14:00 square + roll live side to next expiry (Cross Expiry logic), exit next day 10:03</option>\n"
"      </select>\n"
"    </div>\n")

# remember the choice
A8 = "</script>\n</body>"
must(A8)
s = s.replace(A8, r"""
/*RBEXPPICK*/
(function(){
  const el = document.getElementById('rbExpMode'); if (!el) return;
  try { const v = localStorage.getItem('bt_rbExpMode'); if (v && [...el.options].some(o => o.value === v)) el.value = v; } catch(e){}
  el.addEventListener('change', () => { try { localStorage.setItem('bt_rbExpMode', el.value); } catch(e){} });
})();
""" + A8)

shutil.copyfile(P, P + ".bak13")
io.open(P, "w", encoding="utf-8").write(s)
print("Range Breakout Tue/Thu modes added (carry / hold 15:25 / 14:00 roll).")
