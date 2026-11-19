"""Sessiemappen in ~/BackingTrack, bestandslijsten en ZIP-export."""
from __future__ import annotations

import json
import os
import shutil
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from typing import Optional

from . import library as lib
from .config import OUTPUT_DIR, PREVIEW_DIR

AUDIO_EXT = {".wav", ".aiff", ".aif", ".m4a"}
MEDIA_TYPES = {
    ".wav": "audio/wav", ".aiff": "audio/aiff", ".aif": "audio/aiff", ".m4a": "audio/mp4",
    ".mid": "audio/midi", ".txt": "text/plain; charset=utf-8", ".json": "application/json",
    ".zip": "application/zip",
}


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def camel(text: str, max_len: int = 24) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()   # é → e
    words = re.findall(r"[A-Za-z0-9]+", text.replace("'", ""))
    out = "".join(w[:1].upper() + w[1:] for w in words)
    return out[:max_len]


def folder_name(genre: str, key_tag: str, title: str, mood: str, bpm: int, seconds: float) -> str:
    gtag = lib.GENRES.get(genre, {}).get("tag", camel(genre))
    if title:
        song = title.split(" - ", 1)[1] if " - " in title else title
        ref = camel(song) or lib.MOODS.get(mood, {}).get("tag", "Track")
    else:
        ref = lib.MOODS.get(mood, {}).get("tag", "Track")
    minutes = max(1, int(round(seconds / 60.0)))
    return f"{gtag}_{camel(key_tag, 6)}_{ref}_{bpm}BPM_{minutes}m"


def song_folder_name(name: str, key_tag: str, bpm: int, seconds: float) -> str:
    """Mapnaam voor een nummer met een eigen naam, bv. Zomeravond_Em_118BPM_4m."""
    minutes = max(1, int(round(seconds / 60.0)))
    return f"{camel(name, 40) or 'Nummer'}_{camel(key_tag, 6)}_{bpm}BPM_{minutes}m"


def create_session_dir(base_name: str) -> Path:
    ensure_dirs()
    name, i = base_name, 2
    while (OUTPUT_DIR / name).exists():
        name = f"{base_name}_{i}"
        i += 1
    path = OUTPUT_DIR / name
    path.mkdir(parents=True)
    return path


SUBDIRS = ("Audio", "MIDI")                        # submappen van de HTML-app (BackingTrack Studio)
STUDIO_README = "Lees mij - Logic Pro.txt"


def _url_id(session_id: str) -> str:
    return quote(session_id, safe="")


def session_path(session_id: str) -> Path:
    if not session_id or "/" in session_id or "\\" in session_id or session_id.startswith("."):
        raise FileNotFoundError("Ongeldige sessie")
    path = (OUTPUT_DIR / session_id).resolve()
    if path.parent != OUTPUT_DIR.resolve() or not path.is_dir():
        raise FileNotFoundError("Sessie niet gevonden")
    return path


def session_file(session_id: str, filename: str) -> Path:
    """Bestand in de sessiemap, of in Audio/ of MIDI/ (HTML-app). Nooit daarbuiten."""
    folder = session_path(session_id)
    parts = filename.replace("\\", "/").split("/")
    if len(parts) > 2 or any(not x or x.startswith(".") for x in parts) or (len(parts) == 2 and parts[0] not in SUBDIRS):
        raise FileNotFoundError("Ongeldige bestandsnaam")
    path = (folder / filename).resolve()
    if folder not in path.parents or not path.is_file():
        raise FileNotFoundError("Bestand niet gevonden")
    return path


def file_kind(p: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".mid":
        return "midi"
    if ext in AUDIO_EXT:
        return "audio"
    return "other"


def _session_files(folder: Path) -> list[tuple[str, Path]]:
    out = []
    for p in sorted(folder.iterdir()):
        if p.name.startswith(".") or p.suffix.lower() == ".zip":
            continue
        if p.is_file():
            out.append((p.name, p))
        elif p.is_dir() and p.name in SUBDIRS:
            out += [(f"{p.name}/{q.name}", q) for q in sorted(p.iterdir()) if q.is_file() and not q.name.startswith(".")]
    return out


def list_files(folder: Path) -> list[dict]:
    out = []
    for rel, p in _session_files(folder):
        m = re.match(r"^(\d\d)[_ ]([A-Za-z\-]+)", p.name)
        out.append({
            "name": rel,
            "kind": file_kind(p),
            "instrument": m.group(2).lower() if m else None,
            "size": p.stat().st_size,
            "url": f"/api/sessions/{_url_id(folder.name)}/files/{quote(rel)}",
        })
    return out


def save_session_json(folder: Path, data: dict) -> None:
    (folder / "session.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Tracks van de HTML-app (BackingTrack Studio) inlezen via hun "Lees mij"-bestand
# --------------------------------------------------------------------------- #
def _readme_fields(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-zÀ-ÿ\- ]{3,14}):\s{1,}(.+)$", line)
        if m and line[:1] != " ":
            fields.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return fields


def _bars_to_chords(line: str) -> list[str]:
    chords: list[str] = []
    for bar in line.split("|"):
        for c in bar.strip().split("-"):
            c = c.strip()
            if c and (not chords or chords[-1] != c):
                chords.append(c)
    return chords


def _studio_session(folder: Path) -> Optional[dict]:
    readme = folder / STUDIO_README
    if not readme.is_file():
        return None
    f = _readme_fields(readme.read_text(encoding="utf-8", errors="replace"))
    verse = _bars_to_chords(f.get("couplet") or f.get("schema", "").split("(")[0])
    chorus = _bars_to_chords(f["refrein"]) if "refrein" in f else verse
    bridge = _bars_to_chords(f["bridge"]) if "bridge" in f else []
    bpm_m = re.search(r"(\d+)\s*BPM", f.get("tempo", ""))
    dur_m = re.search(r"(\d+):(\d+)\s*\((\d+)\s*maten", f.get("duur", ""))
    sections, bar = [], 0
    for label, n in re.findall(r"([^·(]+?)\s*\((\d+)\)", f.get("opbouw", "")):
        label, n = label.strip(), int(n)
        low = label.lower()
        kind = ("intro" if low.startswith("intro") else "chorus" if low.startswith("refrein") else
                "bridge" if low.startswith("bridge") else "solo" if low.startswith("solo") else
                "outro" if low.startswith("outro") else "verse")
        chords = bridge if kind == "bridge" else chorus if kind in ("chorus", "outro") else verse
        sections.append({"name": kind, "label": label, "start_bar": bar, "bars": n,
                         "energy": 1.0 if kind == "chorus" else 0.7, "chords": chords[:16]})
        bar += n
    if not sections and verse:
        sections = [{"name": "verse", "label": "Akkoordenschema", "start_bar": 0, "bars": len(verse),
                     "energy": 0.8, "chords": verse[:16]}]
    created = datetime.fromtimestamp(readme.stat().st_mtime).isoformat(timespec="seconds")
    sid = _url_id(folder.name)
    return {
        "id": folder.name, "folder": folder.name, "path": str(folder), "created": created,
        "source": "studio",
        "title": f.get("inspiratie", "").split(" (")[0] or f.get("backingtrack", folder.name),
        "genre": f.get("genre", ""), "mood": f.get("sfeer", ""), "key": f.get("toonsoort", ""),
        "bpm": int(bpm_m.group(1)) if bpm_m else 0,
        "bars": int(dur_m.group(3)) if dur_m else bar,
        "duration_seconds": int(dur_m.group(1)) * 60 + int(dur_m.group(2)) if dur_m else 0,
        "seed": None, "sections": sections, "mix_url": None,
        "zip_url": f"/api/sessions/{sid}/zip", "warnings": [],
        "progressions": {"verse": f.get("couplet", ""), "chorus": f.get("refrein", ""), "bridge": f.get("bridge", "")},
    }


def load_session(session_id: str) -> Optional[dict]:
    """Sessie van de server (session.json) of track van de HTML-app (Lees mij-bestand)."""
    folder = session_path(session_id)
    p = folder / "session.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("source", "server")
    else:
        data = _studio_session(folder)
        if data is None:
            return None
    data["files"] = list_files(folder)
    return data


def load_session_json(session_id: str) -> Optional[dict]:
    return load_session(session_id)


def list_sessions(limit: int = 1000) -> list[dict]:
    ensure_dirs()
    sessions = []
    for d in OUTPUT_DIR.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        try:
            if (d / "session.json").exists():
                data = json.loads((d / "session.json").read_text(encoding="utf-8"))
                data.setdefault("source", "server")
            else:
                data = _studio_session(d)
                if data is None:
                    continue
        except (OSError, ValueError):
            continue
        sessions.append({
            "id": d.name, "title": data.get("title", ""), "created": data.get("created", ""),
            "key": data.get("key"), "bpm": data.get("bpm"), "genre": data.get("genre"),
            "duration_seconds": data.get("duration_seconds"), "mix_url": data.get("mix_url"),
            "source": data.get("source"),
        })
    sessions.sort(key=lambda s: s["created"], reverse=True)
    return sessions[:limit]


def build_zip(session_id: str) -> Path:
    folder = session_path(session_id)
    zip_path = folder / f".{folder.name}.zip"
    files = _session_files(folder)
    newest = max((p.stat().st_mtime for _, p in files), default=0)
    if zip_path.exists() and zip_path.stat().st_mtime >= newest:
        return zip_path
    tmp = zip_path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        for rel, p in files:
            compress = zipfile.ZIP_STORED if p.suffix.lower() in AUDIO_EXT else zipfile.ZIP_DEFLATED
            zf.write(p, arcname=f"{folder.name}/{rel}", compress_type=compress)
    tmp.replace(zip_path)
    return zip_path


def cleanup_previews(keep: int = 6) -> None:
    ensure_dirs()
    files = sorted(PREVIEW_DIR.glob("preview_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep * 2:]:
        try:
            p.unlink()
        except OSError:
            pass


def _trash_dir(path: Path) -> Path:
    """Prullenmand van het volume waar de map op staat (externe schijf: /Volumes/X/.Trashes/<uid>)."""
    parts = path.resolve().parts
    if len(parts) > 2 and parts[1] == "Volumes":
        return Path("/", "Volumes", parts[2], ".Trashes", str(os.getuid()))
    return Path.home() / ".Trash"


def delete_session(session_id: str) -> dict:
    """Verwijdert een nummer (map + alle bestanden). Eerst naar de Prullenmand; lukt dat niet, dan definitief."""
    folder = session_path(session_id)              # controleert dat de map echt in de tracksmap ligt
    if folder.resolve() == OUTPUT_DIR.resolve():
        raise FileNotFoundError("Ongeldige sessie")
    try:
        trash = _trash_dir(folder)
        trash.mkdir(parents=True, exist_ok=True)
        target = trash / folder.name
        if target.exists():
            target = trash / f"{folder.name} {datetime.now().strftime('%H.%M.%S')}"
        os.rename(folder, target)                  # zelfde volume: direct, zonder kopiëren
        return {"deleted": session_id, "trash": True}
    except OSError:
        shutil.rmtree(folder)
        return {"deleted": session_id, "trash": False}
