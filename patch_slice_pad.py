#!/usr/bin/env python3
# Patch 2: pad the /slice fetch window so Cross Expiry's roll has neighbouring
# days loaded.
#
# WHY
#   Cross Expiry rolls into the NEXT weekly expiry (often the other index) a few
#   days after entry. ensureRangeLoaded() currently fetches ONLY the exact
#   selected dates, so the roll's target expiry / next-day bars fall outside the
#   slice -> the roll finds nothing -> "No trades generated". Full-history load
#   never had this because everything was in memory.
#
# FIX
#   Fetch a padded window (selected range +/- PAD_DAYS) from /slice, but leave the
#   user's dateFrom/dateTo untouched. The engine already filters results to the
#   selected range (runBacktest/cross-expiry honour params.dateFrom/dateTo), so
#   more data goes IN, the same reported range comes OUT.
#
# SAFETY
#   - Backs up to backtester.html.bak_pad first.
#   - Aborts without writing if it can't find its exact anchors.
#   - Idempotent: does nothing if already applied.
#
# USAGE (in /root/kite, the folder with backtester.html)
#   python3 patch_slice_pad.py
#   # revert if needed:  mv backtester.html.bak_pad backtester.html

import io, os, sys, shutil

PATH = os.environ.get("BT_HTML", "backtester.html")
PAD_DAYS = 15   # >= one weekly roll to the next expiry, both sides

if not os.path.isfile(PATH):
    print("ABORT: %s not found. cd into /root/kite or set BT_HTML." % PATH); sys.exit(1)

with io.open(PATH, "r", encoding="utf-8") as f:
    html = f.read()

if "__qFrom" in html:
    print("Already patched - nothing to do."); sys.exit(0)

# The single guarded HEAD probe line inside ensureRangeLoaded (unique in the file).
OLD = "  try { sliceOk = (await fetch(`/slice?from=${from}&to=${to}`, { method: 'HEAD' })).ok; } catch (e) {}"
# The single streaming GET inside ensureRangeLoaded (there is another /slice GET
# elsewhere, so match with its surrounding setBar calls to stay unique).
OLD_STREAM = "  setBar(5);\n  await streamCsv(`/slice?from=${from}&to=${to}`, 'range');\n  setBar(60);"

if html.count(OLD) != 1:
    print("ABORT: could not find the HEAD /slice probe exactly once. No changes made."); sys.exit(1)
if html.count(OLD_STREAM) != 1:
    print("ABORT: could not find the streaming /slice GET exactly once. No changes made."); sys.exit(1)

# Compute padded query bounds just before the probe. Uses local helpers only.
NEW = (
"  const __PAD = %d;\n"
"  const __qFrom = new Date(new Date(from) - __PAD * 86400000).toISOString().slice(0, 10);\n"
"  const __qTo   = new Date(new Date(to)   + __PAD * 86400000).toISOString().slice(0, 10);\n"
"  try { sliceOk = (await fetch(`/slice?from=${__qFrom}&to=${__qTo}`, { method: 'HEAD' })).ok; } catch (e) {}"
) % PAD_DAYS

NEW_STREAM = (
"  setBar(5);\n"
"  await streamCsv(`/slice?from=${__qFrom}&to=${__qTo}`, 'range');\n"
"  setBar(60);"
)

html = html.replace(OLD, NEW)
html = html.replace(OLD_STREAM, NEW_STREAM)

shutil.copyfile(PATH, PATH + ".bak_pad")
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print("Patched %s (backup %s.bak_pad). Slice now loads +/- %d days around the selected range." % (PATH, PATH, PAD_DAYS))
print("Reload the page, pick your range, Run. Cross Expiry should show trades again.")
