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


SOLO_PREFIX = "06_Solo_"
SOLO_MIX = "00_Mix_met_solo"
GENERATED_EXT = {".mid", ".wav", ".aiff", ".aif", ".m4a"}


def _clear_generated(folder: Path) -> None:
    """Oude stems/MIDI/mixen weg vóór het opnieuw opbouwen in dezelfde map (session.json blijft tot de nieuwe er is)."""
    for p in folder.iterdir():
        if p.is_file() and (p.suffix.lower() in GENERATED_EXT or p.name.endswith(".zip")) and p.name[:2].isdigit():
            p.unlink(missing_ok=True)
        elif p.is_file() and p.name.startswith(".") and p.name.endswith(".zip"):
            p.unlink(missing_ok=True)


def _solo_tracks(arr: Arrangement, req: GenerateRequest, solo_seed: int) -> tuple[list[TrackData], list[dict]]:
    tracks, info = [], []
    genre, mood = arr.plan.profile.genre, arr.plan.profile.mood
    base = {s.base_index: s for s in arr.sections if s.base_index is not None}
    for sec in arr.sections:
        spec = sec.solo_spec
        if spec is None:
            continue
        style = auto_style(genre) if spec.style == "auto" else spec.style
        tone = auto_tone(genre, mood) if spec.tone == "auto" else spec.tone
        after = base[spec.after]
        tr = solo_track(arr, sec, sec.solo_no, style, tone, solo_seed, req.humanize)
        tr.id = f"{SOLO_PREFIX}{sec.solo_no}_na{storage.camel(after.label, 18)}"
        tr.name = f"Gitaarsolo {sec.solo_no}"
        tracks.append(tr)
        info.append({"number": sec.solo_no, "label": sec.label, "after": spec.after, "after_label": after.label,
                     "start_bar": sec.start_bar, "bars": sec.bars, "style": style, "tone": tone,
                     "tone_label": TONES[tone][1], "chords": spec.chords, "name": tr.id})
    return tracks, info


def _solo_chart(solos: list[dict]) -> str:
    if not solos:
        return ""
    lines = ["", "Gitaarsolo's (elk audiobestand begint op maat 1):"]
    for s in solos:
        lines.append(f"  Gitaarsolo {s['number']}: na {s['after_label']}, maat {s['start_bar'] + 1}-"
                     f"{s['start_bar'] + s['bars']} ({s['bars']} maten, {s['style']}, {s['tone_label']})"
                     f"  ->  {s['name']}.wav / .mid")
    return "\n".join(lines) + "\n"


def generate_session(req: GenerateRequest, folder: Optional[Path] = None,
                     keep: Optional[dict] = None) -> SessionResult:
    """Nieuw nummer, of (met `folder`) een bestaand nummer in dezelfde map opnieuw opbouwen, bv. met solo's."""
    plan = resolve_plan(req)
    instruments = _selected(req)
    arr = build_arrangement(plan, req.duration_seconds, req.bridge, req.fade_outro, req.fade_bars, req.intro,
                            req.solos)
    tracks = generate_tracks(arr, instruments, req.humanize)
    warnings = plan.warnings
    solo_seed = req.solo_seed if req.solo_seed is not None else random.randint(1, 999_999)
    solo_tracks, solo_info = _solo_tracks(arr, req, solo_seed) if req.solos else ([], [])
    if req.solos:
        req = req.model_copy(update={"solo_seed": solo_seed})

    length_s, _, _ = _timing(arr, req.fade_outro)
    if folder is None:
        if plan.song_name:
            base = storage.song_folder_name(plan.song_name, plan.key.folder_tag, plan.bpm, length_s)
        else:
            base = storage.folder_name(plan.profile.genre, plan.key.folder_tag, plan.reference and plan.title or "",
                                       plan.profile.mood, plan.bpm, length_s)
        folder = storage.create_session_dir(base)
    else:
        _clear_generated(folder)

    # MIDI
    for t in tracks:
        meta = INSTRUMENT_META[t.id]
        write_stem(t, arr, folder / f"{meta['number']:02d}_{meta['file']}.mid", with_fade=req.fade_outro)
    for t in solo_tracks:
        write_stem(t, arr, folder / f"{t.id}.mid", with_fade=req.fade_outro)
    write_full(tracks + solo_tracks, arr, folder / "00_Arrangement.mid", with_fade=req.fade_outro)
    (folder / "Akkoorden.txt").write_text(chord_chart(arr) + _solo_chart(solo_info), encoding="utf-8")

    # Audio
    stems = _render_tracks(tracks + solo_tracks, arr, folder / ".render", req.fade_outro, warnings)
    solo_ids = {t.id for t in solo_tracks}
    for tid, audio in stems.items():
        stem_name = tid if tid in solo_ids else f"{INSTRUMENT_META[tid]['number']:02d}_{INSTRUMENT_META[tid]['file']}"
        if "wav" in req.formats or not req.formats:
            renderer.write(audio, folder / f"{stem_name}.wav", "WAV")
        if "aiff" in req.formats:
            renderer.write(audio, folder / f"{stem_name}.aiff", "AIFF")
    sid = storage._url_id(folder.name)

    def mix_file(name: str, parts: dict) -> Optional[str]:
        if not parts:
            return None
        mix = _mix(parts)
        renderer.write(mix, folder / f"{name}.wav", "WAV", "PCM_16")
        if "aiff" in req.formats:
            renderer.write(mix, folder / f"{name}.aiff", "AIFF")
        ext = "m4a" if renderer.to_m4a(find_afconvert(), folder / f"{name}.wav", folder / f"{name}.m4a") else "wav"
        return f"/api/sessions/{sid}/files/{name}.{ext}"

    backing = {k: v for k, v in stems.items() if k not in solo_ids}
    mix_url = mix_file("00_Mix", backing)
    mix_solo_url = None
    if solo_ids & set(stems):
        lead = {k: v * 1.1 for k, v in stems.items() if k in solo_ids}
        mix_solo_url = mix_file(SOLO_MIX, {**backing, **lead})

    sections = []
    for s in arr.sections:
        seen = []
        for tc in s.chords:
            if not seen or seen[-1] != tc.chord.symbol:
                seen.append(tc.chord.symbol)
        sections.append({"name": s.kind, "label": s.label, "start_bar": s.start_bar, "bars": s.bars,
                         "energy": round((s.energy_start + s.energy_end) / 2, 2), "chords": seen[:16],
                         "base_index": s.base_index, "solo": s.solo_no})

    keep = keep or {}
    result = SessionResult(
        id=folder.name, folder=folder.name, path=str(folder),
        created=keep.get("created") or datetime.now().isoformat(timespec="seconds"),
        title=plan.title, genre=plan.profile.genre, mood=plan.profile.mood, key=plan.key.name, bpm=plan.bpm,
        bars=arr.total_bars, duration_seconds=round(length_s, 1), requested_seconds=req.duration_seconds,
        seed=plan.seed, fade_outro=req.fade_outro, bridge=any(s.kind == "bridge" for s in arr.sections),
        sections=sections, files=[], mix_url=mix_url, zip_url=f"/api/sessions/{sid}/zip",
        audio_rendered=bool(stems), warnings=warnings, profile=plan.profile, solos=solo_info,
        mix_solo_url=mix_solo_url,
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
# Gitaarsolo's: het nummer opnieuw opbouwen (zelfde seed) met ingevoegde solodelen
# --------------------------------------------------------------------------- #
def set_solos(session_id: str, sreq: SoloRequest) -> dict:
    folder = storage.session_path(session_id)
    data = storage.load_session(session_id)
    if not data:
        raise ValueError("Nummer niet gevonden.")
    if not data.get("request"):
        raise ValueError("Solo's toevoegen kan alleen bij nummers die met deze app (server) zijn gemaakt, "
                         "niet bij tracks van de online HTML-app.")
    req_data = dict(data["request"])
    req_data["seed"] = data.get("seed", req_data.get("seed"))
    if data.get("profile"):
        req_data["profile"] = data["profile"]
    req_data["solos"] = [x.model_dump() for x in sreq.solos]
    req_data["solo_seed"] = sreq.seed
    req = GenerateRequest(**req_data)
    generate_session(req, folder=folder, keep={"created": data.get("created")})
    return storage.load_session(folder.name)
