"""Genereert nootdata per instrument (drums, bas, keys, gitaar, pad) op basis van het arrangement."""
from __future__ import annotations

import bisect
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .arranger import Arrangement, Section, TimedChord
from .config import TICKS_PER_BEAT as T
from .theory import Chord, bass_pitch, guitar_voicing, pad_voicing, voice_lead


@dataclass
class Note:
    tick: int
    dur: int
    pitch: int
    vel: int


@dataclass
class TrackData:
    id: str
    name: str
    channel: int
    program: int
    volume: int
    pan: int
    reverb: int
    chorus: int
    notes: list[Note] = field(default_factory=list)
    expression: list[tuple[float, int]] = field(default_factory=list)   # (beat, CC11-waarde)


# GM drumnoten
KICK, SNARE, STICK, CHH, PHH, OHH, CRASH, RIDE, BELL = 36, 38, 37, 42, 44, 46, 49, 51, 53
TOM_HI, TOM_MID, TOM_LO, FLOOR = 50, 47, 45, 41


class Ctx:
    def __init__(self, arr: Arrangement, humanize: bool):
        self.arr = arr
        p = arr.plan.profile
        self.profile = p
        self.rng = random.Random(arr.plan.seed)
        self.humanize = humanize
        self.swing = float(p.swing)
        self.grid16 = p.drum_style in ("lofi", "funk") or p.genre in ("lofi", "funk")
        self.base_vel = float(p.velocity)
        self.color = int(p.color)
        self.timeline: list[tuple[TimedChord, Section]] = [(tc, s) for s in arr.sections for tc in s.chords]
        self.starts = [tc.start for tc, _ in self.timeline]

    # -- tijd & dynamiek ---------------------------------------------------- #
    def swung(self, beat: float) -> float:
        frac = beat % 1.0
        if self.swing <= 0:
            return beat
        if self.grid16:
            if abs(frac - 0.25) < 1e-6 or abs(frac - 0.75) < 1e-6:
                return beat + self.swing * 0.0833
        else:
            if abs(frac - 0.5) < 1e-6:
                return beat + self.swing * 0.1667
            if abs(frac - 0.75) < 1e-6:
                return beat + self.swing * 0.0833
        return beat

    def vel(self, energy: float, factor: float = 1.0) -> float:
        return self.base_vel * (0.58 + 0.52 * energy) * factor

    def add(self, notes: list[Note], beat: float, dur: float, pitch: int, vel: float,
            swing: bool = True, jitter: float = 1.0) -> None:
        b = self.swung(beat) if swing else beat
        tick = int(round(b * T))
        v = vel
        if self.humanize:
            tick += int(self.rng.gauss(0, 5 * jitter))
            v += self.rng.gauss(0, 4)
        tick = max(0, tick)
        notes.append(Note(tick, max(20, int(dur * T)), max(1, min(127, pitch)), int(max(1, min(127, v)))))

    # -- akkoorden ---------------------------------------------------------- #
    def chord_at(self, beat: float) -> Optional[tuple[TimedChord, Section, int]]:
        i = bisect.bisect_right(self.starts, beat + 1e-6) - 1
        if i < 0:
            return None
        tc, s = self.timeline[i]
        if beat >= tc.start + tc.beats - 1e-6:
            return None
        return tc, s, i

    def next_chord(self, index: int) -> Optional[Chord]:
        return self.timeline[index + 1][0].chord if index + 1 < len(self.timeline) else None

    def colored(self, chord: Chord, extra: int = 0) -> Chord:
        return chord.with_color(min(2, self.color + extra))


def _bars(arr: Arrangement):
    for s in arr.sections:
        for b in range(s.bars):
            bar = s.start_bar + b
            yield s, bar, bar * 4.0, b == s.bars - 1


def _is_final_bar(s: Section, bar_idx_last: bool) -> bool:
    return s.final_hit and bar_idx_last


def _intro_silent(s: Section, bar: int) -> bool:
    """In een intro van 8+ maten komen drums en bas pas halverwege binnen."""
    return s.kind == "intro" and s.bars >= 8 and (bar - s.start_bar) < s.bars // 2


def _pattern_events(ctx: Ctx, bar_beat: float, pattern: list[tuple[float, float]], fn: Callable) -> None:
    for pos, dur in pattern:
        beat = bar_beat + pos
        hit = ctx.chord_at(beat)
        if not hit:
            continue
        tc, s, idx = hit
        dur = min(dur, tc.start + tc.beats - beat)
        if dur <= 0.05:
            continue
        fn(beat, dur, tc, s, idx)


def _held_pattern(ctx: Ctx, bar_beat: float) -> list[tuple[float, float]]:
    """Posities waar in deze maat een akkoord begint (plus tel 1), met duur tot het maateinde."""
    pos = {0.0}
    for tc, _ in ctx.timeline:
        if bar_beat < tc.start < bar_beat + 4.0 - 1e-6:
            pos.add(round(tc.start - bar_beat, 4))
    return [(p_, 4.0 - p_) for p_ in sorted(pos)]


# =========================================================================== #
# DRUMS
# =========================================================================== #
def _eighths(v=0.8, off=0.55):
    return [(i * 2, v if i % 2 == 0 else off) for i in range(8)]


def _sixteenths(v=0.75):
    return [(i, v if i % 4 == 0 else (0.6 if i % 2 == 0 else 0.42)) for i in range(16)]


DRUM_PATTERNS: dict[str, dict[str, dict[int, list]]] = {
    "ballad": {
        "intro": {KICK: [(0, 0.8)], RIDE: [(0, 0.5), (4, 0.4), (8, 0.5), (12, 0.4)]},
        "low": {KICK: [(0, 1), (10, 0.7)], STICK: [(4, 0.85), (12, 0.85)], CHH: _eighths(0.7, 0.45)},
        "high": {KICK: [(0, 1), (7, 0.55), (10, 0.85)], SNARE: [(4, 1), (12, 1)],
                 CHH: _eighths(0.75, 0.5), OHH: [(14, 0.55)]},
    },
    "pop": {
        "intro": {KICK: [(0, 0.8), (8, 0.7)], CHH: _eighths(0.5, 0.35)},
        "low": {KICK: [(0, 1), (8, 0.9)], SNARE: [(4, 0.9), (12, 0.9)], CHH: _eighths(0.7, 0.45)},
        "high": {KICK: [(0, 1), (6, 0.7), (8, 0.95)], SNARE: [(4, 1), (12, 1)], CHH: _sixteenths(0.7),
                 OHH: [(14, 0.6)]},
    },
    "rock": {
        "intro": {KICK: [(0, 0.9)], CHH: _eighths(0.55, 0.4)},
        "low": {KICK: [(0, 1), (8, 1), (10, 0.8)], SNARE: [(4, 1), (12, 1)], CHH: _eighths(0.75, 0.55)},
        "high": {KICK: [(0, 1), (6, 0.7), (8, 1), (10, 0.85)], SNARE: [(4, 1), (12, 1)],
                 RIDE: _eighths(0.8, 0.6)},
    },
    "funk": {
        "intro": {KICK: [(0, 0.8)], CHH: _sixteenths(0.5)},
        "low": {KICK: [(0, 1), (3, 0.55), (10, 0.85)], SNARE: [(4, 1), (12, 1), (7, 0.25), (9, 0.25), (15, 0.25)],
                CHH: _sixteenths(0.65)},
        "high": {KICK: [(0, 1), (3, 0.6), (8, 0.7), (10, 0.9)],
                 SNARE: [(4, 1), (12, 1), (7, 0.28), (9, 0.28), (14, 0.25), (15, 0.3)],
                 CHH: [(i, 0.75 if i % 4 == 0 else 0.5) for i in range(16) if i != 14], OHH: [(14, 0.7)]},
    },
    "shuffle": {
        "intro": {KICK: [(0, 0.8)], CHH: [(0, 0.5), (4, 0.5), (8, 0.5), (12, 0.5)]},
        "low": {KICK: [(0, 1), (8, 0.9)], SNARE: [(4, 1), (12, 1)], CHH: _eighths(0.75, 0.5)},
        "high": {KICK: [(0, 1), (6, 0.5), (8, 1)], SNARE: [(4, 1), (12, 1)], RIDE: _eighths(0.85, 0.6)},
    },
    "jazz_swing": {
        "intro": {RIDE: [(0, 0.6), (4, 0.5), (8, 0.6), (12, 0.5)], PHH: [(4, 0.5), (12, 0.5)]},
        "low": {RIDE: [(0, 0.75), (4, 0.7), (6, 0.5), (8, 0.75), (12, 0.7), (14, 0.5)],
                PHH: [(4, 0.65), (12, 0.65)], KICK: [(0, 0.3), (8, 0.25)]},
        "high": {RIDE: [(0, 0.85), (4, 0.8), (6, 0.6), (8, 0.85), (12, 0.8), (14, 0.6)],
                 PHH: [(4, 0.7), (12, 0.7)], KICK: [(0, 0.35), (8, 0.3)]},
    },
    "lofi": {
        "intro": {KICK: [(0, 0.7)], CHH: _eighths(0.4, 0.3)},
        "low": {KICK: [(0, 0.95), (7, 0.6), (10, 0.8)], SNARE: [(4, 0.75), (12, 0.75)], CHH: _eighths(0.5, 0.35)},
        "high": {KICK: [(0, 1), (7, 0.65), (10, 0.85)], SNARE: [(4, 0.85), (12, 0.85)],
                 CHH: [(i, 0.55 if i % 2 == 0 else 0.3) for i in range(16)]},
    },
    "epic": {
        "intro": {FLOOR: [(0, 0.6), (8, 0.5)], RIDE: [(0, 0.35), (8, 0.3)]},
        "low": {KICK: [(0, 1)], TOM_LO: [(6, 0.6), (8, 0.8)], FLOOR: [(0, 0.7), (14, 0.6)], CHH: _eighths(0.45, 0.3)},
        "high": {KICK: [(0, 1), (3, 0.6), (10, 0.8)], SNARE: [(8, 1)], FLOOR: [(0, 0.8), (6, 0.7), (14, 0.75)],
                 TOM_LO: [(12, 0.7)], OHH: _eighths(0.6, 0.45)},
    },
}


def _drum_fill(style: str, energy: float, building: bool) -> list[tuple[int, int, float]]:
    """(stap, noot, sterkte) voor stappen 8-15 van de laatste maat."""
    if style == "jazz_swing":
        return [(10, SNARE, 0.5), (14, SNARE, 0.6), (15, KICK, 0.6)]
    if building:
        return [(s, SNARE, 0.45 + 0.04 * (s - 8)) for s in range(8, 16)]
    if energy < 0.6:
        return [(12, TOM_MID, 0.7), (14, TOM_LO, 0.75), (15, FLOOR, 0.8)]
    return [(8, SNARE, 0.85), (10, TOM_HI, 0.85), (11, TOM_HI, 0.8), (12, TOM_MID, 0.85),
            (13, TOM_MID, 0.8), (14, TOM_LO, 0.9), (15, FLOOR, 0.95)]


def gen_drums(ctx: Ctx) -> TrackData:
    arr, p = ctx.arr, ctx.profile
    style = p.drum_style if p.drum_style in DRUM_PATTERNS else "pop"
    pats = DRUM_PATTERNS[style]
    notes: list[Note] = []
    sections = arr.sections

    for s, bar, b0, last in _bars(arr):
        if _intro_silent(s, bar):
            if bar == s.start_bar + s.bars // 2 - 1:   # cymbal-swell richting de inzet
                ctx.add(notes, b0 + 2.0, 2.0, RIDE, ctx.vel(0.3, 0.5), swing=False)
            continue
        e = s.energy_at(b0)
        if _is_final_bar(s, last):
            ctx.add(notes, b0, 4.0, CRASH, ctx.vel(1.0, 1.05), swing=False, jitter=0)
            ctx.add(notes, b0, 1.0, KICK, ctx.vel(1.0, 1.05), swing=False, jitter=0)
            ctx.add(notes, b0, 4.0, 57, ctx.vel(0.9, 0.8), swing=False, jitter=0)   # crash 2
            continue
        tier = "intro" if s.kind == "intro" or e < 0.4 else ("low" if e < 0.7 else "high")
        pattern = pats[tier]

        idx = sections.index(s)
        has_next = idx + 1 < len(sections)
        nxt = sections[idx + 1] if has_next else None
        do_fill = last and has_next and e >= 0.42 and not (nxt and nxt.final_hit and nxt.bars == 1)
        building = s.kind == "bridge" and (bar - s.start_bar) >= s.bars - 2
        fill = _drum_fill(style, e, building) if (do_fill or building) else []
        fill_steps = {st for st, _, _ in fill}
        if building and not last:
            fill = [(st, SNARE, 0.4 + 0.03 * st) for st in range(0, 16, 2)] + fill
            fill_steps = set(range(8, 16))

        # Crash bij de start van een energieke sectie
        first_bar = bar == s.start_bar
        if first_bar and s.kind not in ("intro", "verse", "interlude") or (first_bar and s.kind == "verse" and e > 0.55):
            ctx.add(notes, b0, 3.0, CRASH, ctx.vel(e, 0.95), swing=False, jitter=0.5)
        if first_bar and s.kind == "intro" and not _intro_silent(s, bar) and s.bars >= 8:
            ctx.add(notes, b0, 3.0, CRASH, ctx.vel(e, 0.7), swing=False)

        for inst, hits in pattern.items():
            for step, strength in hits:
                if step in fill_steps and inst in (SNARE, STICK, KICK, OHH):
                    continue
                if step in fill_steps and inst in (CHH, RIDE) and step >= 12:
                    continue
                if first_bar and inst in (CHH, RIDE, OHH) and step == 0 and s.kind not in ("intro", "verse"):
                    continue
                dur = 0.9 if inst == OHH else 0.25
                ctx.add(notes, b0 + step / 4.0, dur, inst, ctx.vel(e, strength),
                        jitter=0.4 if inst == KICK else 1.0)
        # Jazz: af en toe een snare-comp
        if style == "jazz_swing" and tier != "intro" and ctx.rng.random() < 0.5:
            st = ctx.rng.choice([6, 10, 14, 11])
            ctx.add(notes, b0 + st / 4.0, 0.25, SNARE, ctx.vel(e, 0.35))
        for st, inst, strength in fill:
            ctx.add(notes, b0 + st / 4.0, 0.25, inst, ctx.vel(max(e, 0.6), strength), swing=style != "epic")

    return TrackData("drums", "Drums", 9, 0, 105, 64, 35, 0, notes)


# =========================================================================== #
# BAS
# =========================================================================== #
def gen_bass(ctx: Ctx) -> TrackData:
    arr, p = ctx.arr, ctx.profile
    style = p.bass_style
    notes: list[Note] = []

    def root_of(ch: Chord) -> int:
        return bass_pitch(ch.bass_pc)

    def approach(nxt: Optional[Chord], cur: int) -> int:
        if nxt is None:
            return cur
        target = root_of(nxt)
        return target - 1 if ctx.rng.random() < 0.6 else target + 2 if target + 2 <= 45 else target - 2

    for s, bar, b0, last in _bars(arr):
        if _intro_silent(s, bar):
            continue
        e = s.energy_at(b0)
        if _is_final_bar(s, last):
            hit = ctx.chord_at(b0)
            if hit:
                ctx.add(notes, b0, 4.0, root_of(hit[0].chord), ctx.vel(0.9), swing=False, jitter=0)
            continue
        vf = 0.95

        if style == "root_long":
            if e < 0.7 or s.kind == "intro":
                pat = [(0.0, 4.0)]
            else:
                pat = [(0.0, 2.4), (2.5, 0.5), (3.0, 1.0)]

            def fn(beat, dur, tc, sec, idx, pat=pat):
                r = root_of(tc.chord)
                pos = beat - b0
                pitch = r
                if pos == 2.5:
                    pitch = r + 12 if r + 12 <= 52 else r + tc.chord.fifth
                elif pos == 3.0:
                    nxt = ctx.next_chord(idx)
                    ends_here = tc.start + tc.beats <= b0 + 4.0 + 1e-6
                    pitch = approach(nxt, r) if ends_here and nxt and nxt.root != tc.chord.root else r + tc.chord.fifth
                ctx.add(notes, beat, dur * 0.97, pitch, ctx.vel(e, vf))
            _pattern_events(ctx, b0, pat, fn)

        elif style == "root_fifth":
            pat = [(0.0, 1.45), (1.5, 0.5), (2.0, 1.0), (3.0, 1.0)] if e >= 0.6 else [(0.0, 2.0), (2.0, 2.0)]

            def fn(beat, dur, tc, sec, idx):
                r = root_of(tc.chord)
                pos = beat - b0
                pitch = r
                if pos == 2.0:
                    pitch = r + tc.chord.fifth
                elif pos == 3.0:
                    nxt = ctx.next_chord(idx)
                    pitch = approach(nxt, r) if nxt and tc.start + tc.beats <= b0 + 4 + 1e-6 else r + 12
                ctx.add(notes, beat, dur * 0.92, pitch, ctx.vel(e, vf if pos in (0.0, 2.0) else 0.8))
            _pattern_events(ctx, b0, pat, fn)

        elif style == "eighth_drive":
            pat = [(i * 0.5, 0.45) for i in range(8)]

            def fn(beat, dur, tc, sec, idx):
                r = root_of(tc.chord)
                pos = beat - b0
                pitch = r + 12 if (e >= 0.8 and pos in (1.5, 3.5)) else r
                acc = 1.0 if pos % 1 == 0 else 0.78
                ctx.add(notes, beat, dur, pitch, ctx.vel(e, vf * acc))
            _pattern_events(ctx, b0, pat, fn)

        elif style == "walking":
            def fn(beat, dur, tc, sec, idx):
                ch = tc.chord
                r = root_of(ch)
                n_in_chord = int(round(beat - tc.start))
                ends = abs((tc.start + tc.beats) - (beat + 1.0)) < 1e-6
                third = ch.third if ch.third is not None else 2
                if ends:
                    pitch = approach(ctx.next_chord(idx), r)
                elif n_in_chord % 4 == 0:
                    pitch = r
                elif n_in_chord % 4 == 1:
                    pitch = r + third if ctx.rng.random() < 0.6 else r + 12
                elif n_in_chord % 4 == 2:
                    pitch = r + ch.fifth
                else:
                    pitch = r + ctx.rng.choice([9, 10, 12, third])
                ctx.add(notes, beat, 0.95, pitch, ctx.vel(e, 0.9 if n_in_chord % 2 == 0 else 0.8))
            _pattern_events(ctx, b0, [(i, 1.0) for i in range(4)], fn)

        elif style == "funk_16":
            hits = [(0, 0, 0.45, 1.0), (3, 12, 0.2, 0.75), (6, 0, 0.2, 0.8), (7, 10, 0.2, 0.6),
                    (10, 0, 0.4, 0.95), (12, 7, 0.2, 0.7), (14, 12, 0.2, 0.85), (15, 10, 0.15, 0.6)]
            if e < 0.6:
                hits = [h for h in hits if h[0] in (0, 3, 10, 14)]

            def make(step, iv, d, acc):
                def fn(beat, dur, tc, sec, idx):
                    r = root_of(tc.chord)
                    pitch = r + (iv if iv != 10 or 10 in tc.chord.intervals or tc.chord.is_minor else 7)
                    ctx.add(notes, beat, min(d, dur), pitch, ctx.vel(e, acc))
                return fn
            for step, iv, d, acc in hits:
                _pattern_events(ctx, b0, [(step / 4.0, d)], make(step, iv, d, acc))

        elif style == "blues_shuffle":
            def fn(beat, dur, tc, sec, idx):
                ch = tc.chord
                r = root_of(ch)
                pos = int(round((beat - b0) * 2)) % 8
                seq = [0, 0, 7, 7, 9, 9, 7, 7] if ch.is_minor else [0, 4, 7, 9, 10, 9, 7, 4]
                if e < 0.5:
                    seq = [0, 0, 7, 7, 9, 9, 7, 7]
                ctx.add(notes, beat, 0.45, r + seq[pos], ctx.vel(e, 0.95 if pos % 2 == 0 else 0.75))
            _pattern_events(ctx, b0, [(i * 0.5, 0.5) for i in range(8)], fn)

        else:  # lofi
            pat = [(0.0, 1.4), (1.5, 0.9), (3.0, 0.5), (3.5, 0.5)]

            def fn(beat, dur, tc, sec, idx):
                r = root_of(tc.chord)
                pos = beat - b0
                pitch = {0.0: r, 1.5: r, 2.0: r + tc.chord.fifth, 3.0: r + tc.chord.fifth, 3.5: r + 12}.get(pos, r)
                if pos == 3.5:
                    nxt = ctx.next_chord(idx)
                    if nxt and tc.start + tc.beats <= b0 + 4 + 1e-6:
                        pitch = approach(nxt, r)
                ctx.add(notes, beat, dur * 0.95, pitch, ctx.vel(e, 0.9 if pos == 0 else 0.7))
            _pattern_events(ctx, b0, pat if e >= 0.45 else pat[:1] + [(2.0, 2.0)], fn)

    prog = p.programs.get("bass", 33)
    return TrackData("bass", "Bass", 0, prog, 110, 64, 12, 0, notes)


# =========================================================================== #
# KEYS
# =========================================================================== #
def gen_keys(ctx: Ctx) -> TrackData:
    arr, p = ctx.arr, ctx.profile
    style = p.keys_style
    notes: list[Note] = []
    prev: list[int] = []
    extra = 1 if style in ("rhodes_lofi", "jazz_comp") else 0

    def voicing(ch: Chord, low=55, high=79) -> list[int]:
        nonlocal prev
        c = ctx.colored(ch, extra)
        pcs = c.pcs()
        if style == "jazz_comp" and len(pcs) >= 4:
            pcs = [pc for pc in pcs if pc != c.root % 12] or pcs   # rootless voicing
        v = voice_lead(pcs, low, high, prev or None, center=(low + high) // 2)
        prev = v
        return v

    def play(beat, dur, chord, energy, factor=1.0, left_hand=True, swing=True):
        for n in voicing(chord):
            ctx.add(notes, beat, dur, n, ctx.vel(energy, factor * 0.85), swing=swing)
        if left_hand:
            r = 36 + ((chord.bass_pc - 36) % 12)
            ctx.add(notes, beat, dur, r + 12 if r < 41 else r, ctx.vel(energy, factor * 0.7), swing=swing)

    for s, bar, b0, last in _bars(arr):
        e = s.energy_at(b0)
        if _is_final_bar(s, last):
            hit = ctx.chord_at(b0)
            if hit:
                play(b0, 4.0, hit[0].chord, 0.85, 1.0, True, False)
            continue

        if style == "pad_sustain" or (s.kind == "intro" and style not in ("ballad_arp",)) and e < 0.4:
            restrike = e >= 0.75
            pat = _held_pattern(ctx, b0)
            if restrike and len(pat) == 1:
                pat = [(0.0, 2.0), (2.0, 2.0)]

            def fn(beat, dur, tc, sec, idx):
                play(beat, dur * 0.98, tc.chord, e, 0.85)
            _pattern_events(ctx, b0, pat, fn)

        elif style == "ballad_arp":
            if e < 0.4:
                pat = _held_pattern(ctx, b0)

                def fn(beat, dur, tc, sec, idx):
                    play(beat, dur * 0.98, tc.chord, e, 0.8)
                _pattern_events(ctx, b0, pat, fn)
            else:
                step = 0.5
                order = [0, 1, 2, 3, 2, 1, 2, 3]

                def fn(beat, dur, tc, sec, idx):
                    v = voicing(tc.chord, 57, 81)
                    i = int(round((beat - b0) / step)) % len(order)
                    if abs(beat - tc.start) < 1e-6 or abs(beat - b0) < 1e-6:
                        r = 36 + ((tc.chord.bass_pc - 36) % 12)
                        ctx.add(notes, beat, min(tc.start + tc.beats - beat, 4.0) * 0.98, r + 12 if r < 41 else r,
                                ctx.vel(e, 0.7))
                        if e >= 0.8:
                            for n in v:
                                ctx.add(notes, beat, 1.0, n, ctx.vel(e, 0.6))
                    pitch = v[order[i] % len(v)]
                    if order[i] >= len(v):
                        pitch += 12
                    ctx.add(notes, beat, 1.2, pitch, ctx.vel(e, 0.72 + (0.1 if i % 2 == 0 else 0)))
                _pattern_events(ctx, b0, [(i * step, step) for i in range(8)], fn)

        elif style == "comp_offbeat":
            pat = [(i * 0.5, 0.4) for i in range(8)] if e >= 0.75 else [(0.0, 0.9), (1.0, 0.9), (2.0, 0.9), (3.0, 0.9)]
            if e < 0.45:
                pat = [(0.0, 1.9), (2.0, 1.9)]

            def fn(beat, dur, tc, sec, idx):
                on = (beat - b0) % 1 == 0
                play(beat, dur, tc.chord, e, 0.95 if on else 0.75, left_hand=on and (beat - b0) % 2 == 0)
            _pattern_events(ctx, b0, pat, fn)

        elif style == "jazz_comp":
            options = [[(0.0, 0.7), (1.5, 0.45)], [(0.5, 0.4), (2.0, 0.8)], [(1.0, 0.45), (2.5, 0.8)],
                       [(0.0, 1.2), (3.5, 0.4)], [(1.5, 0.45), (3.0, 0.6)]]
            pat = ctx.rng.choice(options)

            def fn(beat, dur, tc, sec, idx):
                play(beat, dur, tc.chord, e, 0.8, left_hand=False)
            _pattern_events(ctx, b0, pat, fn)

        elif style == "rhodes_lofi":
            def fn(beat, dur, tc, sec, idx):
                ant = 0.25 if beat > 0.5 and abs(beat - tc.start) < 1e-6 and ctx.rng.random() < 0.5 else 0.0
                play(beat - ant, dur * 0.95 + ant, tc.chord, e, 0.75, swing=False)
            _pattern_events(ctx, b0, _held_pattern(ctx, b0), fn)
            if e >= 0.6 and ctx.rng.random() < 0.4:
                hit = ctx.chord_at(b0 + 2.5)
                if hit:
                    play(b0 + 2.5, 0.4, hit[0].chord, e, 0.55, left_hand=False)

        elif style == "funk_stabs":
            steps = [2, 6, 7, 10, 14] if e >= 0.6 else [2, 10]

            def fn(beat, dur, tc, sec, idx):
                play(beat, 0.18, tc.chord, e, 0.85, left_hand=False)
            _pattern_events(ctx, b0, [(st / 4.0, 0.25) for st in steps], fn)

        else:  # blues_comp
            pat = [(1.0, 0.4), (3.0, 0.4)] + ([(2.5, 0.3), (3.5, 0.3)] if e >= 0.7 else [])

            def fn(beat, dur, tc, sec, idx):
                play(beat, dur, tc.chord, e, 0.8, left_hand=False)
            _pattern_events(ctx, b0, pat, fn)

    prog = p.programs.get("keys", 4)
    return TrackData("keys", "Keys", 1, prog, 92, 48, 45, 15, notes)


# =========================================================================== #
# GITAAR
# =========================================================================== #
def gen_guitar(ctx: Ctx) -> TrackData:
    arr, p = ctx.arr, ctx.profile
    style = p.guitar_style
    notes: list[Note] = []

    def strum(beat, dur, pitches, energy, factor, down=True, spread=0.025):
        order = pitches if down else list(reversed(pitches))[: max(3, len(pitches) - 2)]
        for i, n in enumerate(order):
            ctx.add(notes, beat + i * spread, max(0.1, dur - i * spread), n, ctx.vel(energy, factor * (1 - 0.03 * i)))

    for s, bar, b0, last in _bars(arr):
        e = s.energy_at(b0)
        if _is_final_bar(s, last):
            hit = ctx.chord_at(b0)
            if hit:
                strum(b0, 4.0, guitar_voicing(hit[0].chord), 0.85, 0.95, spread=0.06)
            continue

        if style in ("arpeggio", "clean_arp_delay"):
            step = 0.5 if e >= 0.4 else 1.0
            order = [0, 2, 3, 4, 5, 4, 3, 2] if step == 0.5 else [0, 3, 4, 5]
            delay = style == "clean_arp_delay"

            def fn(beat, dur, tc, sec, idx):
                v = guitar_voicing(tc.chord)
                i = int(round((beat - b0) / step)) % len(order)
                pitch = v[order[i] % len(v)]
                vel = ctx.vel(e, (0.78 if i % 2 == 0 else 0.66) * (0.9 if delay else 1.0))
                ctx.add(notes, beat, 1.5 if step == 0.5 else 2.0, pitch, vel)
                if delay:
                    echo_beat = beat + 0.75
                    if echo_beat < arr.total_beats:
                        ctx.add(notes, echo_beat, 0.9, pitch, vel * 0.42, swing=False)
            _pattern_events(ctx, b0, [(i * step, step) for i in range(int(4 / step))], fn)

        elif style == "strum_8":
            if e < 0.45:
                pat = [(0.0, 2.0, True), (2.0, 2.0, True)]
            else:
                pat = [(0.0, 1.0, True), (1.0, 0.5, True), (1.5, 1.0, False), (2.5, 0.5, False),
                       (3.0, 0.5, True), (3.5, 0.5, False)]
            for pos, d, down in pat:
                def fn(beat, dur, tc, sec, idx, down=down):
                    strum(beat, dur * 0.95, guitar_voicing(tc.chord), e, 0.85 if down else 0.65, down)
                _pattern_events(ctx, b0, [(pos, d)], fn)

        elif style == "power_8":
            muted = e < 0.7

            def fn(beat, dur, tc, sec, idx):
                r = 40 + ((tc.chord.bass_pc - 40) % 12)
                if r > 47:
                    r -= 12
                chord = [r, r + 7, r + 12]
                on = (beat - b0) % 1 == 0
                strum(beat, 0.22 if muted else 0.45, chord, e, (0.8 if on else 0.7) * (0.85 if muted else 1.0),
                      spread=0.008)
            _pattern_events(ctx, b0, [(i * 0.5, 0.5) for i in range(8)], fn)

        elif style == "funk_chops":
            accents = {2, 6, 10, 13} if e < 0.6 else {2, 6, 10, 13, 14}

            def fn(beat, dur, tc, sec, idx):
                st = int(round((beat - b0) * 4))
                c = ctx.colored(tc.chord, 1)
                v = voice_lead(c.pcs()[:4], 60, 79, None, center=69)[-3:]
                if st in accents:
                    strum(beat, 0.12, v, e, 0.85, down=st % 2 == 0, spread=0.006)
                elif st % 2 == 1 and e >= 0.6:
                    ctx.add(notes, beat, 0.05, v[-1], ctx.vel(e, 0.28))
            _pattern_events(ctx, b0, [(i / 4.0, 0.25) for i in range(16)], fn)

        elif style == "blues_shuffle":
            def fn(beat, dur, tc, sec, idx):
                r = 40 + ((tc.chord.root - 40) % 12)
                if r > 47:
                    r -= 12
                pos = int(round((beat - b0) * 2)) % 4
                top = r + (7 if pos < 2 else 9)
                if e >= 0.8 and pos >= 2 and (bar % 2 == 1):
                    top = r + 10
                ctx.add(notes, beat, 0.42, r, ctx.vel(e, 0.8 if pos % 2 == 0 else 0.62))
                ctx.add(notes, beat, 0.42, top, ctx.vel(e, 0.78 if pos % 2 == 0 else 0.6))
            _pattern_events(ctx, b0, [(i * 0.5, 0.5) for i in range(8)], fn)

        elif style == "jazz_quarters":
            def fn(beat, dur, tc, sec, idx):
                c = ctx.colored(tc.chord, 1)
                r = 40 + ((c.bass_pc - 40) % 12)
                third = c.third if c.third is not None else 5
                sev = 11 if 11 in c.intervals else 10 if 10 in c.intervals else 9
                shell = [r, r + sev, r + 12 + third]
                on2_4 = int(round(beat - b0)) % 2 == 1
                strum(beat, 0.55, shell, e, 0.7 if on2_4 else 0.62, spread=0.01)
            _pattern_events(ctx, b0, [(float(i), 1.0) for i in range(4)], fn)

        else:  # lofi_pluck
            n_hits = 2 if e < 0.6 else 3
            positions = sorted(ctx.rng.sample([0.0, 0.5, 1.5, 2.0, 2.5, 3.0, 3.5], n_hits))

            def fn(beat, dur, tc, sec, idx):
                v = guitar_voicing(ctx.colored(tc.chord, 1))
                pitch = ctx.rng.choice(v[-3:])
                ctx.add(notes, beat, 1.2, pitch, ctx.vel(e, 0.6))
            _pattern_events(ctx, b0, [(pos, 1.0) for pos in positions], fn)

    prog = p.programs.get("guitar", 27)
    return TrackData("guitar", "Guitar", 2, prog, 88, 84, 55, 25, notes)


# =========================================================================== #
# PAD
# =========================================================================== #
def gen_pad(ctx: Ctx) -> TrackData:
    arr, p = ctx.arr, ctx.profile
    style = p.pad_style
    notes: list[Note] = []
    expression: list[tuple[float, int]] = [(0.0, 100)]
    prev: Optional[list[int]] = None
    held: dict[int, list] = {}   # pitch -> [start_beat, end_beat, vel]

    factor = {"wide": 0.78, "swell": 0.8, "soft": 0.6}.get(style, 0.75)

    def flush(pitch):
        st, en, v = held.pop(pitch)
        ctx.add(notes, st, en - st, pitch, v, swing=False, jitter=0.3)

    for tc, s in ctx.timeline:
        e = s.energy_at(tc.start)
        if s.kind == "intro":
            e = max(e, 0.55)   # pad draagt het intro
        v = pad_voicing(tc.chord, prev)
        prev = v
        vel = ctx.vel(e, factor)
        end = tc.start + tc.beats + (2.0 if s.final_hit and tc is s.chords[-1] else 0.02)
        # Gelijke noten doorhouden (legato), andere afsluiten
        for pitch in list(held.keys()):
            if pitch not in v:
                flush(pitch)
        for pitch in v:
            if pitch in held and abs(held[pitch][1] - tc.start) < 0.05:
                held[pitch][1] = end
            else:
                if pitch in held:
                    flush(pitch)
                held[pitch] = [tc.start, end, vel]
        if style == "swell" and tc.beats >= 2:
            expression.append((tc.start, 55))
            expression.append((tc.start + tc.beats * 0.6, 112))
    for pitch in list(held.keys()):
        flush(pitch)

    # Swell aan het begin van elke sectie (ook voor 'wide')
    if style == "wide":
        for s in arr.sections:
            if s.kind in ("chorus", "bridge", "outro"):
                expression.append((s.start_beat, 85))
                expression.append((s.start_beat + 4.0, 115))
            else:
                expression.append((s.start_beat, 100))
    expression.sort()
    prog = p.programs.get("pad", 89)
    return TrackData("pad", "Pad", 3, prog, 82, 64, 85, 50, notes, expression)


GENERATORS = {
    "drums": gen_drums,
    "bass": gen_bass,
    "keys": gen_keys,
    "guitar": gen_guitar,
    "pad": gen_pad,
}


def generate_tracks(arr: Arrangement, instruments: list[str], humanize: bool = True) -> list[TrackData]:
    tracks = []
    for inst in ["drums", "bass", "keys", "guitar", "pad"]:
        if inst in instruments:
            ctx = Ctx(arr, humanize)   # eigen RNG per spoor -> reproduceerbaar per seed
            ctx.rng.seed(f"{arr.plan.seed}-{inst}")
            tracks.append(GENERATORS[inst](ctx))
    return tracks
