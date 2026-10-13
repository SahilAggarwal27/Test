#!/usr/bin/env python3
# Range Breakout: Tue/Thu (expiry-day) handling, picked from a dropdown (rbExpMode):
#  carry   = current: carried position squares next day at the carry time (10:03); expiry-day entry squares at exit time
#  hold    = carried position is held through the expiry day and squared at the exit time (15:25)
#  sq14    = everything on the expiring contract squares at 14:00 on the expiry day, no roll
#  roll14  = on the expiry day everything on the expiring contract squares at 14:00; at 14:00 a fresh position is
#            opened on the NEXT expiry (other index), ATM at 10:03, using that contract's 09:20-10:03 Low (sell
#            trigger) / High (SL); it is squared the same day at the exit time (15:25)
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
ROLL = r"""    /*RBROLL*/
    if (params.strategy === 'breakdown' && params.rbExpMode === 'roll14' && typeof ceCalendarExp === 'function' && ceCalendarExp(date, inst) === date) {
      const rollM = parseTime(params.rbRollTime || '14:00');
      let nx = null, nexp = null;
      for (const ix of ['NIFTY', 'SENSEX']) {
        if (ix === inst || !GROUPED[date][ix]) continue;
        const e = ceNearestExp(date, ix);
        if (e && e > date && (nexp === null || e < nexp)) { nexp = e; nx = ix; }
      }
      const nspec = nx ? SPECS[nx] : null;
      const natm = nspec ? ceAtm(date, nx, params.refEnd) : null;          // ATM at 10:03 (as traded live)
      if (natm !== null) {
        const G = GROUPED[date][nx];
        const cS = natm + (params.ceOffset || 0) * nspec.step, pS = natm + (params.peOffset || 0) * nspec.step;
        const okN = r => (!r.exp || r.exp === nexp || Math.abs((new Date(r.exp) - new Date(nexp)) / 86400000) <= 1);
        if (G[cS] && G[pS]) {
          const peT = {}; for (const r of G[pS]) if (okN(r)) peT[r.time] = r;
          const ns = G[cS].filter(r => okN(r) && peT[r.time])
            .map(r => ({ time: r.time, ce: r.ce, pe: peT[r.time].pe, ce_h: r.ce_h, ce_l: r.ce_l, pe_h: peT[r.time].pe_h, pe_l: peT[r.time].pe_l, spot: r.spot }))
            .sort((a, b) => parseTime(a.time) - parseTime(b.time));
          const rs = parseTime(params.refStart), re = parseTime(params.refEnd);
          const ref = ns.filter(r => { const m = parseTime(r.time); return m >= rs && m <= re; });
          const win = ns.filter(r => { const m = parseTime(r.time); return m >= rollM && m <= exitMin; });
          if (ref.length && win.length >= 2) {
            const nLot = lotFor(nx, date) * params.lots, rt = [];
            const cL = Math.min(...ref.map(r => r.ce)), cH = Math.max(...ref.map(r => r.ce));
            const pL = Math.min(...ref.map(r => r.pe)), pH = Math.max(...ref.map(r => r.pe));
            runLegBreakdown(win, cL, cH, 'ce', nLot, reOpts).forEach(t => rt.push({ ...t, date, exitDate: date, instrument: nx, leg: 'CE', strike: natm, roll: true }));
            runLegBreakdown(win, pL, pH, 'pe', nLot, reOpts).forEach(t => rt.push({ ...t, date, exitDate: date, instrument: nx, leg: 'PE', strike: natm, roll: true }));
            if (rt.length) {
              trades.push(...rt);
              dailyPnl.push({ date, dow: ['Mon','Tue','Wed','Thu','Fri'][dayIdx], instrument: nx, atm: natm,
                pnl: rt.reduce((a, t) => a + t.pnl, 0), nTrades: rt.length, slHits: rt.filter(t => t.reason === 'SL').length });
            }
          }
        }
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
"        <option value=\"roll14\">14:00 square + roll to next expiry (10:03 Low/High), square at exit time (15:25)</option>\n"
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
print("Range Breakout Tue/Thu modes added (carry / hold 15:25 / 14:00 / 14:00 roll).")
