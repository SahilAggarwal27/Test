#!/bin/bash
# Auto-deploy backtester.html from GitHub (no API calls -> no rate limits).
# Cron every 2 min (self-installs). Applies patch_backtester.py + all fix_*.py.
# Live file only replaced if every patch succeeds. Previous copy: backtester.html.prev
DIR=/root/kite
REPO=https://github.com/SahilAggarwal27/Test

if ! crontab -l 2>/dev/null | grep -q "kite/update.sh"; then
  (crontab -l 2>/dev/null; echo "*/2 * * * * bash $DIR/update.sh >> $DIR/update.log 2>&1") | crontab -
  echo "cron installed"
fi

SHA=$(git ls-remote "$REPO" refs/heads/main 2>/dev/null | cut -f1)
[ -z "$SHA" ] && { echo "$(date) github unreachable"; exit 1; }
[ "$SHA" = "$(cat $DIR/.deployed_sha 2>/dev/null)" ] && exit 0

TMP=$(mktemp -d)
curl -sfL "https://codeload.github.com/SahilAggarwal27/Test/tar.gz/$SHA" | tar -xz -C "$TMP" || { echo "$(date) download failed"; rm -rf "$TMP"; exit 1; }
SRC=$(ls -d "$TMP"/*/ | head -1)
cd "$SRC" || exit 1
FILES=$(ls fix_*.py 2>/dev/null; [ -f patch_backtester.py ] && echo patch_backtester.py)
for f in $FILES; do
  BT_HTML="$SRC/backtester.html" python3 "$f" || { echo "$(date) $f FAILED - live file untouched"; rm -rf "$TMP"; exit 1; }
done
[ "$(stat -c%s backtester.html)" -gt 50000 ] || { echo "$(date) file too small"; rm -rf "$TMP"; exit 1; }
cp "$DIR/backtester.html" "$DIR/backtester.html.prev" 2>/dev/null
cp backtester.html "$DIR/backtester.html"
cp update.sh "$DIR/update.sh"
echo "$SHA" > "$DIR/.deployed_sha"
echo "$(date) deployed ${SHA:0:7} ($(echo $FILES))"
rm -rf "$TMP"
