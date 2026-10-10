#!/usr/bin/env python3
# Data Calendar button: Year -> Month -> Day view of which dates have data (NIFTY / SENSEX,
# rows, candle High/Low). Click a year to expand months, a month to see its calendar.
# Reads data_days.json built on the server by coverage_build.py (refreshed nightly).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*DATACAL*/" in s:
    print("Already fixed."); sys.exit(0)
K = '<button id="coverageBtn"'
A = "</script>\n</body>"
if s.count(K) != 1 or s.count(A) != 1:
    print("ABORT: anchor not found."); sys.exit(1)
i = s.index("</button>", s.index(K)) + len("</button>")
s = s[:i] + '\n    <button id="calBtn" style="background:#0b7a75;margin-top:8px">\U0001F5D3\ufe0f Data Calendar (year / month / day)</button>' + s[i:]
JS = r"""
/*DATACAL*/
async function showDataCalendar(){
  const main = $('main');
  main.innerHTML = '<div class="empty"><h2>Loading data calendar…</h2></div>';
  let cov = null;
  for (const u of ['/data_days.json', '/data/data_days.json', 'data_days.json']) {
    try { const r = await fetch(u + '?_=' + Date.now(), { cache: 'no-store' }); if (r.ok) { cov = await r.json(); break; } } catch (e) {}
  }
  if (!cov || !cov.days) { main.innerHTML = '<div class="warn">Calendar not built yet. On the server run: <code>python3 coverage_build.py</code></div>'; return; }
  const D = cov.days, insts = ['NIFTY', 'SENSEX'], today = new Date().toISOString().slice(0, 10);
  const dates = Object.keys(D).sort(), first = dates[0];
  const iso = d => d.toISOString().slice(0, 10);
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const COL = { full: '#c8efd4', part: '#fff1b8', none: '#f8c9cc' };
  const st = d => { const e = D[d]; if (!e) return 'none'; const n = insts.filter(i => e[i] && e[i][0] > 0).length; return n === insts.length ? 'full' : (n ? 'part' : 'none'); };
  const bar = (f, p, w) => `<span style="display:inline-block;width:120px;height:9px;background:${COL.none};border-radius:4px;overflow:hidden;vertical-align:middle;margin:0 8px">`
    + `<span style="display:inline-block;height:9px;width:${w ? f / w * 120 : 0}px;background:#2CA02C"></span><span style="display:inline-block;height:9px;width:${w ? p / w * 120 : 0}px;background:#e6b800"></span></span>`;
  const line = (lbl, w, f, p, h) => `<b>${lbl}</b>${bar(f, p, w)}${f + p}/${w} weekdays (${w ? Math.round((f + p) / w * 100) : 0}%) · both ${f} · one ${p} · <span style="color:#d62728">missing ${w - f - p}</span> · H/L ${h}`;
  let html = `<h2 style="color:#1F3864">\u{1F5D3}\ufe0f Data Calendar</h2>
    <p style="color:#6c7a89;font-size:13px">Click a year, then a month.
    <span style="background:${COL.full};padding:0 6px">NIFTY + SENSEX</span>
    <span style="background:${COL.part};padding:0 6px">one index only</span>
    <span style="background:${COL.none};padding:0 6px">weekday with no data (holiday or gap)</span>
    · <b>HL</b> = candle High/Low available · hover a day for row counts · updated ${cov.generated}</p>`;
  for (let y = +today.slice(0, 4); y >= +first.slice(0, 4); y--) {
    let W = 0, F = 0, Pp = 0, H = 0, mhtml = '';
    for (let m = 11; m >= 0; m--) {
      let w = 0, f = 0, p = 0, h = 0, cells = '';
      const d0 = new Date(Date.UTC(y, m, 1)); let pad = (d0.getUTCDay() + 6) % 7; if (pad > 4) pad = 0;
      let row = '<tr>' + '<td></td>'.repeat(pad), col = pad;
      for (let d = new Date(d0); d.getUTCMonth() === m; d.setUTCDate(d.getUTCDate() + 1)) {
        const ds = iso(d), dw = d.getUTCDay(); if (dw === 0 || dw === 6) continue;
        if (ds > today || ds < first) { row += '<td></td>'; } else {
          w++; const s = st(ds), e = D[ds] || {}; if (s === 'full') f++; else if (s === 'part') p++;
          const hl = insts.some(i => e[i] && e[i][1] > 0); if (hl) h++;
          const tip = insts.map(i => `${i}: ${e[i] ? e[i][0].toLocaleString() + ' rows' + (e[i][1] ? ', H/L' : '') : 'none'}`).join(' | ');
          row += `<td title="${fmtD(ds)} — ${tip}" style="background:${COL[s]};text-align:center;padding:4px 2px;border:1px solid #fff;min-width:46px">${d.getUTCDate()}`
            + `<div style="font-size:9px;color:#555">${insts.map(i => e[i] ? i[0] : '·').join(' ')}${hl ? ' HL' : ''}</div></td>`;
        }
        if (++col === 5) { cells += row + '</tr>'; row = '<tr>'; col = 0; }
      }
      if (col) cells += row + '<td></td>'.repeat(5 - col) + '</tr>';
      if (!w) continue;
      W += w; F += f; Pp += p; H += h;
      mhtml += `<details style="margin:4px 0 4px 18px"><summary style="cursor:pointer;font-size:13px">${line(MON[m], w, f, p, h)}</summary>
        <table style="width:auto;margin:6px 0 10px 10px;font-size:12px"><thead><tr>${['Mon','Tue','Wed','Thu','Fri'].map(x => `<th style="text-align:center">${x}</th>`).join('')}</tr></thead><tbody>${cells}</tbody></table></details>`;
    }
    if (!W) continue;
    html += `<details style="margin:6px 0;border:1px solid #e3e8ef;border-radius:6px;padding:6px 10px;background:#fff"${y === +today.slice(0, 4) ? ' open' : ''}>
      <summary style="cursor:pointer;font-size:15px">${line(String(y), W, F, Pp, H)}</summary>${mhtml}</details>`;
  }
  main.innerHTML = html;
}
$('calBtn').addEventListener('click', showDataCalendar);
"""
s = s.replace(A, JS + A)
shutil.copyfile(P, P + ".bak14")
io.open(P, "w", encoding="utf-8").write(s)
print("Data Calendar added.")
