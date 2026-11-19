"""Sessiemappen in ~/BackingTrack, bestandslijsten en ZIP-export."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Optional

from . import library as lib
from .config import OUTPUT_DIR, PREVIEW_DIR

SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]+$")
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


def create_session_dir(base_name: str) -> Path:
    ensure_dirs()
    name, i = base_name, 2
    while (OUTPUT_DIR / name).exists():
        name = f"{base_name}_{i}"
        i += 1
    path = OUTPUT_DIR / name
    path.mkdir(parents=True)
    return path


def session_path(session_id: str) -> Path:
    if not SAFE_ID.match(session_id):
        raise FileNotFoundError("Ongeldige sessie")
    path = (OUTPUT_DIR / session_id).resolve()
    if path.parent != OUTPUT_DIR.resolve() or not path.is_dir():
        raise FileNotFoundError("Sessie niet gevonden")
    return path


def session_file(session_id: str, filename: str) -> Path:
    folder = session_path(session_id)
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise FileNotFoundError("Ongeldige bestandsnaam")
    path = (folder / filename).resolve()
    if path.parent != folder or not path.is_file():
        raise FileNotFoundError("Bestand niet gevonden")
    return path


def file_kind(p: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".mid":
        return "midi"
    if ext in AUDIO_EXT:
        return "audio"
    return "other"


def list_files(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.iterdir()):
        if p.name.startswith(".") or p.suffix.lower() == ".zip" or not p.is_file():
            continue
        m = re.match(r"^\d\d_([A-Za-z]+)", p.name)
        out.append({
            "name": p.name,
            "kind": file_kind(p),
            "instrument": m.group(1).lower() if m else None,
            "size": p.stat().st_size,
            "url": f"/api/sessions/{folder.name}/files/{p.name}",
        })
    return out


def save_session_json(folder: Path, data: dict) -> None:
    (folder / "session.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_session_json(session_id: str) -> Optional[dict]:
    p = session_path(session_id) / "session.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_sessions(limit: int = 50) -> list[dict]:
    ensure_dirs()
    sessions = []
    for d in OUTPUT_DIR.iterdir():
        if not d.is_dir() or d.name.startswith(".") or not (d / "session.json").exists():
            continue
        try:
            data = json.loads((d / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sessions.append({
            "id": d.name, "title": data.get("title", ""), "created": data.get("created", ""),
            "key": data.get("key"), "bpm": data.get("bpm"), "genre": data.get("genre"),
            "duration_seconds": data.get("duration_seconds"), "mix_url": data.get("mix_url"),
        })
    sessions.sort(key=lambda s: s["created"], reverse=True)
    return sessions[:limit]


def build_zip(session_id: str) -> Path:
    folder = session_path(session_id)
    zip_path = folder / f".{folder.name}.zip"
    files = [p for p in sorted(folder.iterdir()) if p.is_file() and not p.name.startswith(".")]
    newest = max((p.stat().st_mtime for p in files), default=0)
    if zip_path.exists() and zip_path.stat().st_mtime >= newest:
        return zip_path
    tmp = zip_path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        for p in files:
            compress = zipfile.ZIP_STORED if p.suffix.lower() in AUDIO_EXT else zipfile.ZIP_DEFLATED
            zf.write(p, arcname=f"{folder.name}/{p.name}", compress_type=compress)
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
