#!/usr/bin/env bash
# Backtester daily heartbeat + dead-man's switch.
# - Telegram: pings you every day so SILENCE = something is wrong.
# - healthchecks.io: alerts you if this script itself never runs (droplet down / cron dead).
#
# Setup: fill DATA + HC_URL below; put TG_BOT / TG_CHAT in the crontab line.
set -uo pipefail

# ------------------------- CONFIG -------------------------
: "${TG_BOT:?export TG_BOT (Telegram bot token)}"
: "${TG_CHAT:?export TG_CHAT (Telegram chat id)}"
HC_URL="https://hc-ping.com/<YOUR-HC-UUID>"        # healthchecks.io ping URL
DATA="/root/bt/data/kite_ohlc_data.csv"            # main options data file (edit to real path)
STALE_HELP="Check the Kite collector on the droplet."
# ----------------------------------------------------------

tg(){ curl -s -m 10 "https://api.telegram.org/bot${TG_BOT}/sendMessage" \
        -d chat_id="${TG_CHAT}" --data-urlencode text="$1" >/dev/null 2>&1; }

today=$(TZ=Asia/Kolkata date +%F)

if [ -r "$DATA" ]; then
  # locate the datetime column from the header (don't hardcode its position)
  dtcol=$(head -1 "$DATA" | tr ',' '\n' | grep -nxi "datetime" | head -1 | cut -d: -f1)
  [ -z "$dtcol" ] && dtcol=2
  # read only the tail so we never load the whole (huge) file
  last=$(tail -c 3000000 "$DATA" | awk -F, -v c="$dtcol" 'NF>=c{d=substr($c,1,10)} END{print d}')
else
  last="FILE-MISSING"
fi

if [ "$last" = "$today" ]; then
  tg "✅ Backtester OK — ${today} IST
Data last row: ${last}"
  curl -fsS -m 10 "$HC_URL" >/dev/null 2>&1 || true          # success ping
else
  tg "⚠️ Backtester — DATA NOT FRESH (${today} IST)
Data last row: ${last:-EMPTY}
${STALE_HELP}"
  curl -fsS -m 10 "${HC_URL}/fail" >/dev/null 2>&1 || true    # tell healthchecks it failed
fi
