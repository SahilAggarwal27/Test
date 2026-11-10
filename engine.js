// engine.js — server-side backtest engine for backtester.html
// Runs the SAME strategy code as the page (it loads the deployed backtester.html), reads data
// from the local /slice in 2-week chunks, processes the range in ~2-month segments (with a
// warm-up before and a look-ahead after each, so carried positions stay correct) and returns
// only the finished results. Any range, even 10 years, without loading data into the browser.
//   GET  /health          -> {ok:true}
//   POST /run {kind, params}  kind = cross_expiry | breakdown | time_based | compare | compare_all | compare_ce | compare_vix  -> {id}
//   GET  /job/<id>        -> {status: queued|running|done|error, progress, pct, result?}
const http = require('http'), https = require('https'), fs = require('fs'), vm = require('vm'), path = require('path');
const BASE = process.env.KITE_DIR || '/root/kite';
const PAGE = process.env.BT_PAGE || path.join(BASE, 'backtester.html');
const SLICE = process.env.SLICE_URL || 'http://127.0.0.1:8080/slice';
const PORT = +(process.env.ENGINE_PORT || 8090);
const SEG_DAYS = 31, WARM = 10, LOOK = 12, CHUNK = 14;
const VERSION = 'engine-2-vix';

// ---------- page code in a sandbox with a do-nothing DOM ----------
function makeFake() {
  let fake;
  const h = {
    get(t, k) {
      if (k === Symbol.iterator) return function* () {};
      if (k === Symbol.toPrimitive) return () => '';
      if (k === 'then') return undefined;
      if (k === 'length') return 0;
      return fake;
    },
    apply() { return fake; }, construct() { return fake; }, set() { return true; }
  };
  fake = new Proxy(function () {}, h);
  return fake;
}
const HELPERS = `
var __H = {
  reset(from, to){ resetData(); OHLC_SEEN.clear(); RANGE_FROM = from; RANGE_TO = to; if (typeof _ceDatesRef !== 'undefined') _ceDatesRef = null; },
  trim(keepFrom, from, to){   // slide the window: drop days before keepFrom, then only NEW days get ingested
    for (const d of Object.keys(GROUPED)) if (d < keepFrom) delete GROUPED[d];
    SEEN = new Set(); OHLC_SEEN.clear(); RANGE_FROM = from; RANGE_TO = to;
    if (typeof _ceDatesRef !== 'undefined') _ceDatesRef = null;
  },
  setOhlc(v){ OHLC_MODE = v; },
  ingest(rows){ for (const r of rows) ingestRow(r); },
  ndates(){ return Object.keys(GROUPED || {}).length; },
  costOf(trades, p){ let c = 0; for (const t of trades) { const lq = SPECS[t.instrument] ? SPECS[t.instrument].lot : 0; c += p.brokerage * p.lots + p.slippage * lq * p.lots; } return c; },
  ce(p, S, E, warmS, lookE){
    const r = runBacktestCrossExpiry(Object.assign({}, p, {strategy:'cross_expiry', dateFrom: warmS, dateTo: lookE}));
    const kept = r.trades.filter(t => t.date >= S && t.date <= E);
    const mp = Object.assign({}, p, {dateFrom: S, dateTo: lookE});
    const reg = {}; for (const d in (r.regimeLog || {})) if (d >= S && d <= E) reg[d] = r.regimeLog[d];
    return { trades: kept, daily: ceMtmDaily({trades: kept}, mp, false), byInst: ceMtmDaily({trades: kept}, mp, true),
             costs: __H.costOf(kept, p), carrySkips: r.carrySkips || 0, regime: reg };
  },
  day(p, S, E){
    const r = runBacktest(Object.assign({}, p, {dateFrom: S, dateTo: E}));
    return { trades: r.trades, daily: r.dailyPnl, costs: r.costs, carrySkips: r.carrySkips || 0 };
  }
};`;
function newContext() {
  const html = fs.readFileSync(PAGE, 'utf8');
  const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]);
  const fake = makeFake();
  const ctx = {
    console, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
    document: { getElementById: () => fake, querySelector: () => fake, querySelectorAll: () => [], createElement: () => fake, addEventListener() {}, body: fake },
    Chart: function () { return fake; }, Papa: fake, fetch: async () => ({ ok: false, json: async () => null }),
    AbortController, navigator: {}, location: { hostname: 'localhost' }, Event: function () {}, alert() {},
    URL: { createObjectURL() { return ''; }, revokeObjectURL() {} }, Blob: function () {}, localStorage: undefined
  };
  ctx.window = ctx; ctx.self = ctx; ctx.addEventListener = () => {}; ctx.removeEventListener = () => {};
  vm.createContext(ctx);
  for (const s of scripts) vm.runInContext(s, ctx, { filename: 'backtester.html' });
  vm.runInContext(HELPERS, ctx, { filename: 'helpers.js' });
  return ctx;
}

// ---------- data ----------
function parseCsv(text) {
  const lines = text.split(/\r?\n/); if (!lines.length) return [];
  const hdr = lines[0].replace(/^\ufeff/, '').split(',');
  const out = [];
  for (let i = 1; i < lines.length; i++) {
    const L = lines[i]; if (!L) continue;
    const v = L.split(','), r = {};
    for (let j = 0; j < hdr.length; j++) {
      const x = v[j];
      r[hdr[j]] = (x === undefined || x === '') ? null : (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(x) ? Number(x) : x);
    }
    out.push(r);
  }
  return out;
}
function getText(url) {
  return new Promise((res, rej) => {
    http.get(url, r => {
      if (r.statusCode !== 200) { r.resume(); return rej(new Error('slice HTTP ' + r.statusCode)); }
      const chunks = []; r.on('data', c => chunks.push(c)); r.on('end', () => res(Buffer.concat(chunks).toString('utf8')));
    }).on('error', rej);
  });
}
const iso = d => d.toISOString().slice(0, 10);
const addDays = (s, n) => { const d = new Date(s + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return iso(d); };
function fileSpan(f) {   // first/last date in a local CSV (to skip files that don't overlap a segment)
  try {
    const fd = fs.openSync(f, 'r'), st = fs.fstatSync(fd);
    const head = Buffer.alloc(Math.min(4096, st.size)); fs.readSync(fd, head, 0, head.length, 0);
    const tail = Buffer.alloc(Math.min(4096, st.size)); fs.readSync(fd, tail, 0, tail.length, st.size - tail.length);
    fs.closeSync(fd);
    const dates = s => (s.match(/\d{4}-\d{2}-\d{2}/g) || []);
    const a = dates(head.toString()), b = dates(tail.toString());
    return a.length && b.length ? [a[0], b[b.length - 1]] : null;
  } catch (e) { return null; }
}
async function loadRange(ctx, from, to, prog) {
  ctx.__H.reset(from, to);
  await loadSources(ctx, from, to, prog);
}
async function loadSources(ctx, from, to, prog) {
  const ohlc = path.join(BASE, 'kite_ohlc_data.csv'), live = path.join(BASE, 'kite_live_data.csv');
  const ov = f => { const sp = fileSpan(f); return sp && !(sp[1] < from || sp[0] > to); };
  if (ov(ohlc)) { ctx.__H.setOhlc(true); ctx.__H.ingest(parseCsv(fs.readFileSync(ohlc, 'utf8'))); ctx.__H.setOhlc(false); }
  for (let a = from; a <= to; a = addDays(a, CHUNK)) {
    const b = addDays(a, CHUNK - 1) < to ? addDays(a, CHUNK - 1) : to;
    prog && prog(a);
    ctx.__H.ingest(parseCsv(await getText(`${SLICE}?from=${a}&to=${b}`)));
  }
  if (ov(live)) ctx.__H.ingest(parseCsv(fs.readFileSync(live, 'utf8')));
}


// ---------- India VIX (for the VIX regime entry) ----------
// Per trading day: the collected 09:20 value (vix_live_data.csv) where available, else the PREVIOUS day's
// close from Yahoo ^INDIAVIX (known before the open -> no look-ahead). Cached in vix_daily.csv, refreshed every 6h.
const VIX_FILE = path.join(BASE, 'vix_daily.csv');
let VIX_CACHE = null, VIX_SRC = '';
function getJson(url) {
  return new Promise((res, rej) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 30000 }, r => {
      if (r.statusCode !== 200) { r.resume(); return rej(new Error('HTTP ' + r.statusCode)); }
      const c = []; r.on('data', x => c.push(x)); r.on('end', () => { try { res(JSON.parse(Buffer.concat(c).toString())); } catch (e) { rej(e); } });
    }).on('error', rej).on('timeout', function () { this.destroy(new Error('timeout')); });
  });
}
function liveVix0920() {   // {date: value at ~09:20} from the live VIX collector, whatever its column names are
  const out = {};
  for (const f of [path.join(BASE, 'vix_live_data.csv'), path.join(BASE, 'data', 'vix_live_data.csv')]) {
    if (!fs.existsSync(f)) continue;
    try {
      const rows = parseCsv(fs.readFileSync(f, 'utf8')); if (!rows.length) continue;
      const keys = Object.keys(rows[0]), low = keys.map(k => k.toLowerCase());
      const dk = keys[low.findIndex(k => /datetime|timestamp/.test(k))] || keys[low.findIndex(k => k === 'date')];
      const tk = keys[low.findIndex(k => k === 'time')];
      const vk = keys[low.findIndex(k => ['ltp', 'last_price', 'vix', 'close', 'price', 'value'].includes(k))];
      if (!dk || !vk) continue;
      for (const r of rows) {
        const ds = String(r[dk] || ''), d = ds.slice(0, 10), t = tk ? String(r[tk] || '') : (ds.match(/\d{2}:\d{2}/) || [''])[0];
        const v = +r[vk]; if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || !(v > 0) || !t) continue;
        if (t.slice(0, 5) >= '09:20' && t.slice(0, 5) <= '09:25' && out[d] == null) out[d] = v;
      }
    } catch (e) { console.error('live vix', e.message); }
  }
  return out;
}
async function ensureVix() {
  try { if (VIX_CACHE && fs.existsSync(VIX_FILE) && Date.now() - fs.statSync(VIX_FILE).mtimeMs < 6 * 3600e3) return VIX_CACHE; } catch (e) {}
  const map = {}; let src = [];
  try {
    const j = await getJson('https://query1.finance.yahoo.com/v8/finance/chart/%5EINDIAVIX?period1=1199145600&period2=' + Math.floor(Date.now() / 1000 + 86400) + '&interval=1d');
    const r = j.chart.result[0], ts = r.timestamp, cl = r.indicators.quote[0].close;
    let prev = null;
    for (let i = 0; i < ts.length; i++) {
      const d = new Date((ts[i] + 19800) * 1000).toISOString().slice(0, 10);
      if (prev != null) map[d] = prev;
      if (cl[i] != null) prev = cl[i];
    }
    src.push('prev close (Yahoo) ' + Object.keys(map).length + ' days');
  } catch (e) {
    console.error('vix download failed', e.message);
    if (fs.existsSync(VIX_FILE)) { for (const r of parseCsv(fs.readFileSync(VIX_FILE, 'utf8'))) if (r.date && r.vix > 0) map[r.date] = +r.vix; src.push('cached file'); }
  }
  const lv = liveVix0920(), nl = Object.keys(lv).length;
  Object.assign(map, lv); if (nl) src.push('live 09:20 ' + nl + ' days');
  const days = Object.keys(map).sort();
  if (days.length) { try { fs.writeFileSync(VIX_FILE, 'date,vix\n' + days.map(d => d + ',' + (+map[d]).toFixed(2)).join('\n') + '\n'); } catch (e) {} }
  VIX_CACHE = map; VIX_SRC = src.join(' + ') || 'none';
  return map;
}
const tShift = (t, m) => { const [h, mi] = t.split(':').map(Number), x = h * 60 + mi + m; return String(Math.floor(x / 60)).padStart(2, '0') + ':' + String(x % 60).padStart(2, '0'); };
function vixVariants(p) {
  const lo = +(p.vixLo != null ? p.vixLo : 14), tMid = p.vixTimeMid || '09:40';
  return {
    base: { vixMode: 'fixed', vixFixedTime: '10:05' },
    fixed0940: { vixMode: 'fixed', vixFixedTime: tMid },
    switch: { vixMode: 'switch' },
    lo_m1: { vixMode: 'switch', vixLo: lo - 1 },
    lo_p1: { vixMode: 'switch', vixLo: lo + 1 },
    t_m5: { vixMode: 'switch', vixTimeMid: tShift(tMid, -5) },
    t_p10: { vixMode: 'switch', vixTimeMid: tShift(tMid, 10) },
  };
}

// ---------- job ----------
function segments(from, to) {
  const out = []; let a = from;
  while (a <= to) { const b = addDays(a, SEG_DAYS - 1) < to ? addDays(a, SEG_DAYS - 1) : to; out.push([a, b]); a = addDays(b, 1); }
  return out;
}
function mergeDaily(map, rows, from, to, byInst) {
  for (const x of rows || []) {
    if (x.date < from || x.date > to) continue;
    const k = byInst ? x.date + '|' + x.instrument : x.date;
    const m = map.get(k) || { date: x.date, dow: x.dow, inst: new Set(), atm: new Set(), pnl: 0, nTrades: 0, slHits: 0 };
    String(x.instrument || '').split('+').forEach(s => s && s !== '-' && m.inst.add(s));
    String(x.atm == null ? '' : x.atm).split(' / ').forEach(s => s && s !== '-' && m.atm.add(s));
    m.pnl += x.pnl || 0; m.nTrades += x.nTrades || 0; m.slHits += x.slHits || 0;
    map.set(k, m);
  }
}
const finish = map => [...map.values()].sort((a, b) => a.date < b.date ? -1 : a.date > b.date ? 1 : 0)
  .map(m => ({ date: m.date, dow: m.dow, instrument: [...m.inst].join('+') || '-', atm: [...m.atm].join(' / ') || '-', pnl: m.pnl, nTrades: m.nTrades, slHits: m.slHits }));

async function runJob(job) {
  const { kind } = job, p = job.params, from = p.dateFrom, to = p.dateTo;
  if (!from || !to || from > to) throw new Error('bad date range');
  const ctx = newContext();
  try { ctx.VIX_DAY = await ensureVix(); } catch (e) { console.error('vix', e); ctx.VIX_DAY = {}; }
  const segs = segments(from, to);
  const VXV = kind === 'compare_vix' ? vixVariants(p) : null;
  const vxs = {}; if (VXV) for (const k in VXV) vxs[k] = { trades: [], daily: new Map(), costs: 0, carrySkips: 0, regime: {} };
  const ce = { trades: [], daily: new Map(), byInst: new Map(), costs: 0, carrySkips: 0 };
  const dy = { trades: [], daily: [], costs: 0, carrySkips: 0 };
  const RBM = ['carry', 'sq14', 'roll14'];
  const CEM = ['live', 'sq14', 'roll1525', 'roll1003'];
  const ces = {}; for (const m of CEM) ces[m] = { trades: [], daily: new Map(), costs: 0, carrySkips: 0 };
  const dys = {}; for (const m of RBM) dys[m] = { trades: [], daily: [], costs: 0, carrySkips: 0 };
  const rbParams = (kind === 'compare' || kind === 'compare_all')
    ? Object.assign({}, p, { strategy: 'breakdown', reentryMode: 'original', reentrySL: 'samesl', maxReentries: 50, carry: 'nextday' })
    : Object.assign({}, p, { strategy: kind });
  let loadedTo = null;
  for (let i = 0; i < segs.length; i++) {
    const [S, E] = segs[i];
    const warmS = i === 0 ? S : addDays(S, -WARM);
    const lookE = addDays(E, LOOK) < to ? addDays(E, LOOK) : to;
    const prog = a => { job.progress = `segment ${i + 1}/${segs.length} · loading ${a}`; job.pct = Math.round(100 * (i + 0.5) / segs.length); };
    if (loadedTo === null || warmS > loadedTo) await loadRange(ctx, warmS, lookE, prog);
    else if (lookE > loadedTo) { const nf = addDays(loadedTo, 1); ctx.__H.trim(warmS, nf, lookE); await loadSources(ctx, nf, lookE, prog); }
    else ctx.__H.trim(warmS, warmS, lookE);
    loadedTo = lookE > (loadedTo || '') ? lookE : loadedTo;
    job.progress = `segment ${i + 1}/${segs.length} · computing ${S} → ${E}`;
    if (kind === 'cross_expiry' || kind === 'compare' || kind === 'compare_all') {
      const r = ctx.__H.ce(p, S, E, warmS, lookE);
      ce.trades.push(...r.trades); mergeDaily(ce.daily, r.daily, from, to, false); mergeDaily(ce.byInst, r.byInst, from, to, true);
      ce.costs += r.costs; ce.carrySkips += r.carrySkips;
    }
    if (kind === 'compare_vix') {
      for (const k in VXV) { const r = ctx.__H.ce(Object.assign({}, p, { ceMode: p.ceMode || 'live' }, VXV[k]), S, E, warmS, lookE), c = vxs[k];
        c.trades.push(...r.trades); mergeDaily(c.daily, r.daily, from, to, false); c.costs += r.costs; c.carrySkips += r.carrySkips; Object.assign(c.regime, r.regime); }
    } else if (kind === 'compare_ce') {
      for (const m of CEM) { const r = ctx.__H.ce(Object.assign({}, p, { ceMode: m }), S, E, warmS, lookE), c = ces[m];
        c.trades.push(...r.trades); mergeDaily(c.daily, r.daily, from, to, false); c.costs += r.costs; c.carrySkips += r.carrySkips; }
    } else if (kind === 'compare_all') {
      for (const m of RBM) { const r = ctx.__H.day(Object.assign({}, rbParams, { rbExpMode: m }), S, E), d = dys[m];
        d.trades.push(...r.trades); d.daily.push(...r.daily); d.costs += r.costs; d.carrySkips += r.carrySkips; }
    } else if (kind !== 'cross_expiry' && kind !== 'compare_vix') {
      const r = ctx.__H.day(rbParams, S, E);
      dy.trades.push(...r.trades); dy.daily.push(...r.daily); dy.costs += r.costs; dy.carrySkips += r.carrySkips;
    }
    job.pct = Math.round(100 * (i + 1) / segs.length);
  }
  ctx.__H.reset(null, null);
  const ceRes = () => ({ trades: ce.trades, dailyPnl: finish(ce.daily), dailyPnlByInst: finish(ce.byInst), costs: ce.costs, carrySkips: ce.carrySkips });
  const dyRes = () => ({ trades: dy.trades, dailyPnl: dy.daily, costs: dy.costs, carrySkips: dy.carrySkips });
  if (kind === 'compare_vix') {
    const vx = {}; for (const k in vxs) vx[k] = { trades: vxs[k].trades, dailyPnl: finish(vxs[k].daily), costs: vxs[k].costs, carrySkips: vxs[k].carrySkips, regime: vxs[k].regime };
    const vix = {}; for (const d in (ctx.VIX_DAY || {})) if (d >= from && d <= to) vix[d] = ctx.VIX_DAY[d];
    return { vx, vix, vixSrc: VIX_SRC, split: '2025-01-01' };
  }
  if (kind === 'compare_ce') { const ce3 = {}; for (const m of CEM) ce3[m] = { trades: ces[m].trades, dailyPnl: finish(ces[m].daily), costs: ces[m].costs, carrySkips: ces[m].carrySkips }; return { ce3 }; }
  if (kind === 'compare') return { ce: ceRes(), rb: dyRes() };
  if (kind === 'compare_all') { const rb = {}; for (const m of RBM) rb[m] = { trades: dys[m].trades, dailyPnl: dys[m].daily, costs: dys[m].costs, carrySkips: dys[m].carrySkips }; return { ce: ceRes(), rb }; }
  return kind === 'cross_expiry' ? ceRes() : dyRes();
}

// ---------- HTTP ----------
const jobs = new Map(); let queue = Promise.resolve(), seq = 0;
function send(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(obj));
}
function serve() {
  const srv = http.createServer((req, res) => {
    if (req.method === 'OPTIONS') return send(res, 204, {});
    const u = req.url.split('?')[0];
    if (u === '/health') return send(res, 200, { ok: true, version: VERSION, queued: [...jobs.values()].filter(j => j.status === 'queued' || j.status === 'running').length });
    if (u === '/run' && req.method === 'POST') {
      let body = ''; req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
      req.on('end', () => {
        let q; try { q = JSON.parse(body); } catch (e) { return send(res, 400, { error: 'bad json' }); }
        if (!['cross_expiry', 'breakdown', 'time_based', 'compare', 'compare_all', 'compare_ce', 'compare_vix'].includes(q.kind) || !q.params) return send(res, 400, { error: 'bad request' });
        const id = (++seq).toString(36) + Date.now().toString(36);
        const job = { id, kind: q.kind, params: q.params, status: 'queued', progress: 'queued', pct: 0, t: Date.now() };
        jobs.set(id, job);
        queue = queue.then(async () => {
          job.status = 'running'; const t0 = Date.now();
          try { job.result = await runJob(job); job.status = 'done'; job.progress = `done in ${Math.round((Date.now() - t0) / 1000)}s`; }
          catch (e) { job.status = 'error'; job.error = String(e && e.message || e); console.error(e); }
        });
        send(res, 200, { id });
      });
      return;
    }
    const m = u.match(/^\/job\/([a-z0-9]+)$/);
    if (m) {
      const j = jobs.get(m[1]); if (!j) return send(res, 404, { error: 'no such job' });
      const out = { status: j.status, progress: j.progress, pct: j.pct, error: j.error };
      if (j.status === 'done') { out.result = j.result; setTimeout(() => jobs.delete(j.id), 600000); }
      return send(res, 200, out);
    }
    send(res, 404, { error: 'not found' });
  });
  srv.requestTimeout = 0; srv.headersTimeout = 60000;
  srv.listen(PORT, '0.0.0.0', () => console.log(`backtest engine ${VERSION} on :${PORT} (page ${PAGE}, slice ${SLICE})`));
}
if (require.main === module) serve();
module.exports = { newContext, loadRange, runJob, parseCsv, segments, addDays };
