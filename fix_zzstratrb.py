#!/usr/bin/env python3
# Range Breakout Tue/Thu modes built into the Strategy dropdown (options share value "breakdown" /
# "compare" so all existing logic keeps working; data-rb sets the mode). Separate dropdown hidden.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*STRATRB*/" in s:
    print("Already fixed."); sys.exit(0)
B = '      <option value="breakdown">Range Breakout (Sell Below Low, SL = High)</option>\n'
C = '      <option value="compare">\u2696\ufe0f Compare: Cross Expiry vs Range Breakout (Low / SL High)</option>\n'
W = '    <div style="margin-top:8px">\n      <label>Range Breakout \u2014 Tue/Thu (expiry day)</label>\n'
N = "  const NA='Cross Expiry', NB='Range Breakout (Low / SL High)';"
A = "</script>\n</body>"
for a in (B, C, W, A):
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
V = [('sq14', 'Tue/Thu square 14:00'), ('roll14', 'Tue/Thu 14:00 roll (Cross Expiry logic, exit next day 10:03)')]
s = s.replace(B, B.replace('<option ', '<option data-rb="carry" '))   # standalone RB 14:00 / 14:00-roll options removed (in Compare only)
s = s.replace(C, C.replace('<option ', '<option data-rb="carry" ') +
              ''.join('      <option value="compare" data-rb="%s">\u2696\ufe0f Compare: Cross Expiry vs Range Breakout \u2014 %s</option>\n' % v for v in V))
s = s.replace(W, W.replace('<div style="margin-top:8px">', '<div id="rbExpWrap" style="display:none;margin-top:8px">'))
if s.count(N) == 1:
    s = s.replace(N, "  const RBL={carry:'',sq14:' \u2014 Tue/Thu 14:00',roll14:' \u2014 14:00 roll'};\n"
                     "  const NA='Cross Expiry', NB='Range Breakout (Low / SL High)'+(RBL[base.rbExpMode]||'');")
s = s.replace(A, r"""
/*STRATRB*/
(function(){
  const sel = document.getElementById('strategy'), rb = document.getElementById('rbExpMode');
  if (!sel || !rb) return;
  const sync = () => { const o = sel.options[sel.selectedIndex]; rb.value = (o && o.dataset.rb) || 'carry'; };
  sel.addEventListener('change', () => { sync(); try { localStorage.setItem('bt_strategy_idx', String(sel.selectedIndex)); } catch(e){} });
  let i = null; try { i = localStorage.getItem('bt_strategy_idx'); } catch(e){}
  if (i !== null && +i >= 0 && +i < sel.options.length && sel.options[+i].value === sel.value) sel.selectedIndex = +i;
  sync();
})();
""" + A)
shutil.copyfile(P, P + ".bak15")
io.open(P, "w", encoding="utf-8").write(s)
print("Range Breakout Tue/Thu modes added to the Strategy dropdown.")
