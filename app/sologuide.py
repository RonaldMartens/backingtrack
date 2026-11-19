"""Soloschema: welke toonladders passen over het nummer, posities op de hals en doelnoten per akkoord."""
from __future__ import annotations

from typing import Optional

from .theory import Chord, Key, parse_chord_name, parse_key

OPEN = [40, 45, 50, 55, 59, 64]      # E A D G B E (laag -> hoog)
MAX_FRET = 17

# id: (naam, intervallen, gradenlabels)
SCALES: dict[str, tuple[str, list[int], list[str]]] = {
    "penta_minor": ("Mineur pentatonisch", [0, 3, 5, 7, 10], ["1", "b3", "4", "5", "b7"]),
    "blues": ("Blues-toonladder", [0, 3, 5, 6, 7, 10], ["1", "b3", "4", "b5", "5", "b7"]),
    "aeolian": ("Natuurlijk mineur (Aeolisch)", [0, 2, 3, 5, 7, 8, 10], ["1", "2", "b3", "4", "5", "b6", "b7"]),
    "dorian": ("Dorisch", [0, 2, 3, 5, 7, 9, 10], ["1", "2", "b3", "4", "5", "6", "b7"]),
    "harmonic": ("Harmonisch mineur", [0, 2, 3, 5, 7, 8, 11], ["1", "2", "b3", "4", "5", "b6", "7"]),
    "penta_major": ("Majeur pentatonisch", [0, 2, 4, 7, 9], ["1", "2", "3", "5", "6"]),
    "major_blues": ("Majeur-blues", [0, 2, 3, 4, 7, 9], ["1", "2", "b3", "3", "5", "6"]),
    "ionian": ("Majeur (Ionisch)", [0, 2, 4, 5, 7, 9, 11], ["1", "2", "3", "4", "5", "6", "7"]),
    "mixolydian": ("Mixolydisch", [0, 2, 4, 5, 7, 9, 10], ["1", "2", "3", "4", "5", "6", "b7"]),
}
SEVEN = {"aeolian", "dorian", "harmonic", "ionian", "mixolydian"}
# Pentatonische/blues-ladders: posities op basis van deze 5-tonige ladder (+ extra 'blue note')
BOX_BASE = {"penta_minor": "penta_minor", "blues": "penta_minor", "penta_major": "penta_major",
            "major_blues": "penta_major"}


def _pcs(scale_id: str, root: int) -> list[int]:
    return [(root + i) % 12 for i in SCALES[scale_id][1]]


def _chord_tones(ch: Chord) -> list[tuple[int, str]]:
    tones = [(ch.root % 12, "grondtoon")]
    if ch.third is not None:
        tones.append(((ch.root + ch.third) % 12, "terts"))
    tones.append(((ch.root + ch.fifth) % 12, "kwint"))
    for i, role in ((10, "septiem"), (11, "grote septiem"), (9, "sext")):
        if i in ch.intervals:
            tones.append(((ch.root + i) % 12, role))
            break
    return tones


def _boxes(scale_id: str, root: int) -> list[dict]:
    """Posities op de hals: pentatonisch = 2 noten per snaar, 7-tonig = 3 noten per snaar."""
    base = BOX_BASE.get(scale_id, scale_id)
    pcs = set(_pcs(base, root))
    per = 2 if len(pcs) == 5 else 3
    pool = [p for p in range(OPEN[0], OPEN[-1] + MAX_FRET + 1) if p % 12 in pcs]
    extra = set(_pcs(scale_id, root)) - pcs          # blue note(s)
    out = []
    for i, p in enumerate(pool):
        if p - OPEN[0] > 11:
            break
        notes, ok = [], True
        for s in range(6):
            chunk = pool[i + s * per: i + (s + 1) * per]
            if len(chunk) < per:
                ok = False
                break
            for q in chunk:
                f = q - OPEN[s]
                if f < 0 or f > MAX_FRET:
                    ok = False
                notes.append([s, f, q % 12])
        if not ok:
            continue
        lo, hi = min(n[1] for n in notes), max(n[1] for n in notes)
        if hi - lo > 5:          # onspeelbare rek: overslaan
            continue
        for s in range(6):
            for f in range(lo, hi + 1):
                if (OPEN[s] + f) % 12 in extra:
                    notes.append([s, f, (OPEN[s] + f) % 12])
        out.append({"from": lo, "to": hi, "start_pc": p % 12, "root_on_low_e": p % 12 == root, "notes": notes})
    out.sort(key=lambda b: b["from"])
    for n, b in enumerate(out, start=1):
        b["number"] = n
    return out


def _choose_scales(key: Key, chords: list[Chord], genre: str) -> list[tuple[str, str]]:
    """(scale_id, waarom) – de eerste is de basis die over het hele nummer werkt."""
    all_pcs = {pc for ch in chords for pc, _ in _chord_tones(ch)}
    r = key.root
    has = lambda iv: (r + iv) % 12 in all_pcs  # noqa: E731
    bluesy = genre in ("blues", "rock")
    out: list[tuple[str, str]] = []
    if key.minor:
        out.append(("penta_minor", "De veilige basis: werkt over (bijna) het hele nummer. Vijf tonen, geen ‘foute’ noten."))
        if bluesy:
            out.append(("blues", "Pentatonisch + de b5 als ‘blue note’: kort aantikken als doorgangsnoot, niet op blijven hangen."))
        if has(9) and not has(8):
            out.append(("dorian", f"Het nummer heeft een grote sext ({key.note_name(r + 9)}), bv. een majeur IV-akkoord: Dorisch klinkt dan precies goed."))
        else:
            out.append(("aeolian", "De volledige mineurtoonladder: meer melodie dan pentatonisch, met de 2 en b6 voor spanning."))
        if has(11):
            out.append(("harmonic", f"Er zit een majeur V-akkoord in (met {key.note_name(r + 11)}): speel over dát akkoord harmonisch mineur."))
    else:
        out.append(("penta_major", "De veilige basis: werkt over (bijna) het hele nummer. Vrolijk en open."))
        if has(10):
            out.append(("mixolydian", f"Het nummer heeft een b7 ({key.note_name(r + 10)}), bv. een bVII-akkoord: Mixolydisch past dan."))
        else:
            out.append(("ionian", "De volledige majeurtoonladder: meer melodie, met de 4 en 7 als spanningsnoten."))
        if bluesy:
            out.append(("major_blues", "Majeur pentatonisch + de b3: die even naar de 3 buigen geeft het bluesgevoel."))
            out.append(("penta_minor", "Mineur pentatonisch op dezelfde grondtoon: de stoere bluesrock-kleur (b3 tegen een majeur akkoord)."))
    return out


def _clashes(pcs: set[int], ch: Chord) -> bool:
    """Botst een ladder met dit akkoord? Praktijkregels: geen kleine terts tegen een grote terts (en andersom),
    geen halve toon boven de grondtoon (behalve b9 op een dominant-akkoord), geen b7 tegen een grote septiem
    en geen grote septiem tegen een b7."""
    r = ch.root % 12
    dominant = ch.third == 4 and 10 in ch.intervals
    if ch.third == 4 and (r + 3) % 12 in pcs:
        return True
    if ch.third == 3 and (r + 4) % 12 in pcs:
        return True
    if not dominant and (r + 1) % 12 in pcs:
        return True
    if 10 in ch.intervals and (r + 11) % 12 in pcs:
        return True
    if 11 in ch.intervals and (r + 10) % 12 in pcs:
        return True
    return False


def _fits(scale_id: str, root: int, chords: list[Chord]) -> bool:
    pcs = set(_pcs(scale_id, root)) - ({(root + 6) % 12} if scale_id == "blues" else set()) \
        - ({(root + 3) % 12} if scale_id == "major_blues" else set())   # blue notes zijn doorgangsnoten
    return not any(_clashes(pcs, ch) for ch in chords)


def solo_guide(key_name: str, sections: list[dict], genre: str = "") -> dict:
    key = parse_key(key_name)
    parsed: dict[str, Optional[Chord]] = {}
    for s in sections:
        for sym in s.get("chords", []):
            if sym not in parsed:
                try:
                    parsed[sym] = parse_chord_name(sym, key)
                except (ValueError, KeyError):
                    parsed[sym] = None
    chords = [c for c in parsed.values() if c is not None]
    chosen = _choose_scales(key, chords, genre)
    main_pcs = set(_pcs(chosen[0][0], key.root))

    scales = []
    for sid, why in chosen:
        name, ivs, labels = SCALES[sid]
        scales.append({
            "id": sid, "name": f"{key.note_name(key.root)} {name[0].lower() + name[1:]}",
            "short": name, "why": why, "pcs": _pcs(sid, key.root),
            "degrees": {str((key.root + i) % 12): lab for i, lab in zip(ivs, labels)},
            "note_names": [key.note_name(key.root + i) for i in ivs],
            "boxes": _boxes(sid, key.root),
        })

    out_sections = []
    for s in sections:
        chs = []
        sec_chords = []
        for sym in dict.fromkeys(s.get("chords", [])):
            ch = parsed.get(sym)
            if ch is None:
                chs.append({"symbol": sym, "tones": [], "outside": [], "fits": []})
                continue
            sec_chords.append(ch)
            tones = _chord_tones(ch)
            chs.append({
                "symbol": sym,
                "fits": [sc["id"] for sc in scales if _fits(sc["id"], key.root, [ch])],
                "tones": [{"pc": pc, "name": key.note_name(pc), "role": role} for pc, role in tones],
                "outside": [key.note_name(pc) for pc, _ in tones if pc not in main_pcs],
            })
        fits = [sc["id"] for sc in scales if _fits(sc["id"], key.root, sec_chords)]
        out_sections.append({"label": s.get("label", ""), "name": s.get("name", ""), "chords": chs, "fits": fits})

    return {
        "key": key.name, "key_dutch": key.dutch, "root_pc": key.root,
        "pc_names": [key.note_name(pc) for pc in range(12)],
        "open": OPEN, "max_fret": MAX_FRET, "scales": scales, "sections": out_sections,
    }
