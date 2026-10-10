#!/usr/bin/env python3
# Long ranges (months/years) loaded nothing: one huge /slice request timed out, so only the
# live file (last ~5 weeks) was used. Now: /slice is fetched in 2-week chunks with progress,
# and only strikes within +-10 steps of spot are kept in memory (all any strategy uses).
import io, os, sys, shutil
P = os.environ.get("BT_HTML", "backtester.html")
s = io.open(P, encoding="utf-8").read()
if "/*CHUNK*/" in s:
    print("Already fixed."); sys.exit(0)
R = [
("  try { sliceOk = (await fetch(`/slice?from=${from}&to=${to}`, { method: 'HEAD' })).ok; } catch (e) {}",
 "  try { sliceOk = (await fetch(`/slice?from=${from}&to=${from}`, { method: 'HEAD' })).ok; } catch (e) {}   /*CHUNK*/ // probe a single day, not the whole range"),
("  await streamCsv(`/slice?from=${from}&to=${to}`, 'range');",
 """  { const iso = d => d.toISOString().slice(0,10); let a = new Date(from + 'T00:00:00Z'); const parts = [];
    while (iso(a) <= to) { const b = new Date(a); b.setUTCDate(b.getUTCDate() + 13); parts.push([iso(a), iso(b) < to ? iso(b) : to]); a = new Date(b); a.setUTCDate(a.getUTCDate() + 1); }
    for (let i = 0; i < parts.length; i++) {   // 2-week chunks: no server timeout, steady progress
      setBar(5 + 55 * i / parts.length);
      await streamCsv(`/slice?from=${parts[i][0]}&to=${parts[i][1]}`, `range ${i + 1}/${parts.length} (${parts[i][0]})`);
    } }"""),
("  if (RANGE_FROM && (date < RANGE_FROM || date > RANGE_TO)) return;   // keep only the selected range in memory",
 """  if (RANGE_FROM && (date < RANGE_FROM || date > RANGE_TO)) return;   // keep only the selected range in memory
  { const sp = SPECS[r.instrument]; if (sp && r.spot && r.strike && Math.abs(r.strike - r.spot) > 10 * sp.step) return; }   // far strikes: unused, save memory"""),
]
for a, b in R:
    if s.count(a) != 1:
        print("ABORT: anchor not found: " + a[:60]); sys.exit(1)
for a, b in R:
    s = s.replace(a, b)
shutil.copyfile(P, P + ".bak13")
io.open(P, "w", encoding="utf-8").write(s)
print("Chunked range loading enabled.")
