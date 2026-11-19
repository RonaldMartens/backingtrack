"""FastAPI-server: REST API + webinterface.

Start:  uvicorn app.main:app --host 0.0.0.0 --port 8000
API-documentatie (handig voor de iOS-app): http://localhost:8000/docs
"""
from __future__ import annotations

import os
import re
import subprocess

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import library as lib
from . import lifecycle, storage
from .analyzer import analyze_reference
from .guitar import chord_sheet
from .config import OUTPUT_DIR, PREVIEW_DIR, STATIC_DIR, find_afconvert, find_fluidsynth, find_soundfont
from .engine import add_solos, generate_preview, generate_session, remove_solos
from pydantic import BaseModel, Field

from .models import AnalyzeRequest, AnalyzeResponse, GenerateRequest, PreviewResult, SessionResult, SoloRequest
from .theory import key_options

app = FastAPI(title="BackingTrack Generator", version="1.0.0",
              description="Backingtrack-generator voor Logic Pro: MIDI + WAV/AIFF-stems per instrument.")

origins = [o.strip() for o in os.environ.get("BACKINGTRACK_CORS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    """Altijd de nieuwste versie van de webinterface tonen (geen verouderde pagina uit de browsercache)."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/sessions/") and not request.url.path.startswith("/api/preview/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.on_event("startup")
def _startup() -> None:
    storage.ensure_dirs()
    lifecycle.start_watchdog()


# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    sf2 = find_soundfont()
    return {
        "status": "ok",
        "fluidsynth": find_fluidsynth(),
        "soundfont": str(sf2) if sf2 else None,
        "afconvert": find_afconvert(),
        "output_dir": str(OUTPUT_DIR),
        "claude_env_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        **lifecycle.status(),
    }


@app.get("/api/options")
def options() -> dict:
    return {
        "moods": lib.mood_options(),
        "genres": lib.genre_options(),
        "keys": key_options(),
        "progressions": lib.progression_options(),
        "instruments": [{"id": i["id"], "label": i["label"]} for i in lib.INSTRUMENTS],
        "references": lib.reference_titles(),
        "limits": {"bpm": [50, 180], "duration_seconds": [60, 600]},
    }


@app.post("/api/analyze-reference", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    return analyze_reference(req.reference, req.api_key, req.use_claude)


class GuitarChordsRequest(BaseModel):
    chords: list[str] = Field(min_length=1, max_length=64)
    key: str = "C"


@app.post("/api/guitar-chords")
def guitar_chords(req: GuitarChordsRequest) -> dict:
    """Gitaargrepen (4 posities per akkoord) voor de akkoorden van een track."""
    return {"chords": chord_sheet([c.strip() for c in req.chords if c.strip()], req.key)}


@app.post("/api/generate", response_model=SessionResult)
def generate(req: GenerateRequest) -> SessionResult:
    try:
        with lifecycle.busy():
            return generate_session(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/preview", response_model=PreviewResult)
def preview(req: GenerateRequest) -> PreviewResult:
    try:
        with lifecycle.busy():
            return generate_preview(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/preview/files/{name}")
def preview_file(name: str) -> FileResponse:
    if not re.match(r"^preview_[a-f0-9]{10}\.(wav|m4a)$", name):
        raise HTTPException(404, "Niet gevonden")
    path = PREVIEW_DIR / name
    if not path.exists():
        raise HTTPException(404, "Niet gevonden")
    return FileResponse(path, media_type=storage.MEDIA_TYPES[path.suffix])


@app.get("/api/preview/{session_id}")
def session_preview(session_id: str) -> FileResponse:
    """Volledige mix van een sessie (m4a als beschikbaar, anders wav)."""
    for name in ("00_Mix.m4a", "00_Mix.wav"):
        try:
            path = storage.session_file(session_id, name)
            return FileResponse(path, media_type=storage.MEDIA_TYPES[path.suffix])
        except FileNotFoundError:
            continue
    raise HTTPException(404, "Geen mix gevonden voor deze sessie")


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@app.post("/api/shutdown")
def shutdown(request: Request) -> dict:
    """Stopt de server netjes. Alleen toegestaan vanaf de Mac zelf (niet vanaf iPhone/netwerk)."""
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS and not os.environ.get("BACKINGTRACK_ALLOW_REMOTE_SHUTDOWN"):
        raise HTTPException(403, "Stoppen kan alleen vanaf de Mac waarop BackingTrack draait.")
    lifecycle.request_shutdown()   # eerst het antwoord versturen, daarna netjes stoppen
    return {"status": "stopping"}


@app.post("/api/heartbeat")
def heartbeat(client: str) -> dict:
    """Een geopende pagina meldt zich (elke 15 s). Zonder pagina's stopt de server vanzelf."""
    lifecycle.heartbeat(client)
    return lifecycle.status()


@app.post("/api/bye")
def bye(client: str) -> dict:
    """Pagina wordt gesloten (sendBeacon)."""
    lifecycle.bye(client)
    return {"ok": True}


@app.get("/api/sessions")
def sessions() -> list[dict]:
    return storage.list_sessions()


@app.get("/api/sessions/{session_id}")
def session(session_id: str) -> dict:
    """Een eerder gemaakt nummer openen (van de server óf van de HTML-app)."""
    try:
        data = storage.load_session(session_id)
    except FileNotFoundError:
        data = None
    if not data:
        raise HTTPException(404, "Sessie niet gevonden")
    return data


@app.post("/api/sessions/{session_id}/reveal")
def session_reveal(session_id: str, request: Request) -> dict:
    """Toon de map van het nummer in Finder (alleen vanaf de Mac zelf)."""
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise HTTPException(403, "Finder openen kan alleen op de Mac waarop BackingTrack draait.")
    try:
        path = storage.session_path(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Sessie niet gevonden")
    subprocess.Popen(["open", str(path)])
    return {"ok": True, "path": str(path)}


@app.get("/api/sessions/{session_id}/files/{filename:path}")
def session_file(session_id: str, filename: str) -> FileResponse:
    try:
        path = storage.session_file(session_id, filename)
    except FileNotFoundError:
        raise HTTPException(404, "Bestand niet gevonden")
    media = storage.MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=path.name if path.suffix == ".mid" else None)


@app.post("/api/sessions/{session_id}/solos")
def session_solos(session_id: str, req: SoloRequest) -> dict:
    """Gitaarsolo's toevoegen (of opnieuw maken) over de gekozen delen van een bestaand nummer."""
    try:
        with lifecycle.busy():
            return add_solos(session_id, req)
    except FileNotFoundError:
        raise HTTPException(404, "Sessie niet gevonden")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/sessions/{session_id}/solos")
def session_solos_delete(session_id: str) -> dict:
    try:
        return remove_solos(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Sessie niet gevonden")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/sessions/{session_id}/zip")
def session_zip(session_id: str) -> FileResponse:
    try:
        path = storage.build_zip(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Sessie niet gevonden")
    return FileResponse(path, media_type="application/zip", filename=f"{session_id}.zip")


# Webinterface (als laatste, zodat /api voorrang heeft)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
