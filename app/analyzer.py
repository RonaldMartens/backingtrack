"""Vertaalt een referentienummer naar een muzikaal profiel.

Volgorde: 1) lokale bibliotheek (fuzzy match)  2) Claude API (optioneel, met API-key)
3) heuristische parser (artiest- en trefwoordherkenning).
"""
from __future__ import annotations

import difflib
import json
import os
import re
from typing import Optional

from . import library as lib
from .config import CLAUDE_MODEL
from .models import AnalyzeResponse, MusicProfile
from .theory import parse_key, parse_progression


def _norm(s: str) -> str:
    s = s.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- #
# Profielbouwers
# --------------------------------------------------------------------------- #
def profile_from_mood(mood: str, genre: Optional[str] = None, title: str = "",
                      source: str = "mood") -> MusicProfile:
    m = lib.MOODS.get(mood, lib.MOODS["sad"])
    gid = genre if genre in lib.GENRES else m["genre"]
    g = lib.GENRES[gid]
    key = m["key"]
    # Als het genre majeur/mineur sterk bepaalt en de sfeer neutraal is, houden we de sfeer leidend.
    return MusicProfile(
        title=title, source=source, genre=gid, mood=mood if mood in lib.MOODS else "sad",
        bpm=int(round((m["bpm"] + g["bpm"]) / 2)) if gid != m["genre"] else m["bpm"],
        key=key, verse=m["verse"], chorus=m["chorus"], bridge=m["bridge"],
        drum_style=g["drum_style"], bass_style=g["bass_style"], keys_style=g["keys_style"],
        guitar_style=g["guitar_style"], pad_style=g["pad_style"],
        velocity=int(round((m["velocity"] + g["velocity"]) / 2)), swing=g["swing"], color=g["color"],
        programs=dict(g["programs"]), description=m["description"],
    )


def profile_from_library(entry: dict) -> MusicProfile:
    return MusicProfile(
        title=f"{entry['artist']} - {entry['title']}", source="library",
        genre=entry["genre"], mood=entry["mood"], bpm=entry["bpm"], key=entry["key"],
        verse=entry["verse"], chorus=entry["chorus"], bridge=entry["bridge"],
        drum_style=entry["drum_style"], bass_style=entry["bass_style"], keys_style=entry["keys_style"],
        guitar_style=entry["guitar_style"], pad_style=entry["pad_style"],
        velocity=entry["velocity"], swing=entry["swing"], color=entry.get("color", 0),
        programs=dict(entry["programs"]), description=entry["description"],
    )


# --------------------------------------------------------------------------- #
# 1) Lokale bibliotheek
# --------------------------------------------------------------------------- #
def match_library(reference: str) -> tuple[Optional[dict], float]:
    q = _norm(reference)
    best, best_score = None, 0.0
    for entry in lib.REFERENCE_LIBRARY:
        title = _norm(entry["title"])
        artist = _norm(entry["artist"])
        candidates = [f"{artist} {title}", title] + [_norm(a) for a in entry.get("aliases", [])]
        score = max(difflib.SequenceMatcher(None, q, c).ratio() for c in candidates)
        if title and re.search(rf"\b{re.escape(title)}\b", q):
            score = max(score, 0.92 if artist in q or len(title) > 8 else 0.8)
        for alias in entry.get("aliases", []):
            a = _norm(alias)
            if len(a) > 6 and a in q:
                score = max(score, 0.85)
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


# --------------------------------------------------------------------------- #
# 2) Claude API
# --------------------------------------------------------------------------- #
CLAUDE_SYSTEM = """Je bent een ervaren sessiemuzikant en arrangeur. Je vertaalt een referentienummer naar \
instellingen voor een backingtrack-generator. Beschrijf de sfeer en harmonische kleur van het nummer; \
geef geen songtekst of melodie weer. Benaderingen zijn prima – het gaat om de sfeer.

Notatie van akkoordenschema's (velden verse, chorus, bridge):
- Trapnummers (romeinse cijfers) ten opzichte van de toonsoort in het veld `key`, gescheiden door ' - '.
- Hoofdletter = majeur, kleine letter = mineur (I, ii, iii, IV, V, vi, i, III, VI, VII ...).
- In een mineurtoonsoort zijn de trappen natuurlijk mineur: in Am is III = C, VI = F, VII = G.
- Toegestane toevoegingen: 7, maj7, 9, 6, sus2, sus4, (add9), ° (verminderd), ø (halfverminderd), \
voorvoegsel b of # voor chromatische trappen (bv. bII, bVII, #iv°).
- Duur per akkoord is standaard 1 maat; gebruik ':2' voor 2 maten of ':0.5' voor een halve maat.
- Elk schema is samen 4, 8, 12 of 16 maten lang. Laat de bridge contrasteren met couplet en refrein.

Overige velden:
- key: bv. 'Am', 'F#m', 'Eb', 'C'. bpm: geheel getal 50-180.
- velocity: 40-120 (speelsterkte), swing: 0.0 (recht) t/m 1.0 (volledige triolen-shuffle), \
color: 0 = drieklanken, 1 = septiemen, 2 = septiemen+nonen.
- *_program: General MIDI programmanummer (0-gebaseerd). Keys bv. 0 piano, 4 Rhodes, 5 FM-piano, \
7 clavinet, 16 orgel. Gitaar: 24 nylon, 25 staalsnarig, 26 jazz, 27 clean, 28 muted, 29 overdrive. \
Bas: 32 akoestisch, 33 vinger, 34 plectrum, 35 fretless, 38 synthbas. Pad: 48/49 strijkers, 88-95 synth pads.
- description: 1-3 zinnen in het Nederlands over sfeer, instrumentatie en speelstijl.
- recognized: true als je het nummer kent, anders false (en schat dan op basis van artiest/titel).
- canonical_title: 'Artiest - Titel' zoals jij het nummer kent."""


def _claude_schema() -> dict:
    integer = {"type": "integer"}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "canonical_title": {"type": "string"},
            "recognized": {"type": "boolean"},
            "genre": {"type": "string", "enum": list(lib.GENRES.keys())},
            "mood": {"type": "string", "enum": list(lib.MOODS.keys())},
            "bpm": integer,
            "key": {"type": "string"},
            "verse": {"type": "string"},
            "chorus": {"type": "string"},
            "bridge": {"type": "string"},
            "drum_style": {"type": "string", "enum": lib.DRUM_STYLES},
            "bass_style": {"type": "string", "enum": lib.BASS_STYLES},
            "keys_style": {"type": "string", "enum": lib.KEYS_STYLES},
            "guitar_style": {"type": "string", "enum": lib.GUITAR_STYLES},
            "pad_style": {"type": "string", "enum": lib.PAD_STYLES},
            "velocity": integer,
            "swing": {"type": "number"},
            "color": integer,
            "keys_program": integer,
            "guitar_program": integer,
            "bass_program": integer,
            "pad_program": integer,
            "description": {"type": "string"},
        },
        "required": [
            "canonical_title", "recognized", "genre", "mood", "bpm", "key", "verse", "chorus", "bridge",
            "drum_style", "bass_style", "keys_style", "guitar_style", "pad_style", "velocity", "swing",
            "color", "keys_program", "guitar_program", "bass_program", "pad_program", "description",
        ],
    }


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _sanitize_claude(data: dict, reference: str) -> MusicProfile:
    fallback = profile_from_mood(data.get("mood", "sad"), data.get("genre"))
    try:
        key = parse_key(data["key"])
        key_name = key.name
    except (ValueError, KeyError):
        key, key_name = parse_key(fallback.key), fallback.key

    def valid_prog(text: str, default: str) -> str:
        try:
            parse_progression(text, key)
            return text
        except (ValueError, KeyError):
            return default

    title = data.get("canonical_title") or reference
    return MusicProfile(
        title=title, source="claude", genre=data["genre"], mood=data["mood"],
        bpm=int(_clamp(int(data.get("bpm", 90)), 50, 180)), key=key_name,
        verse=valid_prog(data.get("verse", ""), fallback.verse),
        chorus=valid_prog(data.get("chorus", ""), fallback.chorus),
        bridge=valid_prog(data.get("bridge", ""), fallback.bridge),
        drum_style=data["drum_style"], bass_style=data["bass_style"], keys_style=data["keys_style"],
        guitar_style=data["guitar_style"], pad_style=data["pad_style"],
        velocity=int(_clamp(int(data.get("velocity", 85)), 40, 120)),
        swing=float(_clamp(float(data.get("swing", 0.0)), 0.0, 1.0)),
        color=int(_clamp(int(data.get("color", 0)), 0, 2)),
        programs={
            "keys": int(_clamp(data.get("keys_program", 4), 0, 127)),
            "guitar": int(_clamp(data.get("guitar_program", 27), 0, 127)),
            "bass": int(_clamp(data.get("bass_program", 33), 0, 127)),
            "pad": int(_clamp(data.get("pad_program", 89), 0, 127)),
        },
        description=data.get("description", ""),
    )


def analyze_with_claude(reference: str, api_key: Optional[str]) -> tuple[Optional[MusicProfile], str]:
    try:
        import anthropic
    except ImportError:
        return None, "Python-package 'anthropic' is niet geïnstalleerd."

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": _claude_schema()}},
            system=CLAUDE_SYSTEM,
            messages=[{"role": "user", "content": f"Referentienummer: {reference}"}],
        )
    except anthropic.AuthenticationError:
        return None, "Claude API-key is ongeldig."
    except anthropic.PermissionDeniedError:
        return None, "Deze API-key heeft geen toegang tot het model."
    except anthropic.RateLimitError:
        return None, "Claude API: rate limit bereikt, probeer het zo opnieuw."
    except anthropic.APIStatusError as e:
        return None, f"Claude API-fout ({e.status_code})."
    except anthropic.APIConnectionError:
        return None, "Geen verbinding met de Claude API."

    if response.stop_reason == "refusal":
        return None, "Claude kon deze aanvraag niet verwerken."
    if response.stop_reason == "max_tokens":
        return None, "Claude-antwoord was onvolledig."
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None, "Leeg antwoord van Claude."
    try:
        data = json.loads(text)
        profile = _sanitize_claude(data, reference)
    except (ValueError, KeyError, TypeError) as e:
        return None, f"Kon Claude-antwoord niet verwerken: {e}"
    note = "" if data.get("recognized", True) else " (nummer niet herkend – geschat op basis van artiest/titel)"
    return profile, f"Geanalyseerd door Claude{note}."


# --------------------------------------------------------------------------- #
# 3) Heuristische parser
# --------------------------------------------------------------------------- #
def analyze_heuristic(reference: str) -> tuple[MusicProfile, str]:
    text = _norm(reference)
    parts = re.split(r"\s+[-–—:]\s+", reference.strip(), maxsplit=1)
    title_part = _norm(parts[1] if len(parts) > 1 else parts[0])

    genre, mood, reasons = None, None, []
    for artist, (g, m) in sorted(lib.ARTIST_HINTS.items(), key=lambda kv: -len(kv[0])):
        if _norm(artist) and re.search(rf"\b{re.escape(_norm(artist))}\b", text):
            genre, mood = g, m
            reasons.append(f"artiest herkend: {artist.title()}")
            break

    for word, g in lib.GENRE_KEYWORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            genre = genre or g
            reasons.append(f"genre-trefwoord '{word}'")
            break

    scores = {m: 0 for m in lib.MOOD_KEYWORDS}
    for m, words in lib.MOOD_KEYWORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", title_part):
                scores[m] += 1
    top = max(scores, key=scores.get)
    if scores[top] > 0:
        if mood is None or scores[top] >= 2:
            mood = top
        reasons.append(f"sfeerwoorden in titel → {lib.MOODS[top]['label']}")

    mood = mood or "calm"
    profile = profile_from_mood(mood, genre, title=reference.strip(), source="heuristic")
    why = "; ".join(reasons) if reasons else "geen herkenbare kenmerken, neutrale standaard gekozen"
    profile.description = f"{profile.description} (Schatting: {why}.)"
    return profile, f"Lokale schatting – {why}. Vul een Claude API-key in voor een nauwkeurigere analyse."


# --------------------------------------------------------------------------- #
def analyze_reference(reference: str, api_key: Optional[str] = None, use_claude: bool = True) -> AnalyzeResponse:
    entry, score = match_library(reference)
    if entry and score >= 0.72:
        prof = profile_from_library(entry)
        return AnalyzeResponse(profile=prof, source="library", matched=prof.title, confidence=round(score, 2),
                               message=f"Gevonden in de lokale bibliotheek: {prof.title}.")

    key = (api_key or "").strip() or os.environ.get("ANTHROPIC_API_KEY")
    claude_msg = ""
    if use_claude and key:
        prof, claude_msg = analyze_with_claude(reference, key)
        if prof:
            return AnalyzeResponse(profile=prof, source="claude", matched=prof.title, confidence=0.9,
                                   message=claude_msg)

    prof, msg = analyze_heuristic(reference)
    if claude_msg:
        msg = f"{claude_msg} Teruggevallen op lokale schatting. {msg}"
    return AnalyzeResponse(profile=prof, source="heuristic", matched=None, confidence=0.4, message=msg)
