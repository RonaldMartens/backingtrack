"""Bepaalt instellingen, maatenaantal en songstructuur (Intro, Couplet, Refrein, Bridge, Outro)."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Optional

from . import library as lib
from .analyzer import profile_from_mood
from .models import GenerateRequest, MusicProfile
from .theory import (ChordEvent, Chord, Key, parse_key, parse_progression, parse_chord_token,
                     progression_mode_hint)


@dataclass
class TimedChord:
    start: float      # absolute positie in beats (kwartnoten)
    beats: float
    chord: Chord


@dataclass
class Section:
    kind: str                # intro / verse / chorus / bridge / solo / interlude / outro
    label: str
    start_bar: int
    bars: int
    energy_start: float
    energy_end: float
    chords: list[TimedChord] = field(default_factory=list)
    final_hit: bool = False   # strak slotakkoord in de laatste maat
    fade: bool = False

    @property
    def start_beat(self) -> float:
        return self.start_bar * 4.0

    @property
    def end_beat(self) -> float:
        return (self.start_bar + self.bars) * 4.0

    def energy_at(self, beat: float) -> float:
        if self.bars <= 0:
            return self.energy_start
        t = (beat - self.start_beat) / (self.bars * 4.0)
        t = max(0.0, min(1.0, t))
        return self.energy_start + (self.energy_end - self.energy_start) * t


@dataclass
class Plan:
    profile: MusicProfile
    key: Key
    bpm: int
    verse: list[ChordEvent]
    chorus: list[ChordEvent]
    bridge: list[ChordEvent]
    progression_texts: dict
    warnings: list[str]
    seed: int
    title: str
    reference: Optional[str]
    song_name: str = ""


@dataclass
class Arrangement:
    plan: Plan
    sections: list[Section]
    total_bars: int
    fade_start_bar: Optional[int]
    fade_bars: int

    @property
    def bpm(self) -> int:
        return self.plan.bpm

    @property
    def seconds_per_beat(self) -> float:
        return 60.0 / self.plan.bpm

    @property
    def total_beats(self) -> float:
        return self.total_bars * 4.0

    def section_at(self, beat: float) -> Section:
        for s in self.sections:
            if s.start_beat <= beat < s.end_beat:
                return s
        return self.sections[-1]


# --------------------------------------------------------------------------- #
# Instellingen samenvoegen
# --------------------------------------------------------------------------- #
def _relative_key(key: Key) -> Key:
    if key.minor:
        pc = (key.root + 3) % 12
        return Key(pc, False, key.note_name(pc))
    pc = (key.root - 3) % 12
    return Key(pc, True, key.note_name(pc))


def _bars_of(events: list[ChordEvent]) -> float:
    return sum(e.beats for e in events) / 4.0


def apply_genre(profile: MusicProfile, genre: str) -> MusicProfile:
    if genre not in lib.GENRES or genre == profile.genre:
        return profile
    g = lib.GENRES[genre]
    data = profile.model_dump()
    data.update(
        genre=genre, drum_style=g["drum_style"], bass_style=g["bass_style"], keys_style=g["keys_style"],
        guitar_style=g["guitar_style"], pad_style=g["pad_style"], swing=g["swing"], color=g["color"],
        programs=dict(g["programs"]), velocity=int(round((profile.velocity + g["velocity"]) / 2)),
    )
    return MusicProfile(**data)


def resolve_plan(req: GenerateRequest, preview: bool = False) -> Plan:
    warnings: list[str] = []
    profile = req.profile.model_copy(deep=True) if req.profile else profile_from_mood(req.mood)
    if req.genre and req.genre != "auto":
        profile = apply_genre(profile, req.genre)

    try:
        key = parse_key(req.key if req.key and req.key != "auto" else profile.key)
    except ValueError as e:
        raise ValueError(str(e))

    verse_txt, chorus_txt, bridge_txt = profile.verse, profile.chorus, profile.bridge

    if req.progression_mode in ("preset", "custom"):
        text, wants_minor, preset_bridge = None, None, None
        if req.progression_mode == "preset":
            preset = lib.PROGRESSION_PRESETS.get(req.progression_preset or "")
            if not preset:
                raise ValueError("Kies een akkoordenschema uit de lijst.")
            text, wants_minor, preset_bridge = preset["text"], preset["minor"], preset.get("bridge")
        else:
            text = (req.progression_custom or "").strip()
            if not text:
                raise ValueError("Vul een eigen akkoordenschema in (bv. Am - F - C - G of i - VI - III - VII).")
            if re.search(r"12\s*-?\s*(bar|maten|maats)", text, re.IGNORECASE):
                minor = key.minor or "mineur" in text.lower() or "minor" in text.lower()
                p = lib.PROGRESSION_PRESETS["minor_blues12" if minor else "blues12"]
                text, wants_minor, preset_bridge = p["text"], p["minor"], p.get("bridge")
            else:
                wants_minor = progression_mode_hint(text)
        if wants_minor is not None and wants_minor != key.minor:
            new_key = _relative_key(key)
            warnings.append(
                f"Het schema is {'mineur' if wants_minor else 'majeur'}: gespeeld in {new_key.name} "
                f"(relatieve {'mineur' if wants_minor else 'majeur'} van {key.name})."
            )
            key = new_key
        verse_txt = chorus_txt = text
        bridge_txt = preset_bridge or (lib.DEFAULT_BRIDGE_MINOR if key.minor else lib.DEFAULT_BRIDGE_MAJOR)
        if req.progression_mode == "custom" and progression_mode_hint(text) is None and preset_bridge is None:
            # Akkoordnamen: bridge relatief t.o.v. de gekozen/afgeleide toonsoort
            bridge_txt = lib.DEFAULT_BRIDGE_MINOR if key.minor else lib.DEFAULT_BRIDGE_MAJOR

    try:
        verse = parse_progression(verse_txt, key)
        chorus = parse_progression(chorus_txt, key)
        bridge = parse_progression(bridge_txt, key)
    except (ValueError, KeyError) as e:
        raise ValueError(f"Akkoordenschema niet te lezen: {e}")

    seed = req.seed if req.seed is not None else random.randint(1, 999_999)
    profile.key = key.name
    song_name = (req.song_name or "").strip()
    title = song_name or profile.title or (req.reference or "").strip() or lib.MOODS.get(profile.mood, {}).get("label", "")
    return Plan(profile=profile, key=key, bpm=req.bpm, verse=verse, chorus=chorus, bridge=bridge,
                progression_texts={"verse": verse_txt, "chorus": chorus_txt, "bridge": bridge_txt},
                warnings=warnings, seed=seed, title=title, reference=req.reference, song_name=song_name)


# --------------------------------------------------------------------------- #
# Structuur
# --------------------------------------------------------------------------- #
def total_bars_for(duration_seconds: float, bpm: int) -> int:
    raw = duration_seconds * bpm / 60.0 / 4.0
    bars = int(round(raw / 4.0)) * 4
    return max(16, bars)


def _unit(events: list[ChordEvent]) -> int:
    b = _bars_of(events)
    if abs(b - 12) < 1e-6:
        return 12
    if abs(b - 16) < 1e-6:
        return 16
    return 8


def _fill(events: list[ChordEvent], start_beat: float, beats: float) -> list[TimedChord]:
    out, pos, i = [], 0.0, 0
    while pos < beats - 1e-6:
        ev = events[i % len(events)]
        dur = min(ev.beats, beats - pos)
        out.append(TimedChord(start_beat + pos, dur, ev.chord))
        pos += dur
        i += 1
    return out


def build_arrangement(plan: Plan, duration_seconds: int, bridge: bool, fade: bool, fade_bars: int,
                      intro_on: bool = True) -> Arrangement:
    total = total_bars_for(duration_seconds, plan.bpm)
    u = _unit(plan.verse)
    intro = (4 if total < 40 else 8) if intro_on else 0   # zonder intro: direct het couplet
    outro = (8 if fade_bars > 4 else 4) if fade else 4
    if total < 32:
        outro = 4
    middle = total - intro - outro

    bridge_bars = 0
    if bridge:
        bb = 8 if _bars_of(plan.bridge) <= 8 else int(round(_bars_of(plan.bridge) / 4)) * 4
        if middle - bb >= 2 * min(u, 8):
            bridge_bars = bb
        else:
            plan.warnings.append("Nummer is te kort voor een bridge; bridge overgeslagen.")
    body = middle - bridge_bars
    if body < 2 * u and u == 8:
        u = 4
    if u == 8 and body // u > 8:
        u = 16   # lange nummers: langere secties i.p.v. eindeloos wisselen
    n = max(1, body // u)
    remainder = body - n * u

    kinds: list[str] = []
    for i in range(n):
        kinds.append("verse" if i % 2 == 0 else "chorus")
    if len(kinds) >= 2 and kinds[-1] == "verse":
        kinds[-1] = "chorus"
    if len(kinds) >= 6 and kinds[4] == "verse":
        kinds[4] = "solo"
    blocks: list[tuple[str, int]] = [(k, u) for k in kinds]
    if remainder > 0:
        pos = 2 if len(blocks) >= 2 else len(blocks)
        blocks.insert(pos, ("interlude", remainder))
    if bridge_bars:
        last_chorus = max((i for i, b in enumerate(blocks) if b[0] == "chorus"), default=len(blocks))
        blocks.insert(last_chorus, ("bridge", bridge_bars))

    sections: list[Section] = []
    bar = 0
    if intro:
        sections.append(Section("intro", "Intro", bar, intro, 0.3, 0.42))
        bar += intro
    counts = {"verse": 0, "chorus": 0, "solo": 0}
    n_chorus = sum(1 for b in blocks if b[0] == "chorus")
    for kind, bars in blocks:
        if kind == "verse":
            counts["verse"] += 1
            e = 0.45 if counts["verse"] == 1 else 0.58
            sections.append(Section(kind, f"Couplet {counts['verse']}", bar, bars, e, e + 0.05))
        elif kind == "chorus":
            counts["chorus"] += 1
            last = counts["chorus"] == n_chorus
            e = 1.0 if last and n_chorus > 1 else 0.75 + 0.1 * min(counts["chorus"] - 1, 1)
            sections.append(Section(kind, f"Refrein {counts['chorus']}", bar, bars, e, e))
        elif kind == "solo":
            sections.append(Section(kind, "Solo", bar, bars, 0.78, 0.85))
        elif kind == "interlude":
            sections.append(Section(kind, "Tussenspel", bar, bars, 0.5, 0.55))
        elif kind == "bridge":
            sections.append(Section(kind, "Bridge", bar, bars, 0.5, 0.98))
        bar += bars
    sections.append(Section("outro", "Outro", bar, outro, 0.72 if fade else 0.6, 0.72 if fade else 0.45,
                            final_hit=not fade, fade=fade))
    bar += outro

    for s in sections:
        if s.kind in ("chorus",):
            prog = plan.chorus
        elif s.kind == "bridge":
            prog = plan.bridge
        elif s.kind == "outro" and fade:
            prog = plan.chorus
        else:
            prog = plan.verse
        if s.final_hit:
            body_beats = (s.bars - 1) * 4.0
            s.chords = _fill(prog, s.start_beat, body_beats) if body_beats > 0 else []
            tonic = parse_chord_token("i" if plan.key.minor else "I", plan.key)
            s.chords.append(TimedChord(s.start_beat + body_beats, 4.0, tonic))
        else:
            s.chords = _fill(prog, s.start_beat, s.bars * 4.0)

    fade_start = (total - min(fade_bars, outro)) if fade else None
    return Arrangement(plan=plan, sections=sections, total_bars=total, fade_start_bar=fade_start,
                       fade_bars=min(fade_bars, outro) if fade else 0)


def build_preview_arrangement(plan: Plan) -> Arrangement:
    u = _unit(plan.chorus)
    bars = 12 if u == 12 else 8
    s = Section("chorus", "Refrein (preview)", 0, bars, 0.85, 0.85)
    s.chords = _fill(plan.chorus, 0.0, bars * 4.0)
    return Arrangement(plan=plan, sections=[s], total_bars=bars, fade_start_bar=None, fade_bars=0)


def chord_chart(arr: Arrangement) -> str:
    """Tekstueel akkoordenoverzicht per sectie (voor Akkoorden.txt)."""
    lines = [
        f"{arr.plan.title or 'Backing track'}",
        f"Toonsoort: {arr.plan.key.name} ({arr.plan.key.dutch})  |  Tempo: {arr.bpm} BPM  |  "
        f"Maten: {arr.total_bars}  |  Genre: {lib.GENRES[arr.plan.profile.genre]['label']}",
        "",
    ]
    for s in arr.sections:
        bars_txt = []
        for bar in range(s.bars):
            b0 = (s.start_bar + bar) * 4.0
            names = [tc.chord.symbol for tc in s.chords if b0 <= tc.start < b0 + 4.0 - 1e-6]
            if not names:
                names = ["%"]
            bars_txt.append(" ".join(names))
        lines.append(f"[{s.label}] maat {s.start_bar + 1}-{s.start_bar + s.bars}")
        for i in range(0, len(bars_txt), 4):
            lines.append("  | " + " | ".join(f"{c:<9}" for c in bars_txt[i:i + 4]) + " |")
        lines.append("")
    return "\n".join(lines)
