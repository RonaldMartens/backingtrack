"""Gitaargrepen berekenen voor willekeurige akkoorden (standaardstemming E A D G B E).

Geen vaste lijst: voor elk akkoord worden alle combinaties op de hals doorzocht en beoordeeld op
speelbaarheid (max. 4 vingers, eventueel barré, max. 4 frets breed), juiste bastoon, volledigheid
en klank. Daaruit kiezen we de beste grepen op uiteenlopende posities.
"""
from __future__ import annotations

from itertools import product
from typing import Optional

from .theory import Chord, Key, parse_chord_name, parse_key

TUNING = [40, 45, 50, 55, 59, 64]          # E2 A2 D3 G3 B3 E4, laag → hoog
STRING_NAMES = ["E", "A", "D", "G", "B", "e"]
SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
MAX_FRET = 15


def _required(chord: Chord) -> set[int]:
    pcs = set(chord.pcs())
    if len(pcs) <= 3:
        return pcs
    fifth = (chord.root + chord.fifth) % 12
    req = pcs - {fifth} if chord.fifth == 7 else pcs        # reine kwint mag weg, b5/#5 niet
    if len(req) > 4:                                         # 9/11/13: grondtoon mag ook weg
        req = req - {chord.root}
    return req


def _fingering(frets: list[int]) -> tuple[Optional[dict], list[int], int]:
    """Bepaal barré + vingernummers. Geeft (barre, vingers per snaar (0 = geen), aantal vingers)."""
    fretted = [(s, f) for s, f in enumerate(frets) if f > 0]
    fingers = [0] * 6
    if not fretted:
        return None, fingers, 0
    low = min(f for _, f in fretted)
    at_low = [s for s, f in fretted if f == low]
    barre = None
    rest = fretted
    if len(fretted) > 4 or (len(at_low) >= 3):
        start = at_low[0]
        # barré kan alleen als alle klinkende snaren vanaf de barré minstens op die fret zitten
        if all(frets[s] >= low for s in range(start, 6) if frets[s] >= 0) and \
           not any(frets[s] == 0 for s in range(start, 6)):
            end = max(s for s in range(start, 6) if frets[s] >= 0)
            barre = {"fret": low, "from": start, "to": end}
            for s in at_low:
                fingers[s] = 1
            rest = [(s, f) for s, f in fretted if f != low]
    if barre is None and len(fretted) > 4:
        return None, fingers, 99
    first = 2 if barre else 1
    for i, (s, f) in enumerate(sorted(rest, key=lambda x: (x[1], x[0]))):
        fingers[s] = first + i
    used = (1 if barre else 0) + len(rest)
    return barre, fingers, used


def _score(chord: Chord, frets: list[int], req: set[int]) -> Optional[float]:
    sounding = [(s, f) for s, f in enumerate(frets) if f >= 0]
    pcs = set(chord.pcs())
    if len(sounding) < (3 if len(pcs) <= 2 else 4):
        return None
    # gedempte snaren alleen aan de baskant, plus hooguit de hoge e
    first_sound = sounding[0][0]
    for s in range(first_sound, 6):
        if frets[s] < 0 and s != 5:
            return None
    notes = [TUNING[s] + f for s, f in sounding]
    if notes[0] % 12 != chord.bass_pc:
        return None
    present = {n % 12 for n in notes}
    if not req <= present:
        return None
    fretted = [f for _, f in sounding if f > 0]
    span = (max(fretted) - min(fretted)) if fretted else 0
    if span > 3:
        return None
    barre, _, used = _fingering(frets)
    if used > 4:
        return None
    opens = sum(1 for _, f in sounding if f == 0)
    low = min(fretted) if fretted else 0
    hi = max(fretted) if fretted else 0
    if opens and (low > 3 or hi > 4):
        return None                                   # open snaren met hoge greep: onnatuurlijk
    # open snaren tússen gegrepen noten alleen in de eerste posities (zoals C x32010)
    kinds = ["o" if f == 0 else "f" for _, f in sounding]
    if "fof" in "".join(kinds) and hi > 3:
        return None
    score = 3.0 * len(sounding) - 1.4 * span - 0.25 * low - 0.6 * max(0, low - 9)
    score -= 0.5 * used                                # minder vingers = makkelijker
    fifth_pc = (chord.root + chord.fifth) % 12
    if len(pcs) == 3 and fifth_pc in present:
        score += 2
    doubles = len(notes) - len(present)
    third_pcs = [(chord.root + i) % 12 for i in (3, 4)]
    n_thirds = sum(1 for n in notes if n % 12 in third_pcs)
    score -= 0.5 * max(0, n_thirds - 1)                # verdubbelde terts licht ontmoedigen
    score -= 0.2 * doubles
    if opens and low <= 3:
        score += 2.5                                  # klassieke open greep
    if barre:
        score -= 0.8
    if frets[5] < 0 and len(pcs) < 4:
        score -= 1.5                                  # hoge e dempen is bij gewone drieklanken ongebruikelijk
    # kleine intervallen in de bas klinken modderig
    if len(notes) > 1 and notes[1] - notes[0] < 3:
        score -= 2
    return score


def voicings(chord: Chord, count: int = 4) -> list[dict]:
    req = _required(chord)
    pcs = set(chord.pcs())
    found: dict[tuple, float] = {}
    for base in range(1, MAX_FRET - 3):
        window = range(base, base + 4)
        allow_open = base <= 3
        options = []
        for s in range(6):
            opts = [-1]
            if allow_open and TUNING[s] % 12 in pcs:
                opts.append(0)
            opts += [f for f in window if (TUNING[s] + f) % 12 in pcs]
            options.append(opts)
        for combo in product(*options):
            if combo in found:
                continue
            sc = _score(chord, list(combo), req)
            if sc is not None:
                found[combo] = sc
    ranked = sorted(found.items(), key=lambda kv: -kv[1])

    def pos(fr):
        f = [x for x in fr if x > 0]
        return min(f) if f and (max(f) > 4 or 0 not in fr) else 0

    chosen: list[tuple] = []
    for gap in (3, 2, 1, 0):
        for fr, _ in ranked:
            if len(chosen) >= count:
                break
            if fr in chosen:
                continue
            if all(abs(pos(fr) - pos(c)) >= gap for c in chosen) and (gap or fr not in chosen):
                chosen.append(fr)
        if len(chosen) >= count:
            break
    chosen.sort(key=pos)
    return [_describe(chord, list(fr)) for fr in chosen[:count]]


def _describe(chord: Chord, frets: list[int]) -> dict:
    barre, fingers, _ = _fingering(frets)
    fretted = [f for f in frets if f > 0]
    hi = max(fretted) if fretted else 0
    lo = min(fretted) if fretted else 0
    start = 1 if hi <= 4 else lo                       # diagram begint bij fret 1 of bij de greep
    names = FLAT if any(c in "b" for c in chord.symbol[1:2]) else SHARP
    notes = [names[(TUNING[s] + f) % 12] if f >= 0 else None for s, f in enumerate(frets)]
    label = "open positie" if start == 1 and 0 in frets else f"{start}e positie" if start > 1 else "1e positie"
    return {
        "frets": frets,
        "fingers": fingers,
        "barre": barre,
        "start_fret": start,
        "notes": notes,
        "label": label,
        "tab": "".join("x" if f < 0 else (str(f) if f < 10 else f"({f})") for f in frets),
    }


def chord_sheet(symbols: list[str], key_name: str = "C") -> list[dict]:
    try:
        key = parse_key(key_name)
    except ValueError:
        key = parse_key("C")
    out, seen = [], set()
    for sym in symbols:
        if sym in seen:
            continue
        seen.add(sym)
        try:
            ch = parse_chord_name(sym, key)
            out.append({"symbol": sym, "voicings": voicings(ch)})
        except (ValueError, KeyError):
            out.append({"symbol": sym, "voicings": [], "error": "Onbekend akkoord"})
    return out
