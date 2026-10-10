#!/bin/bash
# Auto-deploy backtester.html from the PRIVATE repo. No more public/private flips.
# Runs every 2 min via cron (installs itself). Applies all patch_*.py / fix_*.py.
# Only swaps the live file if every patch succeeds. Previous copy: backtester.html.prev
DIR=/root/kite
TOKEN=$(cat /root/.ghtoken 2>/dev/null)
[ -z "$TOKEN" ] && { echo "no token in /root/.ghtoken"; exit 1; }
API=https://api.github.com/repos/SahilAggarwal27/Test
H1="Authorization: Bearer $TOKEN"

# self-install cron
if ! crontab -l 2>/dev/null | grep -q "kite/update.sh"; then
  (crontab -l 2>/dev/null; echo "*/2 * * * * bash $DIR/update.sh >> $DIR/update.log 2>&1") | crontab -
  echo "cron installed"
fi

SHA=$(curl -sf -H "$H1" "$API/commits/main" | python3 -c "import sys,json;print(json.load(sys.stdin)['sha'])") || { echo "$(date) github unreachable/bad token"; exit 1; }
[ "$SHA" = "$(cat $DIR/.deployed_sha 2>/dev/null)" ] && exit 0

TMP=$(mktemp -d)
get(){ curl -sf -H "$H1" -H "Accept: application/vnd.github.raw" "$API/contents/$1?ref=$SHA" -o "$TMP/$1"; }

get backtester.html || { echo "$(date) fetch failed"; rm -rf "$TMP"; exit 1; }
FILES=$(curl -sf -H "$H1" "$API/contents?ref=$SHA" | python3 -c "import sys,json;print(' '.join(sorted(x['name'] for x in json.load(sys.stdin) if x['name'].endswith('.py') and x['name'].startswith(('patch_','fix_')))))")
for f in $FILES; do
  get "$f" || { echo "$(date) fetch $f failed"; rm -rf "$TMP"; exit 1; }
  (cd "$TMP" && BT_HTML="$TMP/backtester.html" python3 "$f") || { echo "$(date) $f FAILED - live file untouched"; rm -rf "$TMP"; exit 1; }
done

[ "$(stat -c%s "$TMP/backtester.html")" -gt 50000 ] || { echo "$(date) file too small, abort"; rm -rf "$TMP"; exit 1; }
cp "$DIR/backtester.html" "$DIR/backtester.html.prev" 2>/dev/null
cp "$TMP/backtester.html" "$DIR/backtester.html"
get update.sh && cp "$TMP/update.sh" "$DIR/update.sh"   # self-update
echo "$SHA" > "$DIR/.deployed_sha"
echo "$(date) deployed ${SHA:0:7} (patches: $FILES)"
rm -rf "$TMP"
