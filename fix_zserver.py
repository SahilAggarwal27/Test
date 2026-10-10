#!/usr/bin/env python3
# Server engine hookup: when the droplet's engine (port 8090) is reachable, Run and Compare
# send the job there and only the results come back (any range, no data in the browser).
# Shows "Server engine connected" under the buttons; falls back to the browser if unreachable.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*SERVERENGINE*/" in s:
    print("Already fixed."); sys.exit(0)
A = "</script>\n</body>"
if s.count(A) != 1 or "function runCompare" not in s:
    print("ABORT: anchor not found."); sys.exit(1)
JS = r"""
/*SERVERENGINE*/
(function(){
  const ENG = 'http://' + location.hostname + ':8090';
  window.__srvOK = false;
  const probe = () => {
    const c = new AbortController(); const t = setTimeout(() => c.abort(), 2500);
    fetch(ENG + '/health', { signal: c.signal, cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(j => { const was = window.__srvOK; window.__srvOK = !!(j && j.ok);
                   if (window.__srvOK && !was && $('status') && !$('status').textContent) $('status').textContent = '\u2699\ufe0f Server engine connected \u2014 any date range runs on the server.'; })
      .catch(() => { window.__srvOK = false; })
      .finally(() => clearTimeout(t));
  };
  probe(); setInterval(probe, 60000);
  async function srvRun(kind, params){
    const r = await fetch(ENG + '/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, params }) });
    if (!r.ok) throw new Error('engine HTTP ' + r.status);
    const { id } = await r.json();
    for (;;) {
      await new Promise(res => setTimeout(res, 1500));
      const j = await (await fetch(ENG + '/job/' + id, { cache: 'no-store' })).json();
      if (j.status === 'done') { setBar(null); return j.result; }
      if (j.status === 'error') { setBar(null); throw new Error(j.error || 'engine error'); }
      $('status').textContent = '\u2699\ufe0f Server: ' + (j.progress || j.status);
      if (j.pct != null) setBar(Math.max(2, j.pct));
    }
  }
  window.__srvRun = srvRun;
  const _cmp = runCompare;
  runCompare = async function(){
    if (!window.__srvOK) return _cmp();
    const base = buildParams();
    if (!base.dateFrom || !base.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
    try {
      const res = await srvRun('compare', base);
      renderCompare(cmpStats(res.ce), cmpStats(res.rb), base);
      $('status').textContent = 'Compare done on server \u00b7 ' + fmtD(base.dateFrom) + ' \u2192 ' + fmtD(base.dateTo);
    } catch (e) { console.error(e); $('status').textContent = 'Server engine failed (' + e.message + ') \u2014 running in browser\u2026'; return _cmp(); }
  };
  $('runBtn').addEventListener('click', async (e) => {
    if (window.__srvBypass) { window.__srvBypass = false; return; }
    const st = $('strategy').value;
    if (!window.__srvOK || !['cross_expiry', 'breakdown', 'time_based'].includes(st)) return;
    e.stopImmediatePropagation();
    const params = buildParams();
    if (!params.dateFrom || !params.dateTo) { $('status').textContent = 'Pick From and To dates first.'; return; }
    try {
      const res = await srvRun(st, params);
      render(res, params);
      $('status').textContent = `Done on server \u00b7 ${res.dailyPnl.length} days \u00b7 ${res.trades.length} trades`;
    } catch (err) {
      console.error(err); $('status').textContent = 'Server engine failed (' + err.message + ') \u2014 running in browser\u2026';
      window.__srvBypass = true; $('runBtn').click();
    }
  }, true);
})();
"""
s = s.replace(A, JS + A)
shutil.copyfile(P, P + ".bak15")
io.open(P, "w", encoding="utf-8").write(s)
print("Server engine hookup added.")
