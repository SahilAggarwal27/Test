#!/usr/bin/env python3
# Clean Strategy list: Time-Based / Range Breakout / Cross Expiry, plus a "Scenario" dropdown that
# changes with the strategy (incl. a Compare entry):
#   Range Breakout: Tue/Thu square 15:25 | Tue/Thu square 14:00 | Compare both
#   Cross Expiry:   1) square all 14:00 | 2) next-expiry, sq 15:25 | 3) next-expiry, next day 10:03 | Compare all 3
import io, os, re, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*SCENARIO*/" in s:
    print("Already fixed."); sys.exit(0)
m = re.search(r'(<select id="strategy">\n)(.*?)(    </select>\n)', s, re.S)
A = "</script>\n</body>"
if not m or s.count(A) != 1 or "window.runCompareAll" not in s:
    print("ABORT: anchor not found."); sys.exit(1)
OPTS = ('      <option value="time_based" selected>Time-Based Short Straddle (sell at entry, exit at exit time)</option>\n'
        '      <option value="breakdown" data-rb="carry">Range Breakout (Sell Below Low, SL = High)</option>\n'
        '      <option value="cross_expiry" data-ce="roll1003">Cross Expiry (Tue/Thu 14:00 \u2014 next expiry, other index)</option>\n')
SC = ('\n    <div id="scenWrap" style="display:none">\n'
      '      <label>Scenario</label>\n'
      '      <select id="scenario"></select>\n'
      '    </div>\n')
s = s[:m.start(2)] + OPTS + m.group(3) + SC + s[m.end(3):]
s = s.replace(A, r"""
/*SCENARIO*/
(function(){
  const SC = {
    breakdown: [['rb:carry','Tue/Thu square 15:25'], ['rb:sq14','Tue/Thu square 14:00'], ['rb:compare','\u2696\ufe0f Compare both (15:25 vs 14:00)']],
    cross_expiry: [['ce:sq14','1) Square all positions at 14:00 (no next-expiry position)'],
                   ['ce:roll1525','2) 14:00 next-expiry position, square 15:25'],
                   ['ce:roll1003','3) 14:00 next-expiry position, carry, square next day 10:03'],
                   ['ce:compare','\u2696\ufe0f Compare all 3 scenarios']]
  };
  const st = $('strategy'), sc = $('scenario'), wrap = $('scenWrap');
  const opt = v => [...st.options].find(o => o.value === v);
  const apply = () => {
    const v = sc.value || '', [k, mode] = v.split(':');
    window.__cmpKind = (mode === 'compare') ? (k === 'ce' ? 'compare_ce' : 'compare_rb') : null;
    if (k === 'rb' && mode !== 'compare') { opt('breakdown').dataset.rb = mode; if ($('rbExpMode')) $('rbExpMode').value = mode; }
    if (k === 'ce' && mode !== 'compare') opt('cross_expiry').dataset.ce = mode;
    try { localStorage.setItem('bt_scen_' + st.value, v); } catch(e){}
  };
  const fill = () => {
    const list = SC[st.value];
    if (!list) { wrap.style.display = 'none'; sc.innerHTML = ''; window.__cmpKind = null; return; }
    sc.innerHTML = list.map(([v, t]) => '<option value="' + v + '">' + t + '</option>').join('');
    let saved = null; try { saved = localStorage.getItem('bt_scen_' + st.value); } catch(e){}
    if (saved && list.some(x => x[0] === saved)) sc.value = saved;
    wrap.style.display = 'block'; apply();
  };
  st.addEventListener('change', fill); sc.addEventListener('change', apply); fill();
  // Compare scenarios run before any other Run handler
  document.addEventListener('click', e => {
    if (!e.target.closest || !e.target.closest('#runBtn') || !window.__cmpKind) return;
    e.stopPropagation(); e.preventDefault(); window.runCompareAll();
  }, true);
})();
""" + A)
shutil.copyfile(P, P + ".bak19")
io.open(P, "w", encoding="utf-8").write(s)
print("Strategy list cleaned; Scenario dropdown added.")
