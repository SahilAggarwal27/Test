#!/usr/bin/env python3
# Patch 3: make /slice carry candle High/Low so Cross Expiry works on the fast path.
#
# WHY
#   master_pq has only LTP (close). Cross Expiry needs intra-candle High/Low
#   (ce_h, ce_l, pe_h, pe_l) - it sells on a break below the low and the SL is the
#   high. Those columns live in kite_ohlc_data.csv, keyed by the SAME
#   instrument+datetime+strike+expiry. This patch LEFT JOINs that CSV onto the
#   existing Parquet query in query_slice() and adds the 4 columns to the slice
#   CSV output. Where OHLC exists -> H/L filled; where it doesn't -> blank (page
#   already falls back to LTP there, same as today).
#
# SAFETY
#   - Backs up cloud_server.py to cloud_server.py.bak_hl first.
#   - Aborts without writing if it can't find its exact anchors.
#   - Idempotent: does nothing if already applied.
#   - DuckDB reads the CSV directly; no data rebuild, no full load.
#
# USAGE (in /root/kite)
#   python3 patch_slice_hl.py
#   sudo systemctl restart cloudserver.service
#   # revert:  mv cloud_server.py.bak_hl cloud_server.py && sudo systemctl restart cloudserver.service

import io, os, sys, shutil

PATH = os.environ.get("CLOUD_SERVER", "cloud_server.py")
OHLC = os.environ.get("OHLC_CSV", "/root/kite/kite_ohlc_data.csv")

if not os.path.isfile(PATH):
    print("ABORT: %s not found. cd into /root/kite." % PATH); sys.exit(1)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "ce_h" in src and "query_slice" in src and "LEFT JOIN" in src:
    print("Already patched - nothing to do."); sys.exit(0)

# --- 1) The SELECT block inside query_slice (unique). Replace with a joined SELECT.
OLD_SELECT = (
'        f"""SELECT instrument, datetime, spot, strike, expiry, ce_ltp, pe_ltp\n'
"            FROM read_parquet('{PQ.as_posix()}/*/*.parquet', hive_partitioning=true)\n"
'            WHERE yr BETWEEN ? AND ?\n'
'              AND substr(datetime,1,10) BETWEEN ? AND ?""",'
)

NEW_SELECT = (
'        f"""SELECT p.instrument, p.datetime, p.spot, p.strike, p.expiry, p.ce_ltp, p.pe_ltp,\n'
"                  o.ce_h, o.ce_l, o.pe_h, o.pe_l\n"
"            FROM read_parquet('{PQ.as_posix()}/*/*.parquet', hive_partitioning=true) p\n"
"            LEFT JOIN read_csv_auto('%s', header=true) o\n"
"              ON o.instrument = p.instrument AND o.datetime = p.datetime\n"
"             AND o.strike = p.strike AND o.expiry = p.expiry\n"
'            WHERE p.yr BETWEEN ? AND ?\n'
'              AND substr(p.datetime,1,10) BETWEEN ? AND ?""",'
) % OHLC

# --- 2) The header row written to the slice CSV (unique). Add the 4 columns.
OLD_HDR = 'w.writerow(["instrument", "datetime", "spot", "strike", "expiry", "ce_ltp", "pe_ltp"])'
NEW_HDR = 'w.writerow(["instrument", "datetime", "spot", "strike", "expiry", "ce_ltp", "pe_ltp", "ce_h", "ce_l", "pe_h", "pe_l"])'

if src.count(OLD_SELECT) != 1:
    print("ABORT: query_slice SELECT block not found exactly once. No changes made."); sys.exit(1)
if src.count(OLD_HDR) != 1:
    print("ABORT: slice header row not found exactly once. No changes made."); sys.exit(1)

src = src.replace(OLD_SELECT, NEW_SELECT)
src = src.replace(OLD_HDR, NEW_HDR)

shutil.copyfile(PATH, PATH + ".bak_hl")
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("Patched %s (backup %s.bak_hl)." % (PATH, PATH))
print("Now restart the server:  sudo systemctl restart cloudserver.service")
print("Then reload the fast page and run Cross Expiry - trades should appear.")
