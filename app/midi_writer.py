"""Schrijft MIDI-bestanden (per instrument én een complete multitrack) met mido."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import mido

from .arranger import Arrangement
from .config import TICKS_PER_BEAT as T
from .generators import Note, TrackData

# Prioriteit bij gelijke tick: meta < program < cc < note_off < note_on
_PRIO = {"meta": 0, "program_change": 1, "control_change": 2, "note_off": 3, "note_on": 4}

MIDO_KEYS = {"A", "A#m", "Ab", "Abm", "Am", "B", "Bb", "Bbm", "Bm", "C", "C#", "C#m", "Cb", "Cm", "D",
             "D#m", "Db", "Dm", "E", "Eb", "Ebm", "Em", "F", "F#", "F#m", "Fm", "G", "G#m", "Gb", "Gm"}
ENHARMONIC = {"D#": "Eb", "G#": "Ab", "A#": "Bb", "Dbm": "C#m", "Gbm": "F#m", "A#m": "A#m", "D#m": "D#m"}


def _clean_notes(notes: list[Note]) -> list[Note]:
    """Voorkom overlappende noten met dezelfde toonhoogte (anders hangende/afgekapte noten)."""
    by_pitch: dict[int, list[Note]] = {}
    for n in notes:
        by_pitch.setdefault(n.pitch, []).append(n)
    out = []
    for pitch, ns in by_pitch.items():
        ns.sort(key=lambda n: n.tick)
        for i, n in enumerate(ns):
            if i + 1 < len(ns):
                nxt = ns[i + 1]
                if nxt.tick <= n.tick:
                    continue  # dubbele aanslag op dezelfde tick
                if n.tick + n.dur >= nxt.tick:
                    n = Note(n.tick, max(10, nxt.tick - n.tick - 2), n.pitch, n.vel)
            out.append(n)
    return out


def _expression_curve(points: list[tuple[float, int]]):
    pts = sorted(points) or [(0.0, 100)]

    def value(beat: float) -> float:
        if beat <= pts[0][0]:
            return pts[0][1]
        for (b1, v1), (b2, v2) in zip(pts, pts[1:]):
            if b1 <= beat < b2:
                if b2 - b1 < 1e-6:
                    return v2
                return v1 + (v2 - v1) * (beat - b1) / (b2 - b1)
        return pts[-1][1]
    return value


def fade_gain(t: float) -> float:
    """Gelijke-kracht fade: 1 -> 0 (zelfde curve als de audio-fade)."""
    t = max(0.0, min(1.0, t))
    return math.cos(t * math.pi / 2)


def _expression_events(track: TrackData, arr: Arrangement, with_fade: bool) -> list[tuple[int, int]]:
    curve = _expression_curve(track.expression or [(0.0, 100)])
    fade_start = arr.fade_start_bar * 4.0 if (with_fade and arr.fade_start_bar is not None) else None
    end = arr.total_beats
    events: list[tuple[int, int]] = []
    last_val = None
    beat, step = 0.0, 0.25
    while beat <= end + 1e-6:
        val = curve(beat)
        if fade_start is not None and beat >= fade_start:
            step = 0.125
            val *= fade_gain((beat - fade_start) / max(1e-6, end - fade_start))
        v = int(round(max(0, min(127, val))))
        if v != last_val:
            events.append((int(round(beat * T)), v))
            last_val = v
        beat += step
    if fade_start is not None and last_val != 0:
        events.append((int(round(end * T)), 0))
    return events


def _conductor_events(arr: Arrangement, markers: bool = True) -> list[tuple[int, str, mido.MetaMessage]]:
    ev = [
        (0, "meta", mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(arr.bpm))),
        (0, "meta", mido.MetaMessage("time_signature", numerator=4, denominator=4)),
    ]
    k = arr.plan.key.name
    k = ENHARMONIC.get(k, k)
    if k in MIDO_KEYS:
        ev.append((0, "meta", mido.MetaMessage("key_signature", key=k)))
    if markers:
        for s in arr.sections:
            ev.append((int(s.start_beat * T), "meta", mido.MetaMessage("marker", text=s.label)))
    return ev


def _track_events(track: TrackData, arr: Arrangement, with_fade: bool) -> list[tuple[int, str, mido.Message]]:
    ch = track.channel
    ev: list[tuple[int, str, object]] = [
        (0, "meta", mido.MetaMessage("track_name", name=track.name)),
        (0, "control_change", mido.Message("control_change", channel=ch, control=0, value=0)),
        (0, "control_change", mido.Message("control_change", channel=ch, control=7, value=track.volume)),
        (0, "control_change", mido.Message("control_change", channel=ch, control=10, value=track.pan)),
        (0, "control_change", mido.Message("control_change", channel=ch, control=91, value=track.reverb)),
        (0, "control_change", mido.Message("control_change", channel=ch, control=93, value=track.chorus)),
    ]
    if ch != 9:
        ev.insert(1, (0, "program_change", mido.Message("program_change", channel=ch, program=track.program)))
    for tick, val in _expression_events(track, arr, with_fade):
        ev.append((tick, "control_change", mido.Message("control_change", channel=ch, control=11, value=val)))
    for n in _clean_notes(track.notes):
        ev.append((n.tick, "note_on", mido.Message("note_on", channel=ch, note=n.pitch, velocity=n.vel)))
        ev.append((n.tick + n.dur, "note_off", mido.Message("note_off", channel=ch, note=n.pitch, velocity=0)))
    return ev


def _to_track(events: list, end_tick: Optional[int] = None) -> mido.MidiTrack:
    events = sorted(events, key=lambda e: (e[0], _PRIO.get(e[1], 5)))
    tr = mido.MidiTrack()
    now = 0
    for tick, _, msg in events:
        tr.append(msg.copy(time=max(0, tick - now)))
        now = max(now, tick)
    final = max(now, end_tick or 0)
    tr.append(mido.MetaMessage("end_of_track", time=final - now))
    return tr


def write_stem(track: TrackData, arr: Arrangement, path: Path, with_fade: bool = True,
               tail_beats: float = 0.0) -> None:
    """Type 0: tempo, maatsoort, markers en het instrument in één spoor (ideaal voor Logic)."""
    mid = mido.MidiFile(type=0, ticks_per_beat=T)
    events = _conductor_events(arr) + _track_events(track, arr, with_fade)
    end_tick = int((arr.total_beats + tail_beats) * T)
    mid.tracks.append(_to_track(events, end_tick))
    mid.save(str(path))


def write_full(tracks: list[TrackData], arr: Arrangement, path: Path, with_fade: bool = True) -> None:
    """Type 1: conductor-spoor + één spoor per instrument."""
    mid = mido.MidiFile(type=1, ticks_per_beat=T)
    end_tick = int(arr.total_beats * T)
    conductor = _conductor_events(arr) + [(0, "meta", mido.MetaMessage("track_name", name="Tempo & Markers"))]
    mid.tracks.append(_to_track(conductor, end_tick))
    for t in tracks:
        mid.tracks.append(_to_track(_track_events(t, arr, with_fade), end_tick))
    mid.save(str(path))
