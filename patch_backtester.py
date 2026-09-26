#!/usr/bin/env python3
# One-time, reversible patch for backtester.html.
#
# WHAT IT DOES
#   The page currently streams the full option history into the browser on every
#   open -> that is what freezes / OOMs the tab. This patch makes it:
#     1. load NOTHING on open,
#     2. default the date pickers to the last ~30 days,
#     3. enable Run immediately.
#   Run then pulls ONLY the selected dates via the server's /slice endpoint
#   (that logic, ensureRangeLoaded, already exists in the file). So opening is
#   instant and memory stays small. The backtest engine itself is untouched.
#
# SAFETY
#   - Writes a .bak backup before changing anything.
#   - Aborts without writing if it can't find its exact anchors.
#   - Idempotent: running it again does nothing once patched.
#
# USAGE (run in the folder that contains backtester.html)
#   python3 patch_backtester.py
#   # revert if ever needed:  mv backtester.html.bak backtester.html

import io, os, sys, shutil

PATH = os.environ.get("BT_HTML", "backtester.html")

if not os.path.isfile(PATH):
    print("ABORT: %s not found. cd into the folder that serves it, or set BT_HTML=/path/to/backtester.html" % PATH)
    sys.exit(1)

with io.open(PATH, "r", encoding="utf-8") as f:
    html = f.read()

if "function initLazy()" in html:
    print("Already patched - nothing to do.")
    sys.exit(0)

CALL_OLD = "  checkCloudStatus();\n  tryAutoLoad();\n});"
CALL_NEW = "  checkCloudStatus();\n  initLazy();\n});"
ANCHOR   = "// Trigger auto-load when page is ready"

if html.count(CALL_OLD) != 1:
    print("ABORT: could not find the DOMContentLoaded auto-load call exactly once. No changes made.")
    sys.exit(1)
if html.count(ANCHOR) != 1:
    print("ABORT: could not find the anchor comment exactly once. No changes made.")
    sys.exit(1)

INIT_LAZY = (
"// =============== LAZY INIT (no bulk load on open) ===============\n"
"// Loading the full history into the browser on every open is what froze / OOMed\n"
"// the tab. We now load NOTHING on open - just set a recent default range and\n"
"// enable Run. Run pulls ONLY the selected dates via /slice (see ensureRangeLoaded),\n"
"// so opening is instant and memory stays small.\n"
"async function initLazy() {\n"
"  let last = new Date().toISOString().slice(0, 10);\n"
"  try {\n"
"    const r = await fetch(CLOUD_STATUS_URL, { cache: 'no-store' });\n"
"    if (r.ok) { const s = await r.json(); if (s && s.options && s.options.last) last = s.options.last; }\n"
"  } catch (e) {}\n"
"  const toDefault   = last;\n"
"  const fromDefault = new Date(new Date(last) - 30 * 86400000).toISOString().slice(0, 10);\n"
"  if (!document.getElementById('dateTo').value)   document.getElementById('dateTo').value   = toDefault;\n"
"  if (!document.getElementById('dateFrom').value) document.getElementById('dateFrom').value = fromDefault;\n"
"  document.getElementById('runBtn').disabled = false;\n"
"  document.getElementById('status').textContent = 'Ready - pick a date range and click Run. Only that range loads (fast).';\n"
"}\n\n"
)

html = html.replace(CALL_OLD, CALL_NEW)
html = html.replace(ANCHOR, INIT_LAZY + ANCHOR, 1)

shutil.copyfile(PATH, PATH + ".bak")
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print("Patched %s  (backup saved to %s.bak)." % (PATH, PATH))
print("Reload the page - it should open instantly. Pick a range and click Run.")
