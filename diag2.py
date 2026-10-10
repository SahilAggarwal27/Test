#!/usr/bin/env python3
# Why ~49k rows/day? Profile one day of /slice output (read-only).
import urllib.request, csv, io, collections
body = urllib.request.urlopen("http://127.0.0.1:8080/slice?from=2026-03-03&to=2026-03-03", timeout=600).read().decode()
rows = list(csv.DictReader(io.StringIO(body)))
print("rows:", len(rows), "| header:", list(rows[0].keys()) if rows else None)
by = collections.defaultdict(list)
for r in rows: by[r["instrument"]].append(r)
for inst, rs in by.items():
    mins = {r["datetime"] for r in rs}; strikes = sorted({float(r["strike"] or 0) for r in rs})
    exps = collections.Counter(r["expiry"] for r in rs)
    nospot = sum(1 for r in rs if not r["spot"])
    sp = [float(r["spot"]) for r in rs if r["spot"]]
    print(f"\n{inst}: {len(rs)} rows, {len(mins)} minutes, {len(strikes)} strikes ({strikes[:3]} .. {strikes[-3:]}), "
          f"spot range {min(sp) if sp else None}-{max(sp) if sp else None}, rows without spot {nospot}")
    print("  expiries:", dict(exps.most_common(4)))
    print("  first minutes:", sorted(mins)[:3], "last:", sorted(mins)[-2:])
    print("  sample:", [ (r['datetime'], r['strike'], r['spot'], r['ce_ltp']) for r in rs[:3] ])
