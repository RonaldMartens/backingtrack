#!/bin/bash
# Maakt eenmalig "BackingTrack.app" op je bureaublad: dubbelklikken start de server op de
# achtergrond (zonder Terminal-venster) en opent de app in je browser. Draait hij al, dan
# kun je kiezen tussen Openen en Stoppen.
#   Gebruik:  ./maak-bureaublad-icoon.sh            (tracks naar "<schijf>/BackingTrack Tracks" of ~/Music/BackingTrack)
#             ./maak-bureaublad-icoon.sh "/pad/naar/tracks"
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
if [[ "$REPO" == /Volumes/* ]]; then
  VOL="$(echo "$REPO" | cut -d/ -f1-3)"            # bv. /Volumes/Externe_schijf
  DEFAULT_OUT="$VOL/BackingTrack Tracks"
else
  DEFAULT_OUT="$HOME/Music/BackingTrack"
fi
OUT="${1:-$DEFAULT_OUT}"
DEST="${BT_APP_DEST:-$HOME/Desktop}/BackingTrack.app"

rm -rf "$DEST"
mkdir -p "$DEST/Contents/MacOS" "$DEST/Contents/Resources"
cp "$REPO/assets/BackingTrack.icns" "$DEST/Contents/Resources/BackingTrack.icns"

cat > "$DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>BackingTrack</string>
  <key>CFBundleDisplayName</key><string>BackingTrack</string>
  <key>CFBundleIdentifier</key><string>local.backingtrack.launcher</string>
  <key>CFBundleExecutable</key><string>BackingTrack</string>
  <key>CFBundleIconFile</key><string>BackingTrack</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST

cat > "$DEST/Contents/MacOS/BackingTrack" <<LAUNCHER
#!/bin/bash
REPO="$REPO"
OUT="$OUT"
LAUNCHER
cat >> "$DEST/Contents/MacOS/BackingTrack" <<'LAUNCHER'
PORT=8000
URL="http://localhost:$PORT"
LOG="$HOME/Library/Logs/BackingTrack.log"
VENV="$HOME/.venvs/backingtrack"
melding(){ osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with title \"BackingTrack\" with icon caution" >/dev/null 2>&1; }
draait(){ [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$URL/api/health")" = "200" ]; }
browser(){ [ -z "${BT_NO_BROWSER:-}" ] && open "$URL"; return 0; }

if draait; then
  keuze=$(osascript -e 'button returned of (display dialog "BackingTrack draait al." buttons {"Stoppen", "Openen"} default button "Openen" with title "BackingTrack")' 2>/dev/null)
  if [ "$keuze" = "Stoppen" ]; then curl -s -m 5 -X POST "$URL/api/shutdown" >/dev/null; else browser; fi
  exit 0
fi
if [ ! -d "$REPO" ]; then
  melding "De BackingTrack-map is niet gevonden:\n$REPO\n\nIs de externe schijf aangesloten?"; exit 1
fi
if [ ! -x "$VENV/bin/uvicorn" ]; then
  melding "BackingTrack is nog niet geïnstalleerd.\nVoer eerst ./install.sh uit in:\n$REPO"; exit 1
fi
mkdir -p "$OUT" 2>/dev/null
cd "$REPO" || exit 1
echo "=== $(date) start (tracks: $OUT)" >> "$LOG"
BACKINGTRACK_OUTPUT="$OUT" BT_NO_BROWSER=1 nohup ./start.sh >> "$LOG" 2>&1 &
for i in $(seq 1 60); do
  if draait; then browser; exit 0; fi
  sleep 0.5
done
melding "BackingTrack startte niet binnen 30 seconden.\nDetails staan in:\n$LOG"
open -a Console "$LOG" 2>/dev/null
exit 1
LAUNCHER
chmod +x "$DEST/Contents/MacOS/BackingTrack"
touch "$DEST"   # Finder het nieuwe icoon laten tonen

echo "Klaar: $DEST"
echo "  code:   $REPO"
echo "  tracks: $OUT"
echo "Dubbelklik op het icoon om te starten. Tip: sleep het ook naar je Dock."
