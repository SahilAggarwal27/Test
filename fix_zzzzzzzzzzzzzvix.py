#!/usr/bin/env python3
# VIX regime entry for Cross Expiry (v2) + "Compare entry: 10:05 vs 09:40 vs VIX switch".
#  Regime per day from India VIX (live 09:20 value where collected, else previous day's close = known pre-open):
#    VIX < Low (14)      -> fresh entries anchored 10:05 (window 09:20-10:05), as today
#    Low <= VIX < High   -> anchored at the Mid time (09:40), window 09:20-09:40
#    VIX >= High (16)    -> skip fresh entries / half size / full size at the Mid time (selectable)
#  Hysteresis: a regime boundary must be crossed by +-Band (0.5) to switch.
#  Applies to fresh daily entries and the 14:00 roll (strike + SL window). Carried positions keep the 10:05 rules.
#  params.vixMode: 'off' (default, unchanged behaviour) | 'fixed' (params.vixFixedTime) | 'switch'.
#  VIX data is loaded by the server engine (engine.js) into VIX_DAY; the compare runs on the server only.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*VIXREGIME*/" in s:
    print("Already fixed."); sys.exit(0)

def rep(a, b):
    global s
    if s.count(a) != 1:
        print("ABORT: anchor count %d != 1: %s" % (s.count(a), a[:90])); sys.exit(1)
    s = s.replace(a, b)

# ---------- 1) engine: per-day entry anchor from the VIX regime ----------
rep("  const MORN='10:05', mornM=parseTime(MORN), W0=parseTime('09:20'), ROLL=parseTime(params.rollTime||'14:00');\n",
    "  const MORN='10:05', mornM=parseTime(MORN), W0=parseTime('09:20'), ROLL=parseTime(params.rollTime||'14:00');\n"
    "  let DM=MORN, dmM=mornM, DMULT=1, _rgPrev=null; const regimeLog={};   /*VIXREGIME*/\n")
rep("  const lvl=(date,inst,k,exp,side)=>{ let lo=null,hi=null; for(const r of ceLeg(date,inst,k,exp,side)){ const m=parseTime(r.time);\n"
    "      if(m>=W0&&m<=mornM){",
    "  const lvl=(date,inst,k,exp,side,eM)=>{ let lo=null,hi=null; for(const r of ceLeg(date,inst,k,exp,side)){ const m=parseTime(r.time);\n"
    "      if(m>=W0&&m<=(eM||mornM)){")
rep("const lot=lotFor(p.inst,date)*params.lots, pnl=",
    "const lot=lotFor(p.inst,date)*params.lots*(p.mult==null?1:p.mult), pnl=")
rep("reason:(p.kind==='D'?'':'R-')+why, pnl});",
    "reason:(p.kind==='D'?'':'R-')+why, pnl, mult:(p.mult==null?1:p.mult), pts:(p.ep-px)*(p.mult==null?1:p.mult)});")
rep("  for(const date of dates){\n    const exp={};",
    "  for(const date of dates){\n"
    "    { const _rg=ceRegimeNext(date,params,_rgPrev); _rgPrev=_rg.r; DM=_rg.t; dmM=parseTime(DM); DMULT=_rg.mult;\n"
    "      regimeLog[date]={v:_rg.v, r:_rg.r, t:DM, mult:DMULT}; }\n"
    "    const exp={};")
rep("        if(freeAt[side]===Infinity) continue;\n"
    "        const k=ceStrike(date,act,MORN,side); if(k===null) continue;\n"
    "        const lv=lvl(date,act,k,ex,side); if(!lv) continue;\n"
    "        const start=Math.max(mornM, freeAt[side]||0);",
    "        if(freeAt[side]===Infinity || DMULT===0) continue;\n"
    "        const k=ceStrike(date,act,DM,side); if(k===null) continue;\n"
    "        const lv=lvl(date,act,k,ex,side,dmM); if(!lv) continue;\n"
    "        const start=Math.max(dmM, freeAt[side]||0);")
rep("pos={kind:'D', inst:act, exp:ex, side, strike:k, et:r.time, ep:lv.lo, sl:lv.hi, entryDate:date, _chk:date};",
    "pos={kind:'D', inst:act, exp:ex, side, strike:k, et:r.time, ep:lv.lo, sl:lv.hi, entryDate:date, _chk:date, mult:DMULT};")
rep("if(actExpiring && mode!=='sq14' && openAt14.size){",
    "if(actExpiring && mode!=='sq14' && openAt14.size && DMULT>0){")
rep("const k=ceStrike(date,nxt,MORN,side); if(k===null){ carrySkips++; continue; }",
    "const k=ceStrike(date,nxt,DM,side); if(k===null){ carrySkips++; continue; }")
rep("const lv=lvl(date,nxt,k,nexp,side);\n",
    "const lv=lvl(date,nxt,k,nexp,side,dmM);\n")
rep("const pos={kind:'R', inst:nxt, exp:nexp, side, strike:k, et:eb.time, ep:eb.p, sl:(lv?lv.hi:eb.h), entryDate:date, _chk:date};",
    "const pos={kind:'R', inst:nxt, exp:nexp, side, strike:k, et:eb.time, ep:eb.p, sl:(lv?lv.hi:eb.h), entryDate:date, _chk:date, mult:DMULT};")
rep("  return {trades, dailyPnl, costs, carrySkips};\n}\nfunction runBacktestCrossExpiry(params){ return ceV2(params); }",
    "  return {trades, dailyPnl, costs, carrySkips, regimeLog};\n}\nfunction runBacktestCrossExpiry(params){ return ceV2(params); }")

REGIME = r"""
/*VIXREGIME-CORE*/
var VIX_DAY = {};
function vixOf(date){ const v = VIX_DAY ? VIX_DAY[date] : null; return (v == null || isNaN(v)) ? null : +v; }
// Regime for `date`: r 0 = low VIX, 1 = mid, 2 = high (-1 = not switching). prev = yesterday's r (hysteresis).
function ceRegimeNext(date, params, prev){
  const mode = params.vixMode || 'off', v = vixOf(date);
  const tLow = params.vixTimeLow || '10:05', tMid = params.vixTimeMid || '09:40';
  if (mode === 'fixed') return { r:-1, t: params.vixFixedTime || '10:05', mult:1, v };
  if (mode !== 'switch') return { r:-1, t:'10:05', mult:1, v };
  const lo = +(params.vixLo != null ? params.vixLo : 14), hi = +(params.vixHi != null ? params.vixHi : 16);
  const b = +(params.vixBand != null ? params.vixBand : 0.5), th = [lo, hi];
  let r;
  if (v === null) r = (prev != null && prev >= 0) ? prev : 0;               // no VIX that day -> keep regime
  else {
    const plain = v < lo ? 0 : (v < hi ? 1 : 2);
    if (prev == null || prev < 0 || !(b > 0)) r = plain;
    else { r = prev; while (r < 2 && v >= th[r] + b) r++; while (r > 0 && v <= th[r - 1] - b) r--; }
  }
  if (r === 0) return { r, t: tLow, mult:1, v };
  if (r === 1) return { r, t: tMid, mult:1, v };
  const a = params.vixHighAction || 'skip';
  return { r, t: tMid, mult: a === 'skip' ? 0 : (a === 'half' ? 0.5 : 1), v };
}
"""
rep("/*CEV2*/\n", "/*CEV2*/\n" + REGIME)

# ---------- 2) UI: regime controls (Cross Expiry only) ----------
PANEL = '''    <div id="vixWrap" style="display:none;border:1px solid #e5e7eb;border-radius:6px;padding:8px 10px;margin:6px 0 10px">
      <label style="font-weight:600"><input type="checkbox" id="vixOn"> VIX regime entry time</label>
      <div style="display:flex;gap:8px;flex-wrap:wrap;font-size:12px;align-items:center;margin-top:4px">
        <span>Low &lt; <input type="text" id="vixLo" value="14" style="width:44px"></span>
        <span>High &ge; <input type="text" id="vixHi" value="16" style="width:44px"></span>
        <span>Band &plusmn; <input type="text" id="vixBand" value="0.5" style="width:40px"></span>
        <span>Low-VIX entry <input type="text" id="vixTLow" value="10:05" style="width:52px"></span>
        <span>Mid-VIX entry <input type="text" id="vixTMid" value="09:40" style="width:52px"></span>
        <span>High VIX <select id="vixHiAct"><option value="skip">skip fresh entries</option><option value="half">half size</option><option value="full">full size at mid time</option></select></span>
      </div>
      <div style="font-size:11px;color:#6c7a89;margin-top:4px">VIX = collected 09:20 value where available, else previous day&rsquo;s close (known before the open). Changes fresh entries and the 2 PM roll; carried positions keep their 10:05 rules. Needs the server engine.</div>
    </div>

'''
rep('    <div id="scenWrap" style="display:none">\n', PANEL + '    <div id="scenWrap" style="display:none">\n')

JS = r"""
/*VIXREGIME*/
(function(){
  const num = (id, d) => { const v = parseFloat(($(id) || {}).value); return isNaN(v) ? d : v; };
  const tm = (id, d) => { const v = String(($(id) || {}).value || '').trim(); return /^\d{1,2}:\d{2}$/.test(v) ? v.padStart(5, '0') : d; };
  const vixParams = () => ({ vixMode: ($('vixOn') && $('vixOn').checked) ? 'switch' : 'off',
    vixLo: num('vixLo', 14), vixHi: num('vixHi', 16), vixBand: num('vixBand', 0.5),
    vixTimeLow: tm('vixTLow', '10:05'), vixTimeMid: tm('vixTMid', '09:40'), vixHighAction: ($('vixHiAct') || {}).value || 'skip' });
  const _bp = buildParams;
  buildParams = function(){ const p = _bp.apply(this, arguments); return Object.assign(p, vixParams()); };
  try { ['vixOn','vixLo','vixHi','vixBand','vixTLow','vixTMid','vixHiAct'].forEach(id => {
      const el = $(id), k = 'bt_' + id, v = localStorage.getItem(k);
      if (v != null) { if (el.type === 'checkbox') el.checked = v === '1'; else el.value = v; }
      el.addEventListener('change', () => localStorage.setItem(k, el.type === 'checkbox' ? (el.checked ? '1' : '0') : el.value)); });
  } catch(e){}

  const st = $('strategy'), sc = $('scenario');
  const OPT = 'ce:vixcmp';
  const sync = () => {
    $('vixWrap').style.display = st.value === 'cross_expiry' ? 'block' : 'none';
    if (st.value === 'cross_expiry' && sc && ![...sc.options].some(o => o.value === OPT)) {
      const o = document.createElement('option'); o.value = OPT;
      o.textContent = '\u2696\ufe0f Compare entry time: 10:05 vs 09:40 vs VIX switch (+ robustness, hold-out)';
      sc.appendChild(o);
    }
    if (sc && sc.value === OPT) window.__cmpKind = 'compare_vix';
  };
  st.addEventListener('change', () => setTimeout(sync, 0));
  if (sc) sc.addEventListener('change', () => { if (sc.value === OPT) { window.__cmpKind = 'compare_vix'; opt0(); } });
  const opt0 = () => { const o = [...st.options].find(x => x.value === 'cross_expiry'); if (o) o.dataset.ce = 'live'; };
  sync();

  const _rca = window.runCompareAll;
  window.runCompareAll = function(){ if (window.__cmpKind === 'compare_vix') return runVixCompare(); return _rca.apply(this, arguments); };

  const VARS = [['base','A) Fixed 10:05 (current)'], ['fixed0940','B) Fixed mid time'], ['switch','C) VIX switch'],
                ['lo_m1','C, Low \u22121'], ['lo_p1','C, Low +1'], ['t_m5','C, mid time \u22125m'], ['t_p10','C, mid time +10m']];
  async function runVixCompare(){
    const base = buildParams();
    base.strategy = 'cross_expiry'; base.ceMode = 'live'; base.vixMode = 'switch';
    if (!base.dateFrom || !base.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
    if (!window.__srvOK || !window.__srvRun) { $('status').textContent = 'VIX compare runs on the server engine (port 8090) \u2014 it is not reachable right now.'; return; }
    try {
      const res = await window.__srvRun('compare_vix', base);
      if (!res || !res.vx) throw new Error('engine not updated yet (wait 2 min for auto-deploy)');
      renderVix(res, base);
      $('status').textContent = 'VIX compare done on server \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo);
    } catch (e) { console.error(e); $('status').textContent = 'Server: ' + e.message; }
  }

  function renderVix(res, base){
    const vix = res.vix || {}, lo = +base.vixLo, hi = +base.vixHi, SPLIT = res.split || '2025-01-01';
    const cost = t => { const lq = SPECS[t.instrument] ? SPECS[t.instrument].lot : 0;
      return (base.brokerage * base.lots + base.slippage * lq * base.lots) * (t.mult == null ? 1 : t.mult); };
    const bucket = d => { const v = vix[d]; return v == null ? 'n/a' : v < lo ? '<' + lo : v < hi ? lo + '\u2013' + hi : '\u2265' + hi; };
    const BK = ['<' + lo, lo + '\u2013' + hi, '\u2265' + hi, 'n/a'];
    const S = {};
    for (const [k] of VARS) {
      const r = res.vx[k]; if (!r) continue;
      const tr = r.trades || [];
      const sum = (f, xs) => xs.reduce((a, t) => a + f(t), 0);
      const net = xs => sum(t => t.pnl - cost(t), xs), pts = xs => sum(t => (t.pts != null ? t.pts : 0), xs);
      const byD = {}; for (const x of (r.dailyPnl || [])) byD[x.date] = (byD[x.date] || 0) + x.pnl;
      let cum = 0, pk = 0, mdd = 0; const ds = Object.keys(byD).sort();
      for (const d of ds) { cum += byD[d]; pk = Math.max(pk, cum); mdd = Math.min(mdd, cum - pk); }
      const worst = ds.length ? Math.min(...ds.map(d => byD[d])) : 0;
      const bk = {}; for (const b of BK) { const xs = tr.filter(t => bucket(t.date) === b); bk[b] = { pts: pts(xs), net: net(xs), n: xs.length }; }
      const pre = tr.filter(t => t.date < SPLIT), post = tr.filter(t => t.date >= SPLIT);
      const reg = r.regime || {}; const rc = [0, 0, 0, 0];
      for (const d in reg) { const x = reg[d]; if (x.r >= 0 && x.r <= 2) rc[x.r]++; if (x.v == null) rc[3]++; }
      S[k] = { net: net(tr), pts: pts(tr), n: tr.length, sl: tr.filter(t => String(t.reason).endsWith('SL')).length,
               win: tr.length ? tr.filter(t => t.pnl > 0).length / tr.length * 100 : 0, mdd, worst, bk,
               pre: { pts: pts(pre), n: pre.length }, post: { pts: pts(post), n: post.length }, rc };
    }
    const have = VARS.filter(([k]) => S[k]);
    const P = v => (v >= 0 ? '+' : '') + Math.round(v).toLocaleString('en-IN');
    const cell = (v, best, f) => '<td class="right ' + (v > 0 ? 'green' : v < 0 ? 'red' : '') + '"' + (v === best ? ' style="background:#eaf8ee;font-weight:700"' : '') + '>' + f(v) + '</td>';
    const row = (label, f, get, hb = true) => { const vals = have.map(([k]) => get(S[k])); const best = hb ? Math.max(...vals) : Math.min(...vals);
      return '<tr><td>' + label + '</td>' + vals.map(v => cell(v, best, f)).join('') + '</tr>'; };
    const head = have.map(([, n]) => '<th class="right">' + n + '</th>').join('');
    const A = S.base, B = S.fixed0940, C = S['switch'];
    const chk = (ok, txt) => '<li style="margin:3px 0">' + (ok ? '\u2705' : '\u274c') + ' ' + txt + '</li>';
    const rob = ['lo_m1','lo_p1','t_m5','t_p10'].filter(k => S[k]);
    const checks = (A && B && C) ? [
      chk(C.pts > A.pts && C.pts > B.pts, 'Switch beats both fixed 10:05 and fixed mid time on total points (' + P(C.pts) + ' vs ' + P(A.pts) + ' / ' + P(B.pts) + ')'),
      chk(C.mdd >= A.mdd, 'Switch drawdown no worse than current 10:05 (' + fmt(C.mdd) + ' vs ' + fmt(A.mdd) + ')'),
      chk(rob.length && rob.every(k => S[k].pts > A.pts), 'Neighbouring thresholds / times also beat 10:05 (not a lucky exact setting)'),
      chk(C.post.n > 0 && C.post.pts > A.post.pts, 'Hold-out ' + SPLIT.slice(0,4) + '+ : switch beats 10:05 (' + P(C.post.pts) + ' vs ' + P(A.post.pts) + ' pts)'),
      chk(C.bk[BK[1]].n >= 50 && C.bk[BK[2]].n + A.bk[BK[2]].n >= 30, 'Enough trades in the mid/high VIX buckets to trust it (' + C.bk[BK[1]].n + ' mid, ' + A.bk[BK[2]].n + ' high)')
    ] : [];
    const pass = checks.length && checks.every(c => c.indexOf('\u2705') >= 0);
    const bkRows = BK.map(b => '<tr><td>VIX ' + b.replace('<', '&lt;') + '</td>' + have.map(([k]) => { const x = S[k].bk[b];
      return '<td class="right ' + (x.pts > 0 ? 'green' : x.pts < 0 ? 'red' : '') + '">' + P(x.pts) + ' <span style="opacity:.55;font-size:11px">(' + x.n + ')</span></td>'; }).join('') + '</tr>').join('');
    const rc = C ? C.rc : [0,0,0,0];
    $('main').innerHTML = `
      <div class="card ${pass ? 'pos' : 'neg'}" style="margin:6px 0 14px;text-align:left;padding:14px 18px">
        <div class="t">Verdict \u2014 VIX switch (${fmtD(base.dateFrom)} \u2192 ${fmtD(base.dateTo)}, scenario: as traded live)</div>
        <div class="v">${pass ? 'PASSES \u2014 worth adopting' : 'DOES NOT PASS \u2014 keep 10:05 for now'}</div>
        <ul style="margin:8px 0 0 0;padding-left:4px;list-style:none;font-size:13px">${checks.join('')}</ul>
        <div class="sub2" style="margin-top:6px">Days by regime (switch): low ${rc[0]} \u00b7 mid ${rc[1]} \u00b7 high ${rc[2]} \u00b7 no VIX ${rc[3]} \u00b7 VIX source: ${res.vixSrc || '-'}</div>
      </div>
      <div style="overflow-x:auto"><table style="max-width:1200px"><thead><tr><th>Metric</th>${head}</tr></thead><tbody>
        ${row('Points (premium, size-weighted)', P, x => x.pts)}
        ${row('Net P&L after costs', fmt, x => x.net)}
        ${row('Max drawdown (MTM)', fmt, x => x.mdd)}
        ${row('Worst day (MTM)', fmt, x => x.worst)}
        ${row('Win % (trades)', v => v.toFixed(1) + '%', x => x.win)}
        ${row('Trades', v => String(v), x => x.n, false)}
        ${row('SL hits', v => String(v), x => x.sl, false)}
        ${row('Points before ' + SPLIT.slice(0,4), P, x => x.pre.pts)}
        ${row('Points ' + SPLIT.slice(0,4) + '+ (hold-out)', P, x => x.post.pts)}
      </tbody></table></div>
      <h3 style="margin-top:14px">Points by VIX on the entry day <span style="font-weight:400;font-size:12px">(trade count)</span></h3>
      <div style="overflow-x:auto"><table style="max-width:1200px"><thead><tr><th>Bucket</th>${head}</tr></thead><tbody>${bkRows}</tbody></table></div>
      <div style="font-size:12px;color:#6c7a89;margin-top:8px">A/B ignore VIX (always full size). C uses Low ${lo} / High ${hi} / Band \u00b1${base.vixBand}, entry ${base.vixTimeLow} / ${base.vixTimeMid}, high VIX = ${base.vixHighAction}. Points = (sell \u2212 buy) \u00d7 size, comparable across lot-size changes.</div>`;
  }
})();
"""
rep("</script>\n</body>", JS + "</script>\n</body>")

shutil.copyfile(P, P + ".bakvix")
io.open(P, "w", encoding="utf-8").write(s)
print("VIX regime entry + compare added.")
