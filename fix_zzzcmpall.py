#!/usr/bin/env python3
# "Compare ALL": Cross Expiry + all Range Breakout Tue/Thu variants on the same dates, one screen:
# KPI table (best per row highlighted), all equity curves on one chart, day-by-day table.
# Also "Compare: Range Breakout Tue/Thu square 15:25 vs 14:00" and "Compare: Cross Expiry - all 3 scenarios".
# Runs on the server engine (kind compare_all, one data pass) when connected, else in the browser.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CMPALL*/" in s:
    print("Already fixed."); sys.exit(0)
O = '      <option value="compare" data-rb="carry">'
O2 = '      <option data-rb="carry" value="compare">'
A = "</script>\n</body>"
key = O if s.count(O) == 1 else O2
if s.count(key) != 1 or s.count(A) != 1 or "function cmpStats" not in s:
    print("ABORT: anchor not found."); sys.exit(1)
s = s.replace(key, '      <option value="compare_all">\u2696\ufe0f Compare ALL: Cross Expiry vs all Range Breakout Tue/Thu variants</option>\n'
                   '      <option value="compare_rb">\u2696\ufe0f Compare: Range Breakout \u2014 Tue/Thu square 15:25 vs 14:00</option>\n' + key)
JS = r"""
/*CMPALL*/
(function(){
  const MODES = [['carry','RB \u2014 Tue/Thu sq 15:25'],['sq14','RB \u2014 Tue/Thu sq 14:00'],['roll14','RB \u2014 Tue/Thu 14:00 roll']];
  const COLS = ['#1F3864','#e67e22','#16a085','#8e44ad','#c0392b'];
  const rbP = (base, m) => ({...base, strategy:'breakdown', reentryMode:'original', reentrySL:'samesl', maxReentries:50, carry:'nextday', rbExpMode:m});
  function renderAll(list, base){
    const cap = base.capital || 200000;
    const money = v => fmt(v)+' <span style="font-size:11px;opacity:.6">('+(v/cap*100).toFixed(1)+'%)</span>';
    const pct = v => v.toFixed(1)+'%', n = v => String(v);
    const row = (label, key, f, hb=true) => {
      const vals = list.map(x => x.st[key]); const best = hb ? Math.max(...vals) : Math.min(...vals);
      return '<tr><td>'+label+'</td>'+vals.map(v => '<td class="right"'+(v===best?' style="background:#eaf8ee;font-weight:700"':'')+'>'+f(v)+'</td>').join('')+'</tr>';
    };
    const ranked = list.slice().sort((a,b)=>b.st.net-a.st.net);
    const dates = [...new Set(list.flatMap(x => Object.keys(x.st.byD)))].sort();
    const rows = dates.map(d => { const v = list.map(x => x.st.byD[d]); const mx = Math.max(...v.filter(z=>z!=null));
      return '<tr><td>'+fmtD(d)+'</td><td>'+['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][(new Date(d).getDay()+6)%7]+'</td>'+
        v.map(z => z==null ? '<td class="right" style="color:#bbb">\u2014</td>' : '<td class="right '+(z>0?'green':z<0?'red':'')+'"'+(z===mx?' style="font-weight:700"':'')+'>'+fmt(z)+'</td>').join('')+'</tr>'; }).join('');
    const head = list.map(x => '<th class="right">'+x.name+'</th>').join('');
    $('main').innerHTML = `
      <div class="card pos" style="margin:6px 0 16px;text-align:left;padding:16px 18px">
        <div class="t">Ranking for ${fmtD(base.dateFrom)} \u2192 ${fmtD(base.dateTo)} (net P&L)</div>
        <div class="v">${ranked[0].name}</div>
        <div class="sub2">${ranked.map((x,i)=>(i+1)+'. '+x.name+' '+fmt(x.st.net)).join(' &nbsp;\u00b7&nbsp; ')}</div>
      </div>
      <div style="overflow-x:auto"><table style="max-width:1100px"><thead><tr><th>Metric</th>${head}</tr></thead><tbody>
        ${row('Net P&L','net',money)}${row('Max Drawdown','mdd',money)}${row('Win % (days)','winPct',pct)}
        ${row('Best day','best',fmt)}${row('Worst day','worst',fmt)}${row('Trading days','days',n)}
        ${row('Trades','trades',n,false)}${row('SL hits','sl',n,false)}${row('Costs','costs',fmt,false)}
      </tbody></table></div>
      <div class="chart-wrap" style="margin-top:16px"><canvas id="cmpChart"></canvas></div>
      <h3 style="margin-top:8px">Day by day</h3>
      <div style="max-height:460px;overflow:auto;border:1px solid #e5e7eb;border-radius:6px">
      <table><thead><tr><th>Date</th><th>Day</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
    const ds = list.map((x,i) => { let l=0; return {label:x.name, data:dates.map(d => (x.st.curve[d]!=null ? (l=x.st.curve[d]) : l)),
      borderColor:COLS[i%COLS.length], backgroundColor:'transparent', tension:0.1, pointRadius:1}; });
    if (window._cmpChart) window._cmpChart.destroy();
    window._cmpChart = new Chart($('cmpChart').getContext('2d'), { type:'line', data:{labels:dates.map(fmtD), datasets:ds},
      options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:{ title:{display:true, text:'Cumulative P&L (gross) \u2014 all strategies'} } } });
  }
  const CEM = [['sq14','CE 1) square all 14:00'],['roll1525','CE 2) next-expiry, sq 15:25'],['roll1003','CE 3) next-expiry, next day 10:03']];
  async function runCE3(base){
    if (window.__srvOK && window.__srvRun) {
      try {
        const res = await window.__srvRun('compare_ce', base);
        if (res && res.ce3) { renderAll(CEM.map(([m,nm]) => ({m, name:nm, st:cmpStats(res.ce3[m])})), base);
          $('status').textContent = 'Compare done on server \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo); return; }
        throw new Error('engine not updated yet');
      } catch (e) { console.error(e); $('status').textContent = 'Server: ' + e.message + ' \u2014 running in browser\u2026'; }
    }
    await ensureRangeLoaded(base.dateFrom, base.dateTo);
    if (!GROUPED) { $('status').textContent = 'No data loaded.'; return; }
    setTimeout(() => {
      try { renderAll(CEM.map(([m,nm]) => ({m, name:nm, st:cmpStats(runBacktestCrossExpiry({...base, strategy:'cross_expiry', ceMode:m}))})), base);
        $('status').textContent = 'Compare done \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo); }
      catch (e) { console.error(e); $('status').textContent = 'Error: ' + e.message; }
    }, 50);
  }
  async function runCompareAll(){
    const base = buildParams();
    if (!base.dateFrom || !base.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
    const kind = window.__cmpKind || $('strategy').value;   // set by the Scenario dropdown
    if (kind === 'compare_ce') return runCE3(base);
    const only = kind === 'compare_rb' ? ['carry','sq14'] : null;   // RB 15:25 vs RB 14:00 only
    const pick = list => only ? list.filter(x => only.includes(x.m)) : list;
    if (!base.dateFrom || !base.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
    if (window.__srvOK && window.__srvRun) {
      try {
        const res = await window.__srvRun('compare_all', base);
        if (res && res.rb && res.rb.carry) {
          renderAll(pick([{m:'ce', name:'Cross Expiry', st:cmpStats(res.ce)}].concat(MODES.map(([m,nm]) => ({m, name:nm, st:cmpStats(res.rb[m])})))), base);
          $('status').textContent = 'Compare done on server \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo); return;
        }
        throw new Error('engine not updated yet');
      } catch (e) { console.error(e); $('status').textContent = 'Server: ' + e.message + ' \u2014 running in browser\u2026'; }
    }
    await ensureRangeLoaded(base.dateFrom, base.dateTo);
    if (!GROUPED) { $('status').textContent = 'No data loaded.'; return; }
    $('status').textContent = 'Running all strategies\u2026';
    setTimeout(() => {
      try {
        const list = (only ? [] : [{m:'ce', name:'Cross Expiry', st:cmpStats(runBacktestCrossExpiry({...base, strategy:'cross_expiry'}))}])
          .concat(MODES.filter(([m]) => !only || only.includes(m)).map(([m,nm]) => ({m, name:nm, st:cmpStats(runBacktest(rbP(base, m)))})));
        renderAll(list, base);
        $('status').textContent = 'Compare done \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo);
      } catch (e) { console.error(e); $('status').textContent = 'Error: ' + e.message; }
    }, 50);
  }
  window.runCompareAll = runCompareAll;
  const sel = $('strategy');
  const isAll = () => ['compare_all','compare_rb','compare_ce'].includes(sel.value);
  const ui = () => { if (isAll()) { $('rangeFields').style.display='block'; $('timeFields').style.display='none'; $('slField').style.display='none'; $('slNote').style.display='none'; } };
  sel.addEventListener('change', ui); ui();
  $('runBtn').addEventListener('click', (e) => { if (isAll()) { e.stopImmediatePropagation(); runCompareAll(); } }, true);
})();
"""
s = s.replace(A, JS + A)
shutil.copyfile(P, P + ".bak16")
io.open(P, "w", encoding="utf-8").write(s)
print("Compare ALL added.")
