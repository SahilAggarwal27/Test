#!/usr/bin/env python3
# Compare button: runs Cross Expiry and Range Breakout (sell below 09:20-10:03 low,
# SL = high) on the SAME dates and shows them side by side: KPIs (winner highlighted),
# both equity curves, and a day-by-day table with which strategy did better.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*COMPARE*/" in s:
    print("Already fixed."); sys.exit(0)
H = '<button id="runBtn" disabled>\U0001F680 Run Backtest</button>'
H2 = H + '\n    <button id="cmpBtn" style="background:#0b7a75;margin-top:8px">\u2696\ufe0f Compare: Cross Expiry vs Range Breakout</button>'
A = "</script>\n</body>"
for a in (H, A):
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:40]); sys.exit(1)
JS = r"""
/*COMPARE*/
function cmpByDate(r){ const m={}; for(const x of r.dailyPnl){ m[x.date]=(m[x.date]||0)+x.pnl; } return m; }
function cmpStats(r){
  const byD=cmpByDate(r), dates=Object.keys(byD).sort(); let cum=0, pk=0, mdd=0; const curve={};
  for(const d of dates){ cum+=byD[d]; if(cum>pk) pk=cum; mdd=Math.min(mdd, cum-pk); curve[d]=cum; }
  const v=dates.map(d=>byD[d]), wins=v.filter(x=>x>0).length, gross=v.reduce((a,b)=>a+b,0);
  return { net:gross-r.costs, costs:r.costs, days:dates.length, winPct:dates.length?wins/dates.length*100:0, mdd,
    trades:r.trades.length, sl:r.trades.filter(t=>String(t.reason).endsWith('SL')).length,
    best:v.length?Math.max(...v):0, worst:v.length?Math.min(...v):0, byD, curve };
}
async function runCompare(){
  const base = buildParams();
  if (!base.dateFrom || !base.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
  $('status').textContent = 'Loading…';
  await ensureRangeLoaded(base.dateFrom, base.dateTo);
  if (!GROUPED) { $('status').textContent = 'No data loaded.'; return; }
  $('status').textContent = 'Running both strategies…';
  setTimeout(() => {
    try {
      const ce = runBacktestCrossExpiry({...base, strategy:'cross_expiry'});
      const rb = runBacktest({...base, strategy:'breakdown', reentryMode:'original', reentrySL:'samesl', maxReentries:50, carry:'nextday'});
      renderCompare(cmpStats(ce), cmpStats(rb), base);
      $('status').textContent = 'Compare done · ' + fmtD(base.dateFrom) + ' → ' + fmtD(base.dateTo);
    } catch (e) { console.error(e); $('status').textContent = 'Error: ' + e.message; }
  }, 50);
}
function renderCompare(A, B, base){
  const NA='Cross Expiry', NB='Range Breakout (Low / SL High)';
  const cap = base.capital || 200000;
  const win = A.net>=B.net ? NA : NB, diff = Math.abs(A.net-B.net);
  const row = (label, a, b, fmtF, higherBetter=true) => {
    const aw = higherBetter ? a>b : a<b, bw = higherBetter ? b>a : b<a;
    const st = w => w ? ' style="background:#eaf8ee;font-weight:700"' : '';
    return `<tr><td>${label}</td><td class="right"${st(aw)}>${fmtF(a)}</td><td class="right"${st(bw)}>${fmtF(b)}</td></tr>`;
  };
  const pct = v => v.toFixed(1)+'%', n = v => String(v), money = v => fmt(v)+' <span style="font-size:11px;opacity:.6">('+(v/cap*100).toFixed(1)+'%)</span>';
  const dates = [...new Set([...Object.keys(A.byD), ...Object.keys(B.byD)])].sort();
  let ca=0, cb=0, aBetter=0, bBetter=0;
  const rows = dates.map(d => { const a=A.byD[d], b=B.byD[d];
    if (a!=null && b!=null) { if (a>b) aBetter++; else if (b>a) bBetter++; }
    const w = (a==null||b==null) ? '' : (a>b ? NA : (b>a ? 'Range Breakout' : '='));
    const c = v => v==null ? '<td class="right" style="color:#bbb">—</td>' : `<td class="right ${v>0?'green':v<0?'red':''}">${fmt(v)}</td>`;
    return `<tr><td>${fmtD(d)}</td><td>${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][(new Date(d).getDay()+6)%7]}</td>${c(a)}${c(b)}<td>${w}</td></tr>`; }).join('');
  $('main').innerHTML = `
    <div class="card ${win===NA?'pos':'est'}" style="margin:6px 0 16px;text-align:left;padding:16px 18px">
      <div class="t">Winner for ${fmtD(base.dateFrom)} → ${fmtD(base.dateTo)}</div>
      <div class="v">${win} by ${fmt(diff)}</div>
      <div class="sub2">Better on more days: ${aBetter>=bBetter?NA:'Range Breakout'} (${Math.max(aBetter,bBetter)} vs ${Math.min(aBetter,bBetter)} days)</div>
    </div>
    <table style="max-width:760px"><thead><tr><th>Metric</th><th class="right">${NA}</th><th class="right">${NB}</th></tr></thead><tbody>
      ${row('Net P&L', A.net, B.net, money)}
      ${row('Max Drawdown', A.mdd, B.mdd, money)}
      ${row('Win % (days)', A.winPct, B.winPct, pct)}
      ${row('Best day', A.best, B.best, fmt)}
      ${row('Worst day', A.worst, B.worst, fmt)}
      ${row('Trading days', A.days, B.days, n)}
      ${row('Trades', A.trades, B.trades, n, false)}
      ${row('SL hits', A.sl, B.sl, n, false)}
      ${row('Costs', A.costs, B.costs, fmt, false)}
    </tbody></table>
    <div class="chart-wrap" style="margin-top:16px"><canvas id="cmpChart"></canvas></div>
    <h3 style="margin-top:8px">Day by day</h3>
    <div style="max-height:460px;overflow:auto;border:1px solid #e5e7eb;border-radius:6px">
    <table><thead><tr><th>Date</th><th>Day</th><th class="right">${NA}</th><th class="right">Range Breakout</th><th>Better</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  const ya = [], yb = []; let la=0, lb=0;
  for (const d of dates) { if (A.curve[d]!=null) la=A.curve[d]; if (B.curve[d]!=null) lb=B.curve[d]; ya.push(la); yb.push(lb); }
  if (window._cmpChart) window._cmpChart.destroy();
  window._cmpChart = new Chart($('cmpChart').getContext('2d'), { type:'line',
    data:{ labels:dates.map(fmtD), datasets:[
      {label:NA, data:ya, borderColor:'#1F3864', backgroundColor:'rgba(31,56,100,0.08)', tension:0.1, pointRadius:2},
      {label:NB, data:yb, borderColor:'#e67e22', backgroundColor:'rgba(230,126,34,0.08)', tension:0.1, pointRadius:2} ]},
    options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:{ title:{display:true, text:'Cumulative P&L (gross) — both strategies'} } } });
}
$('cmpBtn').addEventListener('click', runCompare);
"""
s = s.replace(H, H2).replace(A, JS + A)
shutil.copyfile(P, P + ".bak10")
io.open(P, "w", encoding="utf-8").write(s)
print("Compare button added.")
