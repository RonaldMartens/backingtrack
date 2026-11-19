"""Orkestratie: instellingen -> arrangement -> MIDI -> audio -> sessiemap."""
from __future__ import annotations

import random
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from . import library as lib
from . import renderer, storage
from .arranger import Arrangement, build_arrangement, build_preview_arrangement, chord_chart, resolve_plan
from .config import PREVIEW_DIR, find_afconvert, find_fluidsynth, find_soundfont
from .generators import TrackData, generate_tracks
from .midi_writer import write_full, write_stem
from .models import FileInfo, GenerateRequest, PreviewResult, SessionResult, SoloRequest
from .solo import TONES, auto_style, auto_tone, solo_track

INSTRUMENT_META = {i["id"]: i for i in lib.INSTRUMENTS}
TAIL_SECONDS = 3.5   # galmstaart na een strak slotakkoord


def _selected(req: GenerateRequest) -> list[str]:
    sel = [k for k, v in req.instruments.model_dump().items() if v]
    if not sel:
        raise ValueError("Kies minimaal één instrument.")
    return sel


def _timing(arr: Arrangement, fade: bool) -> tuple[float, Optional[float], Optional[float]]:
    """(totale lengte in s, fade-start in s, fade-einde in s)."""
    spb = arr.seconds_per_beat
    end = arr.total_beats * spb
    if fade and arr.fade_start_bar is not None:
        return end, arr.fade_start_bar * 4 * spb, end
    return end + TAIL_SECONDS, None, None


def _render_tracks(tracks: list[TrackData], arr: Arrangement, work: Path, fade: bool,
                   warnings: list[str]) -> dict[str, np.ndarray]:
    fs, sf2 = find_fluidsynth(), find_soundfont()
    if not fs:
        warnings.append("FluidSynth niet gevonden – alleen MIDI geëxporteerd (brew install fluid-synth).")
        return {}
    if not sf2:
        warnings.append("Geen SoundFont (.sf2) gevonden – alleen MIDI geëxporteerd. Zie README.")
        return {}
    work.mkdir(parents=True, exist_ok=True)
    length_s, f_start, f_end = _timing(arr, fade)
    n_samples = int(length_s * renderer.SAMPLE_RATE)
    tail_beats = TAIL_SECONDS / arr.seconds_per_beat + 1

    def one(track: TrackData) -> tuple[str, Optional[np.ndarray], Optional[str]]:
        mid = work / f"{track.id}.mid"
        wav = work / f"{track.id}.wav"
        try:
            # Render-MIDI zonder CC11-fade: de fade wordt sample-nauwkeurig op de audio gezet.
            write_stem(track, arr, mid, with_fade=False, tail_beats=tail_beats)
            renderer.render_midi(fs, sf2, mid, wav)
            audio = renderer.fit_length(renderer.load(wav), n_samples)
            audio = renderer.apply_fade(audio, f_start, f_end)
            return track.id, renderer.protect_clip(audio), None
        except renderer.RenderError as e:
            return track.id, None, str(e)

    out: dict[str, np.ndarray] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(tracks))) as pool:
        for tid, audio, err in pool.map(one, tracks):
            if err:
                warnings.append(f"{tid}: {err}")
            elif audio is not None:
                out[tid] = audio
    shutil.rmtree(work, ignore_errors=True)
    return out


def _mix(stems: dict[str, np.ndarray]) -> np.ndarray:
    mix = None
    for audio in stems.values():
        mix = audio.copy() if mix is None else mix + audio
    return renderer.normalize(mix)


def generate_session(req: GenerateRequest) -> SessionResult:
    plan = resolve_plan(req)
    instruments = _selected(req)
    arr = build_arrangement(plan, req.duration_seconds, req.bridge, req.fade_outro, req.fade_bars, req.intro)
    tracks = generate_tracks(arr, instruments, req.humanize)
    warnings = plan.warnings

    length_s, _, _ = _timing(arr, req.fade_outro)
    if plan.song_name:
        base = storage.song_folder_name(plan.song_name, plan.key.folder_tag, plan.bpm, length_s)
    else:
        base = storage.folder_name(plan.profile.genre, plan.key.folder_tag, plan.reference and plan.title or "",
                                   plan.profile.mood, plan.bpm, length_s)
    folder = storage.create_session_dir(base)

    # MIDI
    for t in tracks:
        meta = INSTRUMENT_META[t.id]
        write_stem(t, arr, folder / f"{meta['number']:02d}_{meta['file']}.mid", with_fade=req.fade_outro)
    write_full(tracks, arr, folder / "00_Arrangement.mid", with_fade=req.fade_outro)
    (folder / "Akkoorden.txt").write_text(chord_chart(arr), encoding="utf-8")

    # Audio
    stems = _render_tracks(tracks, arr, folder / ".render", req.fade_outro, warnings)
    for tid, audio in stems.items():
        meta = INSTRUMENT_META[tid]
        stem_name = f"{meta['number']:02d}_{meta['file']}"
        if "wav" in req.formats:
            renderer.write(audio, folder / f"{stem_name}.wav", "WAV")
        if "aiff" in req.formats:
            renderer.write(audio, folder / f"{stem_name}.aiff", "AIFF")
    mix_url = None
    if stems:
        mix = _mix(stems)
        renderer.write(mix, folder / "00_Mix.wav", "WAV", "PCM_16")
        if "aiff" in req.formats:
            renderer.write(mix, folder / "00_Mix.aiff", "AIFF")
        if renderer.to_m4a(find_afconvert(), folder / "00_Mix.wav", folder / "00_Mix.m4a"):
            mix_url = f"/api/sessions/{folder.name}/files/00_Mix.m4a"
        else:
            mix_url = f"/api/sessions/{folder.name}/files/00_Mix.wav"

    sections = []
    for s in arr.sections:
        seen = []
        for tc in s.chords:
            if not seen or seen[-1] != tc.chord.symbol:
                seen.append(tc.chord.symbol)
        sections.append({"name": s.kind, "label": s.label, "start_bar": s.start_bar, "bars": s.bars,
                         "energy": round((s.energy_start + s.energy_end) / 2, 2), "chords": seen[:16]})

    result = SessionResult(
        id=folder.name, folder=folder.name, path=str(folder), created=datetime.now().isoformat(timespec="seconds"),
        title=plan.title, genre=plan.profile.genre, mood=plan.profile.mood, key=plan.key.name, bpm=plan.bpm,
        bars=arr.total_bars, duration_seconds=round(length_s, 1), requested_seconds=req.duration_seconds,
        seed=plan.seed, fade_outro=req.fade_outro, bridge=any(s.kind == "bridge" for s in arr.sections),
        sections=sections, files=[], mix_url=mix_url, zip_url=f"/api/sessions/{folder.name}/zip",
        audio_rendered=bool(stems), warnings=warnings, profile=plan.profile,
    )
    data = result.model_dump()
    data["request"] = req.model_dump(exclude={"profile"})
    data["progressions"] = plan.progression_texts
    storage.save_session_json(folder, data)
    result.files = [FileInfo(**f) for f in storage.list_files(folder)]
    data["files"] = [f.model_dump() for f in result.files]
    storage.save_session_json(folder, data)
    return result


def generate_preview(req: GenerateRequest) -> PreviewResult:
    plan = resolve_plan(req, preview=True)
    instruments = _selected(req)
    arr = build_preview_arrangement(plan)
    tracks = generate_tracks(arr, instruments, req.humanize)
    warnings = plan.warnings
    storage.ensure_dirs()
    storage.cleanup_previews()
    pid = uuid.uuid4().hex[:10]
    stems = _render_tracks(tracks, arr, PREVIEW_DIR / f".work_{pid}", fade=False, warnings=warnings)
    seconds = arr.total_beats * arr.seconds_per_beat
    if not stems:
        return PreviewResult(url=None, bars=arr.total_bars, seconds=round(seconds, 1), audio_rendered=False,
                             warnings=warnings)
    mix = _mix(stems)
    wav = PREVIEW_DIR / f"preview_{pid}.wav"
    renderer.write(mix, wav, "WAV", "PCM_16")
    m4a = PREVIEW_DIR / f"preview_{pid}.m4a"
    name = m4a.name if renderer.to_m4a(find_afconvert(), wav, m4a) else wav.name
    return PreviewResult(url=f"/api/preview/files/{name}", bars=arr.total_bars, seconds=round(seconds, 1),
                         audio_rendered=True, warnings=warnings)


# --------------------------------------------------------------------------- #
# Gitaarsolo's achteraf toevoegen
# --------------------------------------------------------------------------- #
SOLO_PREFIX = "06_Solo_"
SOLO_MIX = "00_Mix_met_solo"


def _rebuild_arrangement(data: dict) -> tuple[GenerateRequest, Arrangement]:
    """Zelfde instellingen + zelfde seed = exact hetzelfde arrangement als bij het genereren."""
    if not data.get("request"):
        raise ValueError("Solo's toevoegen kan alleen bij nummers die met deze app (server) zijn gemaakt, "
                         "niet bij tracks van de online HTML-app.")
    req_data = dict(data["request"])
    req_data["seed"] = data.get("seed", req_data.get("seed"))
    if data.get("profile"):
        req_data["profile"] = data["profile"]
    req = GenerateRequest(**req_data)
    plan = resolve_plan(req)
    arr = build_arrangement(plan, req.duration_seconds, req.bridge, req.fade_outro, req.fade_bars, req.intro)
    saved = [(s["label"], s["start_bar"], s["bars"]) for s in data.get("sections", [])]
    if saved and saved != [(s.label, s.start_bar, s.bars) for s in arr.sections]:
        raise ValueError("De structuur van dit nummer kon niet worden teruggevonden (gemaakt met een oudere versie). "
                         "Gebruik ‘Instellingen overnemen’ en genereer het nummer opnieuw.")
    return req, arr


def _clear_solos(folder: Path) -> None:
    for p in list(folder.glob(SOLO_PREFIX + "*")) + list(folder.glob(SOLO_MIX + ".*")) + list(folder.glob(".*.zip")):
        p.unlink(missing_ok=True)


def _load_stems(folder: Path) -> list[np.ndarray]:
    stems = []
    for meta in lib.INSTRUMENTS:
        for ext in (".wav", ".aiff"):
            p = folder / f"{meta['number']:02d}_{meta['file']}{ext}"
            if p.exists():
                stems.append(renderer.load(p))
                break
    return stems


def _finish_session(folder: Path, data: dict) -> dict:
    data["files"] = storage.list_files(folder)
    storage.save_session_json(folder, data)
    return storage.load_session(folder.name)


def remove_solos(session_id: str) -> dict:
    folder = storage.session_path(session_id)
    data = storage.load_session(session_id) or {}
    if data.get("source") != "server":
        raise ValueError("Dit nummer heeft geen solo's van deze app.")
    _clear_solos(folder)
    try:
        _, arr = _rebuild_arrangement(data)
        (folder / "Akkoorden.txt").write_text(chord_chart(arr), encoding="utf-8")
    except ValueError:
        pass
    data.pop("solo_warnings", None)
    data.pop("solos", None)
    data.pop("solo_settings", None)
    data.pop("mix_solo_url", None)
    return _finish_session(folder, data)


def add_solos(session_id: str, sreq: SoloRequest) -> dict:

    folder = storage.session_path(session_id)
    data = storage.load_session(session_id)
    if not data:
        raise ValueError("Nummer niet gevonden.")
    req, arr = _rebuild_arrangement(data)
    idxs = sorted(set(sreq.sections))
    if not idxs:
        raise ValueError("Kies minimaal één deel van het nummer voor een solo.")
    if any(i < 0 or i >= len(arr.sections) for i in idxs):
        raise ValueError("Onbekend deel van het nummer gekozen.")

    genre, mood = arr.plan.profile.genre, arr.plan.profile.mood
    style = auto_style(genre) if sreq.style == "auto" else sreq.style
    tone = auto_tone(genre, mood) if sreq.tone == "auto" else sreq.tone
    seed = sreq.seed if sreq.seed is not None else random.randint(1, 999_999)

    _clear_solos(folder)
    warnings: list[str] = []
    solos, tracks, names = [], [], []
    for n, i in enumerate(idxs, start=1):
        sec = arr.sections[i]
        tr = solo_track(arr, sec, n, style, tone, seed, req.humanize)
        name = f"{SOLO_PREFIX}{n}_{storage.camel(sec.label, 20)}"
        write_stem(tr, arr, folder / f"{name}.mid", with_fade=req.fade_outro)
        tracks.append(tr)
        names.append(name)
        solos.append({"number": n, "section": i, "label": sec.label, "start_bar": sec.start_bar,
                      "bars": sec.bars, "name": name})

    for tr, name in zip(tracks, names):
        tr.id = name                       # _render_tracks indexeert op id
    rendered = _render_tracks(tracks, arr, folder / ".render_solo", req.fade_outro, warnings)
    audio_by_name = {name: rendered[name] for name in names if name in rendered}
    for name, audio in audio_by_name.items():
        if "wav" in req.formats or "aiff" not in req.formats:
            renderer.write(audio, folder / f"{name}.wav", "WAV")
        if "aiff" in req.formats:
            renderer.write(audio, folder / f"{name}.aiff", "AIFF")

    mix_solo_url = None
    stems = _load_stems(folder) if audio_by_name else []
    if stems:
        n = len(stems[0])
        backing = sum(renderer.fit_length(s, n) for s in stems)
        lead = sum(renderer.fit_length(a, n) for a in audio_by_name.values())
        mix = renderer.normalize(backing + lead * 1.1)
        renderer.write(mix, folder / f"{SOLO_MIX}.wav", "WAV", "PCM_16")
        if renderer.to_m4a(find_afconvert(), folder / f"{SOLO_MIX}.wav", folder / f"{SOLO_MIX}.m4a"):
            mix_solo_url = f"/api/sessions/{storage._url_id(folder.name)}/files/{SOLO_MIX}.m4a"
        else:
            mix_solo_url = f"/api/sessions/{storage._url_id(folder.name)}/files/{SOLO_MIX}.wav"

    tone_label = TONES[tone][1]
    data["solos"] = solos
    data["solo_settings"] = {"style": style, "tone": tone, "tone_label": tone_label, "seed": seed,
                             "sections": idxs}
    data["mix_solo_url"] = mix_solo_url
    data["solo_warnings"] = warnings
    (folder / "Akkoorden.txt").write_text(chord_chart(arr) + _solo_chart(solos, style, tone_label), encoding="utf-8")
    return _finish_session(folder, data)


def _solo_chart(solos: list[dict], style: str, tone_label: str) -> str:
    lines = ["", f"Gitaarsolo's ({style}, {tone_label}) – elk bestand begint op maat 1:"]
    for s in solos:
        lines.append(f"  Solo {s['number']}: {s['label']}, maat {s['start_bar'] + 1}-{s['start_bar'] + s['bars']}"
                     f"  ->  {s['name']}.wav / .mid")
    return "\n".join(lines) + "\n"
