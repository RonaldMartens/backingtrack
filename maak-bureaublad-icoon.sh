#!/bin/bash
# Maakt eenmalig "BackingTrack.app" op je bureaublad: dubbelklikken start de server op de
# achtergrond (zonder Terminal-venster) en opent de app in je browser. Draait hij al, dan
# kun je kiezen tussen Openen en Stoppen.
#
# Het icoon is een echte (ondertekende) macOS-applet. Daardoor kan macOS het toestemming
# geven voor bestanden op een externe schijf: bij de eerste start vraagt macOS
# "BackingTrack wil toegang tot bestanden op een verwijderbaar volume" → kies OK.
#
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
PB=/usr/libexec/PlistBuddy

# --- 1. Applet bouwen: roept het startscript in de app-bundel aan ----------------------
rm -rf "$DEST"
osacompile -o "$DEST" \
  -e 'set launcher to POSIX path of (path to resource "launcher.sh")' \
  -e 'try' \
  -e '  do shell script "/bin/bash " & quoted form of launcher' \
  -e 'end try'

# --- 2. Startscript ---------------------------------------------------------------------
L="$DEST/Contents/Resources/launcher.sh"
cat > "$L" <<LAUNCHER
#!/bin/bash
REPO="$REPO"
OUT="$OUT"
LAUNCHER
cat >> "$L" <<'LAUNCHER'
PORT=8000
URL="http://localhost:$PORT"
LOG="$HOME/Library/Logs/BackingTrack.log"
VENV="$HOME/.venvs/backingtrack"
mkdir -p "$HOME/Library/Logs"
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
# Mag deze app de bestanden op de (externe) schijf lezen? Zo niet: uitleg + instellingen openen.
if ! head -c 1 "$REPO/start.sh" >/dev/null 2>&1; then
  echo "=== $(date) geen toegang tot $REPO (privacy-instellingen)" >> "$LOG"
  melding "BackingTrack heeft nog geen toegang tot je externe schijf.\n\nZet in het venster dat nu opent bij BackingTrack 'Verwijderbare volumes' aan (Bestanden en mappen), of voeg BackingTrack toe bij 'Volledige schijftoegang'.\n\nDubbelklik daarna opnieuw op het icoon."
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders"
  exit 1
fi
if [ ! -x "$VENV/bin/uvicorn" ]; then
  melding "BackingTrack is nog niet geïnstalleerd.\nVoer eerst ./install.sh uit in:\n$REPO"; exit 1
fi
mkdir -p "$OUT" 2>/dev/null
cd "$REPO" || exit 1
echo "=== $(date) start (tracks: $OUT)" >> "$LOG"
BACKINGTRACK_OUTPUT="$OUT" BT_NO_BROWSER=1 nohup /bin/bash ./start.sh >> "$LOG" 2>&1 < /dev/null &
for i in $(seq 1 60); do
  if draait; then browser; exit 0; fi
  sleep 0.5
done
melding "BackingTrack startte niet binnen 30 seconden.\nDetails staan in:\n$LOG"
open -a Console "$LOG" 2>/dev/null
exit 1
LAUNCHER
chmod +x "$L"

# --- 3. Naam, identiteit en icoon -------------------------------------------------------
P="$DEST/Contents/Info.plist"
$PB -c "Set :CFBundleName BackingTrack" "$P" 2>/dev/null || $PB -c "Add :CFBundleName string BackingTrack" "$P"
$PB -c "Add :CFBundleDisplayName string BackingTrack" "$P" 2>/dev/null || $PB -c "Set :CFBundleDisplayName BackingTrack" "$P"
$PB -c "Add :CFBundleIdentifier string local.backingtrack.launcher" "$P" 2>/dev/null || $PB -c "Set :CFBundleIdentifier local.backingtrack.launcher" "$P"
$PB -c "Add :NSRemovableVolumesUsageDescription string BackingTrack start de server en bewaart tracks op je externe schijf." "$P" 2>/dev/null || true
$PB -c "Delete :CFBundleIconName" "$P" 2>/dev/null || true      # anders wint het standaard-applet-icoon
rm -f "$DEST/Contents/Resources/Assets.car"
cp "$REPO/assets/BackingTrack.icns" "$DEST/Contents/Resources/applet.icns"
$PB -c "Set :CFBundleIconFile applet" "$P" 2>/dev/null || $PB -c "Add :CFBundleIconFile string applet" "$P"

# --- 4. Opnieuw (ad-hoc) ondertekenen, zodat macOS de app herkent ---------------------
xattr -cr "$DEST" 2>/dev/null || true
codesign --force --deep --sign - "$DEST"
touch "$DEST"

echo "Klaar: $DEST"
echo "  code:   $REPO"
echo "  tracks: $OUT"
echo "Dubbelklik op het icoon om te starten. Vraagt macOS om toegang tot een verwijderbaar volume: kies OK."
