#!/usr/bin/env python3
# Strategy dropdown: 4th option "Compare" (runs Cross Expiry vs Range Breakout on Run),
# and the page remembers the last strategy picked instead of resetting to Time-Based.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*STRATPICK*/" in s:
    print("Already fixed."); sys.exit(0)
K = '<option value="cross_expiry">'
A = "</script>\n</body>"
if s.count(K) != 1 or s.count(A) != 1 or "function runCompare" not in s:
    print("ABORT: anchor not found."); sys.exit(1)
i = s.index("</option>", s.index(K)) + len("</option>")
OPT = '\n      <option value="compare">\u2696\ufe0f Compare: Cross Expiry vs Range Breakout (Low / SL High)</option>'
s = s[:i] + OPT + s[i:]
JS = r"""
/*STRATPICK*/
(function(){
  const sel = $('strategy');
  const apply = () => {
    if (sel.value === 'compare') {           // show the Range Breakout window inputs; no entry time / % SL
      $('rangeFields').style.display = 'block';
      $('timeFields').style.display = 'none';
      $('slField').style.display = 'none';
      $('slNote').style.display = 'none';
    }
  };
  sel.addEventListener('change', () => { try { localStorage.setItem('bt_strategy', sel.value); } catch(e){} apply(); });
  $('runBtn').addEventListener('click', (e) => {
    if (sel.value === 'compare') { e.stopImmediatePropagation(); runCompare(); }
  }, true);
  let saved = null; try { saved = localStorage.getItem('bt_strategy'); } catch(e){}
  if (saved && [...sel.options].some(o => o.value === saved)) {
    sel.value = saved; sel.dispatchEvent(new Event('change'));
  }
})();
"""
s = s.replace(A, JS + A)
shutil.copyfile(P, P + ".bak11")
io.open(P, "w", encoding="utf-8").write(s)
print("Strategy dropdown: Compare added + remembered.")
