"""Muziektheorie: toonsoorten, akkoorden, trapnummers (romeinse cijfers) en voicings."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
DUTCH_NAMES = {
    "C": "C", "C#": "Cis", "Db": "Des", "D": "D", "D#": "Dis", "Eb": "Es", "E": "E",
    "F": "F", "F#": "Fis", "Gb": "Ges", "G": "G", "G#": "Gis", "Ab": "As", "A": "A",
    "A#": "Ais", "Bb": "Bes", "B": "B", "Cb": "Ces",
}
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# Toonsoorten die met mollen geschreven worden
FLAT_MAJOR_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"}
FLAT_MINOR_KEYS = {"Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm", "Abm"}


# --------------------------------------------------------------------------- #
# Noten & toonsoorten
# --------------------------------------------------------------------------- #
_ACC = r"(#|b|♯|♭|is|es|s)?"


def _acc_to_semis(acc: str | None) -> int:
    if not acc:
        return 0
    return 1 if acc in ("#", "♯", "is") else -1


def _english_spelling(letter: str, acc: int) -> str:
    return letter + ("#" if acc == 1 else "b" if acc == -1 else "")


@dataclass(frozen=True)
class Key:
    root: int            # pitch class 0-11
    minor: bool
    spelling: str        # bv. "F#", "Bb", "C"

    @property
    def name(self) -> str:
        return self.spelling + ("m" if self.minor else "")

    @property
    def dutch(self) -> str:
        return DUTCH_NAMES.get(self.spelling, self.spelling) + ("m" if self.minor else "")

    @property
    def use_flats(self) -> bool:
        if "b" in self.spelling[1:]:
            return True
        if "#" in self.spelling:
            return False
        return (self.name in FLAT_MINOR_KEYS) if self.minor else (self.spelling in FLAT_MAJOR_KEYS)

    @property
    def scale(self) -> list[int]:
        return MINOR_SCALE if self.minor else MAJOR_SCALE

    def note_name(self, pc: int) -> str:
        return (FLAT_NAMES if self.use_flats else SHARP_NAMES)[pc % 12]

    def parallel(self) -> "Key":
        return Key(self.root, not self.minor, self.spelling)

    @property
    def folder_tag(self) -> str:
        """Bestandsnaamveilig, Nederlandse notatie: F#m -> Fism, Bb -> Bes."""
        return self.dutch


def parse_key(text: str) -> Key:
    """Accepteert o.a. 'Am', 'A minor', 'Gesm', 'Gbm', 'Fis', 'F#', 'Bes', 'Esm', 'C majeur'."""
    if not text:
        raise ValueError("Lege toonsoort")
    s = text.strip().replace("♯", "#").replace("♭", "b")
    s = re.sub(r"\s+", " ", s)
    m = re.match(
        r"^([A-Ga-g])(is|es|s|#|b)?\s*(m|min|minor|mineur|moll|maj|major|majeur|dur|groot|klein)?$",
        s, re.IGNORECASE,
    )
    if not m:
        raise ValueError(f"Onbekende toonsoort: {text}")
    letter = m.group(1).upper()
    acc_raw = m.group(2)
    acc_raw = acc_raw.lower() if acc_raw and acc_raw.lower() in ("is", "es", "s") else acc_raw
    acc = _acc_to_semis(acc_raw)
    qual = (m.group(3) or "")
    minor = qual.lower() in ("m", "min", "minor", "mineur", "moll", "klein") or qual == "m"
    if qual == "M":  # hoofdletter M = majeur
        minor = False
    root = (LETTER_PC[letter] + acc) % 12
    return Key(root=root, minor=minor, spelling=_english_spelling(letter, acc))


def key_options() -> list[dict]:
    """Alle majeur- en mineurtoonsoorten incl. enharmonische schrijfwijzen voor de UI."""
    major = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B", "Cb"]
    minor = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
    out = []
    for sp in major:
        nl = DUTCH_NAMES[sp]
        label = f"{nl} / {sp} majeur" if nl != sp else f"{sp} majeur"
        out.append({"value": sp, "label": label, "group": "Majeur"})
    for sp in minor:
        nl = DUTCH_NAMES[sp]
        label = f"{nl}m / {sp}m mineur" if nl != sp else f"{sp}m mineur"
        out.append({"value": sp + "m", "label": label, "group": "Mineur"})
    return out


# --------------------------------------------------------------------------- #
# Akkoorden
# --------------------------------------------------------------------------- #
@dataclass
class Chord:
    root: int                       # pitch class
    intervals: tuple                # halve tonen t.o.v. grondtoon (kan > 12 zijn)
    symbol: str
    bass: Optional[int] = None      # slash-bas (pitch class)
    tags: set = field(default_factory=set)

    @property
    def bass_pc(self) -> int:
        return self.root if self.bass is None else self.bass

    @property
    def is_minor(self) -> bool:
        return 3 in self.intervals and 4 not in self.intervals

    @property
    def third(self) -> Optional[int]:
        for i in (3, 4):
            if i in self.intervals:
                return i
        return None

    @property
    def fifth(self) -> int:
        for i in (7, 6, 8):
            if i in self.intervals:
                return i
        return 7

    def pcs(self) -> list[int]:
        seen, out = set(), []
        for i in self.intervals:
            pc = (self.root + i) % 12
            if pc not in seen:
                seen.add(pc)
                out.append(pc)
        return out

    def with_color(self, level: int) -> "Chord":
        """Voeg kleurtonen toe (level 1 = 7e, level 2 = 7e + 9e) voor jazz/lo-fi/keys."""
        iv = set(self.intervals)
        if level <= 0 or 5 in iv or 2 in iv:   # sus-akkoorden laten we zo
            return self
        has7 = 10 in iv or 11 in iv or (9 in iv and 6 in iv)
        if not has7:
            if 6 in iv and 3 in iv:
                iv.add(10)       # halfverminderd
            elif 8 in iv:
                pass
            elif 3 in iv:
                iv.add(10)
            else:
                iv.add(11 if "tonic" in self.tags or "IV" in self.tags else 10)
        if level >= 2 and 13 not in iv and 15 not in iv and 6 not in iv:
            iv.add(14)
        return Chord(self.root, tuple(sorted(iv)), self.symbol, self.bass, set(self.tags))


def build_intervals(minor: bool, dim: bool, aug: bool, suffix: str) -> tuple:
    s = suffix.replace("(", "").replace(")", "").replace(" ", "").replace("Δ", "maj").replace("ø", "m7b5")
    third = 3 if minor else 4
    fifth = 6 if dim else 8 if aug else 7
    notes = {0, third, fifth}

    if s == "5":
        return (0, 7)
    if s.startswith("m7b5"):
        notes = {0, 3, 6, 10}
        s = s[4:]
    if "b5" in s:
        notes.discard(7); notes.add(6); s = s.replace("b5", "")
    if "#5" in s:
        notes.discard(7); notes.add(8); s = s.replace("#5", "")

    seventh = None
    if "maj" in s or re.search(r"M(7|9|13)", s):
        seventh = 11
        s = s.replace("maj", "").replace("M", "")
    if dim and s.startswith("7"):
        seventh = 9
        s = s[1:]

    add_only = "add" in s
    s_clean = s.replace("add", "")
    if "sus2" in s_clean:
        notes.discard(third); notes.add(2); s_clean = s_clean.replace("sus2", "")
    if "sus4" in s_clean:
        notes.discard(third); notes.add(5); s_clean = s_clean.replace("sus4", "")
    if s_clean.endswith("sus") or s_clean == "sus":
        notes.discard(third); notes.add(5); s_clean = s_clean.replace("sus", "")

    nums = re.findall(r"(b|#)?(\d+)", s_clean)
    for acc, num in nums:
        n = int(num)
        if n == 7:
            notes.add(seventh if seventh is not None else 10)
        elif n == 6:
            notes.add(9)
        elif n == 9:
            notes.add(13 if acc == "b" else 15 if acc == "#" else 14)
            if not add_only and not acc:
                notes.add(seventh if seventh is not None else 10)
        elif n == 11:
            notes.add(18 if acc == "#" else 17)
            if not add_only:
                notes.add(seventh if seventh is not None else 10); notes.add(14)
        elif n == 13:
            notes.add(21)
            if not add_only:
                notes.add(seventh if seventh is not None else 10); notes.add(14)
    if seventh is not None:
        notes.add(seventh)
    return tuple(sorted(notes))


_CHORD_RE = re.compile(
    r"^([A-Ga-g])(#|b|♯|♭|is(?!us)|es(?!us)|s(?!us))?(.*?)(?:/([A-Ga-g](?:#|b|is|es|s)?))?$"
)
_ROMAN_RE = re.compile(r"^([b#♭♯]?)(VII|III|IV|VI|II|V|I|vii|iii|iv|vi|ii|v|i)(°|o|ø|\+)?(.*)$")
_ROMAN_DEG = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}


def _spell(key: Key, pc: int) -> str:
    return key.note_name(pc)


def parse_chord_name(token: str, key: Key) -> Chord:
    t = token.strip().replace("♯", "#").replace("♭", "b")
    m = _CHORD_RE.match(t)
    if not m:
        raise ValueError(f"Onbekend akkoord: {token}")
    letter, acc, rest, slash = m.group(1).upper(), m.group(2), m.group(3) or "", m.group(4)
    root = (LETTER_PC[letter] + _acc_to_semis(acc)) % 12
    rest_n = rest.replace("(", "").replace(")", "")
    minor = dim = aug = False
    suffix = rest_n
    if rest_n.startswith(("dim", "°", "o")):
        dim, minor = True, True
        suffix = rest_n[3:] if rest_n.startswith("dim") else rest_n[1:]
    elif rest_n.startswith(("aug", "+")):
        aug = True
        suffix = rest_n[3:] if rest_n.startswith("aug") else rest_n[1:]
    elif rest_n.startswith("ø"):
        suffix = rest_n
    elif rest_n.startswith("min"):
        minor, suffix = True, rest_n[3:]
    elif rest_n.startswith("m") and not rest_n.startswith("maj"):
        minor, suffix = True, rest_n[1:]
    elif rest_n.startswith("-"):
        minor, suffix = True, rest_n[1:]
    intervals = build_intervals(minor, dim, aug, suffix)
    bass = None
    if slash:
        sm = re.match(r"^([A-Ga-g])(#|b|is|es|s)?$", slash)
        if sm:
            bass = (LETTER_PC[sm.group(1).upper()] + _acc_to_semis(sm.group(2))) % 12
    acc_n = _acc_to_semis(acc)
    root_txt = _english_spelling(letter, acc_n) if acc else _spell(key, root)
    bass_txt = ""
    if bass is not None:
        sm2 = re.match(r"^([A-Ga-g])(#|b|is|es|s)?$", slash)
        bass_txt = "/" + _english_spelling(sm2.group(1).upper(), _acc_to_semis(sm2.group(2)))
    symbol = root_txt + rest + bass_txt
    return Chord(root, intervals, symbol, bass)


def parse_roman(token: str, key: Key) -> Chord:
    m = _ROMAN_RE.match(token.strip())
    if not m:
        raise ValueError(f"Onbekend trapnummer: {token}")
    acc, numeral, qual, suffix = m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""
    deg = _ROMAN_DEG[numeral.lower()]
    semi = key.scale[deg]
    if key.minor and numeral.lower() == "vii" and qual in ("°", "o"):
        semi = 11  # leidtoon uit harmonisch mineur
    semi += 1 if acc in ("#", "♯") else -1 if acc in ("b", "♭") else 0
    root = (key.root + semi) % 12
    lower = numeral.islower()
    dim = qual in ("°", "o")
    half_dim = qual == "ø"
    aug = qual == "+"
    if half_dim:
        intervals = build_intervals(True, True, False, "7")
        intervals = tuple(sorted(set(intervals) - {9} | {10}))
    else:
        intervals = build_intervals(lower or dim, dim, aug, suffix)
    clean_suffix = suffix.replace("(", "").replace(")", "")
    if "sus" in clean_suffix:
        qual_txt = ""
    elif dim:
        qual_txt = "dim"
    elif half_dim:
        qual_txt = "m7b5"
    elif aug:
        qual_txt = "aug"
    else:
        qual_txt = "m" if lower else ""
    if qual_txt == "m" and clean_suffix.startswith("add"):
        clean_suffix = f"({clean_suffix})"
    if acc in ("b", "♭"):
        root_txt = FLAT_NAMES[root]
    elif acc in ("#", "♯"):
        root_txt = SHARP_NAMES[root]
    else:
        root_txt = _spell(key, root)
    symbol = root_txt + qual_txt + clean_suffix
    tags = set()
    if deg == 0 and not acc:
        tags.add("tonic")
    if deg == 3:
        tags.add("IV")
    return Chord(root, intervals, symbol, None, tags)


def parse_chord_token(token: str, key: Key) -> Chord:
    t = token.strip()
    if _ROMAN_RE.match(t):
        return parse_roman(t, key)
    return parse_chord_name(t, key)


@dataclass
class ChordEvent:
    chord: Chord
    beats: float


def split_progression(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,|\-–—→>]+", text.strip()) if t]


def parse_progression(text: str, key: Key) -> list[ChordEvent]:
    """'Am - F - C - G', 'i - VI - III - VII', 'Am:2 F C:0.5 G:0.5' (getal = aantal maten)."""
    events: list[ChordEvent] = []
    for tok in split_progression(text):
        bars = 1.0
        if ":" in tok:
            tok, dur = tok.split(":", 1)
            try:
                bars = max(0.25, float(dur.replace(",", ".")))
            except ValueError:
                bars = 1.0
        if tok in ("%", "/") and events:
            events.append(ChordEvent(events[-1].chord, bars * 4))
            continue
        events.append(ChordEvent(parse_chord_token(tok, key), bars * 4))
    if not events:
        raise ValueError("Leeg akkoordenschema")
    return events


def progression_mode_hint(text: str) -> Optional[bool]:
    """True = mineur-progressie (begint met 'i'), False = majeur ('I'), None = onbekend/akkoordnamen."""
    toks = split_progression(text)
    for t in toks:
        m = _ROMAN_RE.match(t)
        if not m:
            return None
        if m.group(2).lower() == "i" and not m.group(1):
            return m.group(2) == "i"
    return None


# --------------------------------------------------------------------------- #
# Voicings
# --------------------------------------------------------------------------- #
def bass_pitch(pc: int, low: int = 28) -> int:
    """Grondtoon in basregister: E1 (28) t/m D#2 (39)."""
    return low + ((pc - low) % 12)


def nearest_pitch(pc: int, target: int) -> int:
    base = target - ((target - pc) % 12)
    return base if target - base <= 6 else base + 12


def voice_lead(pcs: list[int], low: int, high: int, prev: Optional[list[int]] = None,
               center: Optional[int] = None) -> list[int]:
    """Kies de inversie die het dichtst bij de vorige voicing ligt (stemvoering)."""
    if not pcs:
        return []
    center = center if center is not None else (low + high) // 2
    candidates = []
    n = len(pcs)
    for rot in range(n):
        order = pcs[rot:] + pcs[:rot]
        for start in range(low, low + 12):
            if start % 12 != order[0]:
                continue
            v, cur = [start], start
            for pc in order[1:]:
                nxt = cur + ((pc - cur) % 12 or 12)
                v.append(nxt)
                cur = nxt
            if v[-1] <= high:
                candidates.append(v)
            v2 = [p + 12 for p in v]
            if v2[-1] <= high:
                candidates.append(v2)
    if not candidates:
        return sorted(nearest_pitch(pc, center) for pc in pcs)

    def score(v: list[int]) -> float:
        if prev:
            sp = sorted(prev)
            a = sorted(v)
            k = min(len(a), len(sp))
            movement = sum(abs(a[i] - sp[i]) for i in range(k))
            return movement + 0.15 * abs(sum(v) / len(v) - center)
        return abs(sum(v) / len(v) - center)

    return min(candidates, key=score)


def guitar_voicing(chord: Chord) -> list[int]:
    """Gitaarachtige 'E-shape' voicing vanaf E2..D#3."""
    r = 40 + ((chord.root - 40) % 12)
    third = chord.third
    has2 = 2 in chord.intervals
    has4 = 5 in chord.intervals
    if len(chord.intervals) == 2:  # powerchord
        return [r, r + 7, r + 12]
    v = [r, r + chord.fifth, r + 12]
    if third is not None:
        v.append(r + 12 + third)
    elif has2:
        v.append(r + 14)
    elif has4:
        v.append(r + 17)
    v.append(r + 12 + chord.fifth)
    if 10 in chord.intervals or 11 in chord.intervals:
        v.append(r + 12 + (10 if 10 in chord.intervals else 11))
    elif 14 in chord.intervals or has2:
        v.append(r + 26 if r + 26 <= 79 else r + 14)
    else:
        v.append(r + 24)
    if chord.bass is not None:
        b = 40 + ((chord.bass - 40) % 12)
        v[0] = b if b <= r + 4 else b - 12
    return sorted(set(p for p in v if 38 <= p <= 82))


def pad_voicing(chord: Chord, prev: Optional[list[int]] = None) -> list[int]:
    """Brede, open pad-voicing: grondtoon + kwint laag, 3e/9e hoog."""
    r = 48 + ((chord.root - 48) % 12)       # C3..B3
    low = [r, r + chord.fifth] if r + chord.fifth <= 62 else [r - 12, r - 12 + chord.fifth]
    upper_pcs = [(chord.root + i) % 12 for i in chord.intervals if i % 12 not in (0, chord.fifth)]
    if not upper_pcs:
        upper_pcs = [(chord.root + 7) % 12]
    prev_upper = [p for p in (prev or []) if p >= 60] or None
    upper = voice_lead(upper_pcs + [(chord.root + 14) % 12] if 14 not in chord.intervals and chord.third
                       and len(upper_pcs) < 3 else upper_pcs, 62, 84, prev_upper, center=72)
    return sorted(set(low + upper))
