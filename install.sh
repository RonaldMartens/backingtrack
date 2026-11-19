#!/bin/bash
# Eenmalige installatie op macOS: FluidSynth, SoundFont en Python-omgeving.
set -euo pipefail
cd "$(dirname "$0")"

VENV="$HOME/.venvs/backingtrack"          # bewust buiten OneDrive (OneDrive breekt symlinks in venvs)
SF_DIR="$HOME/Library/Audio/Sounds/Banks"
SF_FILE="$SF_DIR/GeneralUser-GS.sf2"
SF_URL="https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew ontbreekt. Installeer eerst via https://brew.sh en draai dit script opnieuw."
  exit 1
fi

echo "==> FluidSynth installeren/bijwerken"
brew list fluid-synth >/dev/null 2>&1 || brew install fluid-synth

echo "==> Python controleren"
PY="$(brew --prefix)/bin/python3"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  brew install python@3.12
  PY="$(brew --prefix)/bin/python3.12"
fi
echo "    $("$PY" --version)"

echo "==> Virtuele omgeving in $VENV"
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements.txt

echo "==> SoundFont (GeneralUser GS, ~30 MB)"
mkdir -p "$SF_DIR"
if [ ! -s "$SF_FILE" ]; then
  curl -L --fail -o "$SF_FILE" "$SF_URL"
fi
ls -lh "$SF_FILE"

mkdir -p "$HOME/Music/BackingTrack"
echo
echo "Klaar! Start de app met:  ./start.sh"
