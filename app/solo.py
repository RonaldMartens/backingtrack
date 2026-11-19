"""Gitaarsolo's: melodische leadlijnen over gekozen secties van een al gegenereerd nummer.

Werkwijze: het arrangement wordt uit session.json opnieuw opgebouwd (zelfde seed = zelfde akkoorden),
daarna krijgt elke gekozen sectie een eigen solo. Elke solo wordt een apart MIDI- én audiobestand dat
op maat 1 begint (stilte tot de solo), zodat je hem in Logic direct op maat 1 kunt neerzetten.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

from .arranger import Arrangement, Section
from .config import TICKS_PER_BEAT as T
from .generators import Note, TrackData

# Klankkleur -> General MIDI-programma
TONES = {
    "overdrive": (29, "Overdrive"),
    "distortion": (30, "Distortion"),
    "clean": (27, "Clean"),
    "jazz": (26, "Jazzgitaar"),
}
STYLES = {
    # dichtheid (0..1), kans op bend, kans op snelle loopjes
    "melodisch": (0.30, 0.22, 0.05),
    "bluesy": (0.50, 0.45, 0.15),
    "virtuoos": (0.78, 0.30, 0.45),
}

PENTA_MINOR = [0, 3, 5, 7, 10]
PENTA_MAJOR = [0, 2, 4, 7, 9]
BLUES_MINOR = [0, 3, 5, 6, 7, 10]
NAT_MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]

LOW, HIGH = 57, 88          # A3 .. E6: het bereik waarin een leadgitaar 'zingt'
BEND_FULL = 8191            # hele toon bij standaard pitch-bend-bereik van ±2 halve tonen


def auto_tone(genre: str, mood: str) -> str:
    if genre in ("jazz", "lofi"):
        return "jazz"
    if genre == "funk" or (genre == "pop" and mood == "happy"):
        return "clean"
    return "overdrive"


def auto_style(genre: str) -> str:
    if genre in ("blues", "rock"):
        return "bluesy"
    if genre in ("funk",):
        return "virtuoos"
    return "melodisch"


def scale_for(genre: str, minor: bool, style: str) -> list[int]:
    """Toonladder (halve tonen t.o.v. de grondtoon van de toonsoort)."""
    if genre == "blues":
        return BLUES_MINOR if minor else sorted(set(PENTA_MAJOR + [3]))   # majeur-blues: met b3 als blue note
    if style == "bluesy" or genre == "rock":
        return PENTA_MINOR if minor else PENTA_MAJOR
    if genre == "jazz":
        return NAT_MINOR if minor else MAJOR
    # melodisch: volledige ladder, maar pentatonisch voor snelle loopjes (zie _run)
    return NAT_MINOR if minor else MAJOR


@dataclass
class _Ev:
    beat: float
    dur: float
    pitch: int
    vel: float
    bend: int = 0          # 0, 1 of 2 halve tonen omhoog buigen naar de doeltoon
    vibrato: bool = False


class SoloBuilder:
    def __init__(self, arr: Arrangement, section: Section, style: str, seed: int, number: int):
        self.arr = arr
        self.sec = section
        self.style = style
        self.rng = random.Random(seed * 31 + number * 7919 + section.start_bar)
        p = arr.plan.profile
        key = arr.plan.key
        self.key_root = key.root
        self.minor = key.minor
        self.genre = p.genre
        self.swing = float(p.swing)
        self.density, self.p_bend, self.p_run = STYLES[style]
        ivs = scale_for(p.genre, key.minor, style)
        pcs = {(key.root + i) % 12 for i in ivs}
        self.pool = [m for m in range(LOW, HIGH + 1) if m % 12 in pcs]
        penta = {(key.root + i) % 12 for i in (PENTA_MINOR if key.minor else PENTA_MAJOR)}
        self.penta_pool = [m for m in range(LOW, HIGH + 1) if m % 12 in penta]
        # per solo een eigen ligging: tweede solo iets hoger begint, enz.
        self.base_center = 67 + (number - 1) % 3 * 3
        self.idx = self._nearest_idx(self.base_center)

    # ----------------------------------------------------------------- hulp
    def _nearest_idx(self, pitch: int, pool: Optional[list[int]] = None) -> int:
        pool = pool or self.pool
        return min(range(len(pool)), key=lambda i: abs(pool[i] - pitch))

    def chord_at(self, beat: float):
        for tc in self.sec.chords:
            if tc.start <= beat + 1e-6 < tc.start + tc.beats:
                return tc.chord
        return self.sec.chords[-1].chord if self.sec.chords else None

    def chord_tone(self, pitch: int, beat: float, prefer_root: bool = False) -> int:
        ch = self.chord_at(beat)
        if ch is None:
            return pitch
        pcs = [ch.root % 12]
        if not prefer_root:
            if ch.third is not None:
                pcs.append((ch.root + ch.third) % 12)
            pcs.append((ch.root + ch.fifth) % 12)
        cands = [m for m in range(LOW, HIGH + 1) if m % 12 in pcs]
        return min(cands, key=lambda m: (abs(m - pitch), m))

    # ----------------------------------------------------------- ritme
    def _rhythm(self, length: float, density: float) -> list[tuple[float, float]]:
        """(start, duur) binnen een frase van `length` beats; eindigt op een lange noot."""
        r = self.rng
        out: list[tuple[float, float]] = []
        pos = 0.0 if r.random() < 0.6 else 0.5            # soms een opmaat
        end_long = r.choice([1.0, 1.5, 2.0]) if density < 0.6 else r.choice([1.0, 1.5])
        body_end = length - end_long
        while pos < body_end - 1e-6:
            on_beat = abs(pos - round(pos)) < 1e-6
            x = r.random()
            if on_beat and x < density * 0.45 and pos + 1 <= body_end:
                if r.random() < 0.55:                       # vier zestienden
                    out += [(pos + i * 0.25, 0.25) for i in range(4)]
                else:                                       # triool
                    out += [(pos + i / 3, 1 / 3) for i in range(3)]
                pos += 1.0
            elif x < 0.35 + density * 0.4:
                out.append((pos, 0.5)); pos += 0.5
            elif x < 0.75 + density * 0.1:
                d = 1.0 if on_beat or pos + 1.0 > body_end else 1.5
                out.append((pos, min(d, body_end - pos))); pos += d
            elif on_beat and pos + 2 <= body_end:
                out.append((pos, 1.5)); out.append((pos + 1.5, 0.5)); pos += 2.0
            else:
                pos += 0.5                                  # adempauze
        pos = min(pos, body_end) if out else body_end
        out.append((pos, length - pos))
        return [(s, d) for s, d in out if d > 0.05]

    # ----------------------------------------------------------- melodie
    def _step(self, target: int, run_dir: int) -> int:
        r = self.rng
        if run_dir:
            return run_dir
        steps = [-2, -1, -1, 1, 1, 2, -3, 3, 0]
        weights = [1.2, 3, 3, 3, 3, 1.2, 0.5, 0.5, 0.6]
        cur = self.pool[self.idx]
        bias = 1 if target > cur + 3 else -1 if target < cur - 3 else 0
        if bias:
            weights = [w * (1.8 if s * bias > 0 else 0.6) for s, w in zip(steps, weights)]
        return r.choices(steps, weights)[0]

    def phrase(self, start: float, length: float, density: float, target: int,
               rhythm: Optional[list[tuple[float, float]]] = None, last: bool = False) -> tuple[list[_Ev], list]:
        r = self.rng
        rhythm = rhythm or self._rhythm(length, density)
        evs: list[_Ev] = []
        run_dir = 0
        run_left = 0
        for i, (off, dur) in enumerate(rhythm):
            beat = start + off
            final = i == len(rhythm) - 1
            if dur <= 0.34 and run_left == 0 and r.random() < 0.5 + self.p_run:
                run_dir = r.choice([-1, 1]) if self.pool[self.idx] not in (self.pool[0], self.pool[-1]) else (
                    1 if self.idx == 0 else -1)
                run_left = r.randint(3, 6)
            new = self.idx + self._step(target, run_dir if run_left else 0)
            if new < 2 or new > len(self.pool) - 3:            # loopje tegen de rand: omkeren
                run_dir = -run_dir
                new = self.idx + (run_dir or (1 if new < 2 else -1))
            self.idx = max(0, min(len(self.pool) - 1, new))
            if run_left:
                run_left -= 1
                if run_left == 0:
                    run_dir = 0
            pitch = self.pool[self.idx]
            strong = abs(off - round(off)) < 1e-6 and (round(start + off) % 2 == 0)
            if final:
                pitch = self.chord_tone(pitch, beat, prefer_root=last)
            elif (strong and dur >= 0.5) or dur >= 1.0:
                pitch = self.chord_tone(pitch, beat)
            pitch = max(LOW, min(HIGH, pitch))
            self.idx = self._nearest_idx(pitch)
            accent = 1.08 if strong else 0.95
            ev = _Ev(beat, dur, pitch, accent)
            if dur >= 0.75 and i > 0 and r.random() < self.p_bend:
                if pitch - 2 in self.pool:
                    ev.bend = 2
                elif pitch - 1 >= LOW and (self.style == "bluesy" or self.genre == "blues"):
                    ev.bend = 1
            ev.vibrato = dur >= 0.9 or final
            evs.append(ev)
        return evs, rhythm

    def build(self) -> list[_Ev]:
        sec = self.sec
        total = sec.bars * 4.0
        r = self.rng
        evs: list[_Ev] = []
        unit = 8.0 if sec.bars >= 4 else 4.0              # frases van 2 maten
        n = max(1, int(total // unit))
        prev_rhythm = None
        for k in range(n):
            t = k / max(1, n - 1)                          # 0 -> 1 door de solo heen: opbouw
            last = k == n - 1
            start = sec.start_beat + k * unit
            density = min(0.95, self.density * (0.65 + 0.7 * t))
            target = self.base_center + int(round(9 * t)) + r.choice([-2, 0, 2])
            length = unit - (0.0 if last else r.choice([0.5, 1.0, 1.5, 2.0]))   # ruimte om te ademen
            if last:
                length = unit - 0.0
            reuse = prev_rhythm if (k % 2 == 1 and prev_rhythm and r.random() < 0.6 and not last) else None
            if reuse and max(s + d for s, d in reuse) > length:
                reuse = None
            # vraag & antwoord: frase 2, 4 … gebruiken vaak het ritme van de vorige frase
            ph, rhythm = self.phrase(start, length, density, target, reuse, last)
            if last and len(ph) > 1:
                ph[-1].dur = max(ph[-1].dur, min(4.0, sec.end_beat - ph[-1].beat - 0.25))
            evs += ph
            prev_rhythm = rhythm
        # dynamiek: opbouw door de solo
        for ev in evs:
            t = (ev.beat - sec.start_beat) / max(1.0, total)
            ev.vel = ev.vel * (88 + 22 * t)
        return evs


def _swung(beat: float, swing: float) -> float:
    if swing > 0 and abs(beat % 1.0 - 0.5) < 1e-6:
        return beat + swing * 0.1667
    return beat


def solo_track(arr: Arrangement, section: Section, number: int, style: str, tone: str, seed: int,
               humanize: bool = True) -> TrackData:
    builder = SoloBuilder(arr, section, style, seed, number)
    evs = builder.build()
    program, tone_label = TONES[tone]
    track = TrackData(id="solo", name=f"Solo {number} - {section.label}", channel=5, program=program,
                      volume=104, pan=64, reverb=58 if tone != "jazz" else 40, chorus=12)
    track.expression = [(0.0, 110)]
    spb = arr.seconds_per_beat
    rng = random.Random(seed + number)
    bends: list[tuple[int, int]] = [(0, 0)]
    ticks = [max(0, int(round(_swung(ev.beat, builder.swing) * T)) + (int(rng.gauss(0, 4)) if humanize else 0))
             for ev in evs]
    for i in range(1, len(ticks)):
        ticks[i] = max(ticks[i], ticks[i - 1] + 30)
    for i, ev in enumerate(evs):
        tick = ticks[i]
        dur_beats = ev.dur * (0.96 if ev.dur < 1 else 0.98)
        dur = max(20, int(dur_beats * T))
        if i + 1 < len(evs):
            dur = max(20, min(dur, ticks[i + 1] - tick - 6))   # monofoon: nooit over de volgende noot heen
        vel = int(max(40, min(124, ev.vel + (rng.gauss(0, 4) if humanize else 0))))
        played = ev.pitch - ev.bend
        track.notes.append(Note(tick, dur, played, vel))
        # pitch bend: eerst neutraal, dan omhoog buigen, vibrato, aan het eind weer terug
        bends.append((tick, 0))
        base = 0
        if ev.bend:
            full = BEND_FULL if ev.bend == 2 else BEND_FULL // 2
            b0 = tick + int(dur * 0.12)
            b1 = tick + int(min(dur * 0.45, 0.5 * T))
            steps = 6
            for s in range(1, steps + 1):
                x = s / steps
                bends.append((b0 + int((b1 - b0) * x), int(full * math.sin(x * math.pi / 2))))
            base = full
        if ev.vibrato and dur / T * spb > 0.35:
            v_start = tick + int(dur * (0.5 if ev.bend else 0.35))
            rate = 5.2                                         # Hz
            depth = 900 if ev.bend else 700                    # ~ kwart halve toon
            period = (1.0 / rate) / spb * T                    # ticks
            tt = v_start
            k = 0
            while tt < tick + dur - 10:
                ramp = min(1.0, (tt - v_start) / max(1.0, period * 2))
                val = base + int(depth * ramp * math.sin(2 * math.pi * k / 8))
                bends.append((int(tt), max(-8192, min(8191, val))))
                tt += period / 8
                k += 1
        bends.append((tick + dur + 2, 0))   # pas ná de note-off terug
    track.bends = bends
    return track
