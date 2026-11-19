"""Orkestratie: instellingen -> arrangement -> MIDI -> audio -> sessiemap."""
from __future__ import annotations

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
from .models import FileInfo, GenerateRequest, PreviewResult, SessionResult

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
