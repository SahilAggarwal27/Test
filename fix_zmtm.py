#!/usr/bin/env python3
# Cross Expiry Daily P&L = ONE row per trading day (every day in the range, incl. days
# with no exits), merged across all legs, marked-to-market at each day's close for
# positions carried overnight. Sum of days = total realized P&L of closed trades.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*MTMDAILY*/" in s:
    print("Already fixed."); sys.exit(0)
A = "</script>\n</body>"
if s.count(A) != 1:
    print("ABORT: anchor not found."); sys.exit(1)
JS = r"""
/*MTMDAILY*/
function ceMtmDaily(r, params, byInst){
  const dowArr=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const days=Object.keys(GROUPED).sort().filter(d=>(!params.dateFrom||d>=params.dateFrom)&&(!params.dateTo||d<=params.dateTo));
  const agg={}; const mk0=()=>({pnl:0,n:0,sl:0,inst:new Set(),atm:new Set()});
  if(!byInst) days.forEach(d=>agg[d]=mk0());
  const touch=(d,t)=>{ const k=byInst?d+'|'+t.instrument:d; if(!agg[k]) agg[k]=mk0(); agg[k].inst.add(t.instrument); agg[k].atm.add(t.strike); return agg[k]; };
  for(const t of r.trades){
    const ed=t.exitDate||t.date, lot=lotFor(t.instrument, ed)*params.lots, exp=ceNearestExp(t.date, t.instrument);
    let prev=t.ep;
    for(const d of days){ if(d<t.date || d>=ed) continue;
      const L=ceLeg(d,t.instrument,t.strike,exp,t.leg); if(!L.length) continue;
      const mk=L[L.length-1].p; touch(d,t).pnl+=(prev-mk)*lot; prev=mk; }
    const a=touch(ed,t); a.pnl+=(prev-t.xp)*lot; a.n++; if(String(t.reason).endsWith('SL')) a.sl++;
  }
  return Object.keys(agg).sort().map(k=>{ const d=k.slice(0,10); return {date:d, dow:dowArr[(new Date(d).getDay()+6)%7],
    instrument:[...agg[k].inst].join('+')||'-', atm:[...agg[k].atm].join(' / ')||'-',
    pnl:agg[k].pnl, nTrades:agg[k].n, slHits:agg[k].sl}; });
}
(function(){
  const _ce = runBacktestCrossExpiry;
  runBacktestCrossExpiry = function(params){
    const r = _ce(params);
    try { r.dailyPnlByInst = ceMtmDaily(r, params, true); r.dailyPnl = ceMtmDaily(r, params, false); } catch(e){ console.error('mtm daily', e); }
    return r;
  };
  const _sum = window.__addInstrumentSummary;   // per-instrument cards/table keep one column per index
  if (_sum) window.__addInstrumentSummary = function(res){ return _sum(res && res.dailyPnlByInst ? Object.assign({}, res, {dailyPnl: res.dailyPnlByInst}) : res); };
})();
"""
shutil.copyfile(P, P + ".bak9")
io.open(P, "w", encoding="utf-8").write(s.replace(A, JS + A))
print("Daily P&L merged per day (MTM).")
