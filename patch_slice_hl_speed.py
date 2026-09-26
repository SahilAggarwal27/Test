#!/usr/bin/env python3
# Patch 4: speed up the H/L join in /slice.
#
# WHY
#   patch_slice_hl joined the WHOLE kite_ohlc_data.csv on every /slice call
#   (DuckDB rescans the entire CSV each time -> slow). This adds a date filter on
#   the CSV side of the join so only the requested days are read, matching the
#   Parquet side. Same output, much less work.
#
# SAFETY
#   - Backs up cloud_server.py to cloud_server.py.bak_hlspeed first.
#   - Aborts without writing if the expected joined SELECT isn't present.
#   - Idempotent.
#
# USAGE (in /root/kite)
#   python3 patch_slice_hl_speed.py
#   sudo systemctl restart cloudserver.service

import io, os, sys, shutil

PATH = os.environ.get("CLOUD_SERVER", "cloud_server.py")

if not os.path.isfile(PATH):
    print("ABORT: %s not found. cd into /root/kite." % PATH); sys.exit(1)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "o.datetime BETWEEN" in src:
    print("Already patched - nothing to do."); sys.exit(0)

# Anchor: the ON ... clause of the LEFT JOIN added by patch_slice_hl.
OLD = (
"              ON o.instrument = p.instrument AND o.datetime = p.datetime\n"
"             AND o.strike = p.strike AND o.expiry = p.expiry\n"
)
NEW = (
"              ON o.instrument = p.instrument AND o.datetime = p.datetime\n"
"             AND o.strike = p.strike AND o.expiry = p.expiry\n"
"             AND o.datetime BETWEEN ? AND ?\n"
)

if src.count(OLD) != 1:
    print("ABORT: joined ON-clause not found exactly once (run patch_slice_hl first?). No changes."); sys.exit(1)

# The params list currently ends with [fy, ty, d_from, d_to]. The two new '?'
# placeholders sit BEFORE the WHERE clause's fy/ty, so they must be bound first.
OLD_PARAMS = "        [fy, ty, d_from, d_to],"
NEW_PARAMS = "        [d_from, d_to + ' 23:59:59', fy, ty, d_from, d_to],"

if src.count(OLD_PARAMS) != 1:
    print("ABORT: query_slice params list not found exactly once. No changes."); sys.exit(1)

src = src.replace(OLD, NEW)
src = src.replace(OLD_PARAMS, NEW_PARAMS)

shutil.copyfile(PATH, PATH + ".bak_hlspeed")
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("Patched %s (backup %s.bak_hlspeed)." % (PATH, PATH))
print("Restart:  sudo systemctl restart cloudserver.service")
