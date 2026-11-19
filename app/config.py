"""Centrale configuratie: paden, externe tools en constanten."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_DIR / "static"

# Uitvoermap voor alle sessies (overschrijfbaar via env var)
OUTPUT_DIR = Path(os.environ.get("BACKINGTRACK_OUTPUT", str(Path.home() / "BackingTrack"))).expanduser()
PREVIEW_DIR = OUTPUT_DIR / ".previews"

TICKS_PER_BEAT = 480
SAMPLE_RATE = 44100
CLAUDE_MODEL = "claude-opus-5-5"

SOUNDFONT_SEARCH_DIRS = [
    PROJECT_DIR / "soundfonts",
    Path.home() / "Library" / "Audio" / "Sounds" / "Banks",
    Path("/opt/homebrew/share/soundfonts"),
    Path("/usr/local/share/soundfonts"),
    Path("/usr/share/sounds/sf2"),
]
# Voorkeursvolgorde als er meerdere SoundFonts gevonden worden
SOUNDFONT_PREFERENCE = ["generaluser", "musescore_general", "fluidr3", "timgm"]


def find_fluidsynth() -> str | None:
    env = os.environ.get("FLUIDSYNTH_BIN")
    if env and Path(env).exists():
        return env
    found = shutil.which("fluidsynth")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/fluidsynth", "/usr/local/bin/fluidsynth"):
        if Path(candidate).exists():
            return candidate
    return None


def find_soundfont() -> Path | None:
    env = os.environ.get("BACKINGTRACK_SOUNDFONT")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser()
    candidates: list[Path] = []
    for d in SOUNDFONT_SEARCH_DIRS:
        if d.is_dir():
            candidates += sorted(d.glob("*.sf2")) + sorted(d.glob("*.sf3"))
    if not candidates:
        return None

    def rank(p: Path) -> int:
        name = p.name.lower().replace("-", "").replace(" ", "")
        for i, pref in enumerate(SOUNDFONT_PREFERENCE):
            if pref.replace("_", "") in name.replace("_", ""):
                return i
        return len(SOUNDFONT_PREFERENCE)

    return sorted(candidates, key=rank)[0]


def find_afconvert() -> str | None:
    return shutil.which("afconvert")
