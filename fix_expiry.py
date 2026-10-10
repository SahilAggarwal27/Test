#!/usr/bin/env python3
# Fix: Cross Expiry (2PM) showed "No trades" because /slice data has no expiry
# column. Derives each index's weekly expiry from the calendar instead.
# Safe: .bak backup, idempotent, aborts if anchor not found.
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "function ceCalendarExp" in s:
    print("Already fixed."); sys.exit(0)
OLD = 'function ceNearestExp(date, inst){\n  const g = GROUPED[date] && GROUPED[date][inst]; if(!g) return null;\n  let ne=null;\n  for(const s in g) for(const r of g[s]){ if(r.exp && r.exp>=date && (ne===null||r.exp<ne)) ne=r.exp; }\n  return ne;\n}\n'
NEW = "function ceNearestExp(date, inst){\n  const g = GROUPED[date] && GROUPED[date][inst]; if(!g) return null;\n  let ne=null;\n  for(const s in g) for(const r of g[s]){ if(r.exp && r.exp>=date && (ne===null||r.exp<ne)) ne=r.exp; }\n  return ne || ceCalendarExp(date, inst);   // /slice data has no expiry column -> derive it from the weekly calendar\n}\n// Weekly expiry weekday by regime (0=Sun..6=Sat): NIFTY Thu -> Tue from Sep-2025;\n// SENSEX Fri -> Tue (2025) -> Thu from Sep-2025.\nfunction ceExpDow(inst, d){\n  if(inst==='NIFTY')  return d>='2025-09-01' ? 2 : 4;\n  if(inst==='SENSEX') return d>='2025-09-01' ? 4 : (d>='2025-01-01' ? 2 : 5);\n  return null;\n}\nlet _ceDatesRef=null, _ceDates=null;\nfunction ceCalendarExp(date, inst){\n  if(_ceDatesRef!==GROUPED){ _ceDatesRef=GROUPED; _ceDates=Object.keys(GROUPED).sort(); }\n  const last=_ceDates[_ceDates.length-1];\n  const fmt=x=>x.toISOString().slice(0,10);\n  const d=new Date(date+'T00:00:00Z');\n  for(let i=0;i<10;i++){\n    const ds=fmt(d);\n    if(d.getUTCDay()===ceExpDow(inst, ds)){\n      if(ds>last || GROUPED[ds]) return ds;              // trading day (or beyond loaded data)\n      for(let j=_ceDates.length-1;j>=0;j--){            // holiday -> previous trading day\n        if(_ceDates[j]<ds){ return _ceDates[j]>=date ? _ceDates[j] : null; }\n      }\n      return null;\n    }\n    d.setUTCDate(d.getUTCDate()+1);\n  }\n  return null;\n}\n"
if s.count(OLD) != 1:
    print("ABORT: anchor not found. No changes made."); sys.exit(1)
shutil.copyfile(P, P + ".bak2")
io.open(P, "w", encoding="utf-8").write(s.replace(OLD, NEW))
print("Fixed. Hard-refresh the page (Ctrl+Shift+R).")
