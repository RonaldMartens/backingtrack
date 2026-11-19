"""Lokale muzikale bibliotheek: genres, sferen, akkoordenschema's en referentienummers.

Alle akkoordenschema's staan in trapnummers (romeinse cijfers) zodat ze in elke toonsoort werken.
Referentieprofielen zijn bewuste benaderingen van de sfeer – geen transcripties.
"""
from __future__ import annotations

DRUM_STYLES = ["ballad", "pop", "rock", "funk", "shuffle", "jazz_swing", "lofi", "epic"]
BASS_STYLES = ["root_long", "root_fifth", "eighth_drive", "walking", "funk_16", "blues_shuffle", "lofi"]
KEYS_STYLES = ["pad_sustain", "ballad_arp", "comp_offbeat", "jazz_comp", "rhodes_lofi", "funk_stabs", "blues_comp"]
GUITAR_STYLES = ["arpeggio", "clean_arp_delay", "strum_8", "power_8", "funk_chops", "blues_shuffle",
                 "jazz_quarters", "lofi_pluck"]
PAD_STYLES = ["wide", "swell", "soft"]

INSTRUMENTS = [
    {"id": "drums", "label": "Drums", "number": 1, "file": "Drums"},
    {"id": "bass", "label": "Bas", "number": 2, "file": "Bass"},
    {"id": "keys", "label": "Elektrische piano / Keys", "number": 3, "file": "Keys"},
    {"id": "guitar", "label": "Slaggitaar / Arpeggio", "number": 4, "file": "Guitar"},
    {"id": "pad", "label": "Atmosferische synth pad", "number": 5, "file": "Pad"},
]

# --------------------------------------------------------------------------- #
# Genres
# --------------------------------------------------------------------------- #
GENRES: dict[str, dict] = {
    "pop": {
        "label": "Pop", "tag": "Pop", "bpm": 112, "minor": False,
        "drum_style": "pop", "bass_style": "root_fifth", "keys_style": "comp_offbeat",
        "guitar_style": "strum_8", "pad_style": "wide", "swing": 0.0, "velocity": 90, "color": 0,
        "programs": {"keys": 4, "guitar": 25, "bass": 33, "pad": 89},
    },
    "rock": {
        "label": "Rock", "tag": "Rock", "bpm": 124, "minor": True,
        "drum_style": "rock", "bass_style": "eighth_drive", "keys_style": "pad_sustain",
        "guitar_style": "power_8", "pad_style": "soft", "swing": 0.0, "velocity": 102, "color": 0,
        "programs": {"keys": 16, "guitar": 29, "bass": 34, "pad": 89},
    },
    "blues_rock_ballad": {
        "label": "Blues-Rock Ballad", "tag": "RockBallad", "bpm": 70, "minor": True,
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "ballad_arp",
        "guitar_style": "clean_arp_delay", "pad_style": "wide", "swing": 0.0, "velocity": 82, "color": 0,
        "programs": {"keys": 5, "guitar": 27, "bass": 33, "pad": 89},
    },
    "funk": {
        "label": "Funk", "tag": "Funk", "bpm": 104, "minor": True,
        "drum_style": "funk", "bass_style": "funk_16", "keys_style": "funk_stabs",
        "guitar_style": "funk_chops", "pad_style": "swell", "swing": 0.12, "velocity": 96, "color": 1,
        "programs": {"keys": 7, "guitar": 27, "bass": 33, "pad": 90},
    },
    "jazz": {
        "label": "Jazz", "tag": "Jazz", "bpm": 132, "minor": False,
        "drum_style": "jazz_swing", "bass_style": "walking", "keys_style": "jazz_comp",
        "guitar_style": "jazz_quarters", "pad_style": "soft", "swing": 1.0, "velocity": 76, "color": 2,
        "programs": {"keys": 4, "guitar": 26, "bass": 32, "pad": 89},
    },
    "blues": {
        "label": "Blues", "tag": "Blues", "bpm": 96, "minor": False,
        "drum_style": "shuffle", "bass_style": "blues_shuffle", "keys_style": "blues_comp",
        "guitar_style": "blues_shuffle", "pad_style": "soft", "swing": 1.0, "velocity": 90, "color": 1,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 89},
    },
    "lofi": {
        "label": "Lo-Fi", "tag": "LoFi", "bpm": 80, "minor": False,
        "drum_style": "lofi", "bass_style": "lofi", "keys_style": "rhodes_lofi",
        "guitar_style": "lofi_pluck", "pad_style": "soft", "swing": 0.55, "velocity": 70, "color": 2,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 89},
    },
    "cinematic": {
        "label": "Cinematic / Episch", "tag": "Cinematic", "bpm": 76, "minor": True,
        "drum_style": "epic", "bass_style": "root_long", "keys_style": "ballad_arp",
        "guitar_style": "arpeggio", "pad_style": "swell", "swing": 0.0, "velocity": 90, "color": 0,
        "programs": {"keys": 0, "guitar": 27, "bass": 33, "pad": 94},
    },
}

# --------------------------------------------------------------------------- #
# Sferen
# --------------------------------------------------------------------------- #
MOODS: dict[str, dict] = {
    "happy": {
        "label": "Blij / Opgewekt", "tag": "Opgewekt", "genre": "pop", "bpm": 116, "key": "G",
        "verse": "I - V - vi - IV", "chorus": "IV - I - V - V", "bridge": "vi - IV - I - V",
        "velocity": 94,
        "description": "Opgewekte pop: heldere majeurakkoorden, rechte achtsten, open refrein.",
    },
    "sad": {
        "label": "Verdrietig / Melancholisch", "tag": "Melancholisch", "genre": "blues_rock_ballad",
        "bpm": 70, "key": "Am",
        "verse": "i(add9) - VI - III - VII", "chorus": "VI - VII - i(add9) - i", "bridge": "iv - VII - III - VI",
        "velocity": 78,
        "description": "Langzame mineurballad met add9-kleuren, ruime drums en warme pads.",
    },
    "epic": {
        "label": "Melodramatisch / Episch", "tag": "Episch", "genre": "cinematic", "bpm": 76, "key": "Dm",
        "verse": "i - VI - III - VII", "chorus": "VI - III - VII - i", "bridge": "iv - VI - VIIsus4 - VII",
        "velocity": 96,
        "description": "Filmische opbouw: brede pads, toms, grote crescendo's richting het refrein.",
    },
    "calm": {
        "label": "Rustig / Relaxed", "tag": "Relaxed", "genre": "lofi", "bpm": 80, "key": "F",
        "verse": "IVmaj7 - iii7 - ii7 - Imaj7", "chorus": "ii7 - V7 - Imaj7 - vi7", "bridge": "IVmaj7 - V - iii7 - vi7",
        "velocity": 68,
        "description": "Ontspannen, licht geswingde groove met zachte septiem- en none-akkoorden.",
    },
    "energetic": {
        "label": "Energiek / Krachtig", "tag": "Energiek", "genre": "rock", "bpm": 132, "key": "Em",
        "verse": "i - VII - VI - VII", "chorus": "VI - VII - i - i", "bridge": "iv - VI - VII - VII",
        "velocity": 108,
        "description": "Stuwende rock: achtsten op bas en gitaar, harde snare, crashes op de één.",
    },
    "dark": {
        "label": "Mysterieus / Donker", "tag": "Donker", "genre": "cinematic", "bpm": 88, "key": "Cm",
        "verse": "i - i - bII - i", "chorus": "i - VI - iv - V", "bridge": "iv - bII - V - V",
        "velocity": 80,
        "description": "Donkere Frygische kleuren (bII), spaarzame drums en zwellende pads.",
    },
}

# --------------------------------------------------------------------------- #
# Akkoordenschema's
# --------------------------------------------------------------------------- #
BLUES_12 = "I7 - I7 - I7 - I7 - IV7 - IV7 - I7 - I7 - V7 - IV7 - I7 - V7"
MINOR_BLUES_12 = "i7 - i7 - i7 - i7 - iv7 - iv7 - i7 - i7 - VI7 - V7 - i7 - V7"

PROGRESSION_PRESETS: dict[str, dict] = {
    "minor_epic": {"label": "i – VI – III – VII (episch mineur)", "text": "i - VI - III - VII", "minor": True},
    "pop_axis": {"label": "I – V – vi – IV (pop)", "text": "I - V - vi - IV", "minor": False},
    "sensitive": {"label": "vi – IV – I – V", "text": "vi - IV - I - V", "minor": False},
    "fifties": {"label": "I – vi – IV – V (jaren 50)", "text": "I - vi - IV - V", "minor": False},
    "jazz_251": {"label": "ii – V – I (jazz)", "text": "ii7 - V7 - Imaj7 - Imaj7", "minor": False},
    "blues12": {"label": "12-bar Blues", "text": BLUES_12, "minor": False,
                "bridge": "IV7:2 - I7:2 - V7:2 - IV7 - V7"},
    "minor_blues12": {"label": "12-bar Mineur Blues", "text": MINOR_BLUES_12, "minor": True,
                      "bridge": "iv7:2 - i7:2 - VI7:2 - V7:2"},
    "aeolian_rock": {"label": "i – VII – VI – VII (rock)", "text": "i - VII - VI - VII", "minor": True},
    "andalusian": {"label": "i – VII – VI – V (Andalusisch)", "text": "i - VII - VI - V", "minor": True},
    "circle_minor": {"label": "iv – VII – III – VI – ii° – V – i (kwintencirkel)",
                     "text": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i", "minor": True},
    "lofi_cycle": {"label": "IVmaj7 – iii7 – ii7 – Imaj7 (lo-fi)", "text": "IVmaj7 - iii7 - ii7 - Imaj7", "minor": False},
    "minor_groove": {"label": "i7 – iv7 (funk-groove)", "text": "i7 - i7 - iv7 - iv7", "minor": True},
}

DEFAULT_BRIDGE_MINOR = "iv - VI - III - V"
DEFAULT_BRIDGE_MAJOR = "IV - V - iii - vi"

# --------------------------------------------------------------------------- #
# Referentienummers
# --------------------------------------------------------------------------- #
REFERENCE_LIBRARY: list[dict] = [
    {
        "artist": "Gary Moore", "title": "Empty Rooms", "aliases": ["empty rooms"],
        "genre": "blues_rock_ballad", "mood": "sad", "bpm": 70, "key": "Am",
        "verse": "i(add9) - VImaj7 - III(add9) - VIIsus4:0.5 - VII:0.5",
        "chorus": "VI(add9) - VII - i(add9) - isus2",
        "bridge": "iv(add9) - VII - IIImaj7 - VImaj7:0.5 - V:0.5",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "ballad_arp",
        "guitar_style": "clean_arp_delay", "pad_style": "wide", "velocity": 80, "swing": 0.0, "color": 0,
        "programs": {"keys": 5, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Langzame, melancholische 80s rock/blues-ballad (~70 BPM) in mineur met sus2/add9-kleuren, "
                       "brede atmosferische synth-pads, een dragende bas op hele en halve noten en ruime "
                       "ballad-drums met veel galm. Clean gitaar-arpeggio's met delay.",
    },
    {
        "artist": "Pink Floyd", "title": "Shine On You Crazy Diamond", "aliases": ["shine on", "crazy diamond"],
        "genre": "cinematic", "mood": "epic", "bpm": 62, "key": "Gm",
        "verse": "i:2 - iv:2 - VI - VII - i:2", "chorus": "VI - VII - i - i", "bridge": "iv - VI - VII - V",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "clean_arp_delay", "pad_style": "swell", "velocity": 76, "swing": 0.0, "color": 0,
        "programs": {"keys": 16, "guitar": 27, "bass": 33, "pad": 94},
        "description": "Weids, traag en atmosferisch (~62 BPM) in G-mineur. Lange zwellende synth-pads en orgel, "
                       "spaarzame drums, ruimte voor lange gitaarnoten.",
    },
    {
        "artist": "Pink Floyd", "title": "Comfortably Numb", "aliases": ["comfortably numb"],
        "genre": "blues_rock_ballad", "mood": "epic", "bpm": 64, "key": "Bm",
        "verse": "i - i - VII - VII - VI - VI - iv - i", "chorus": "III - VII - bII:0.5 - VI:0.5 - III",
        "bridge": "VI - VII - III - III",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "clean_arp_delay", "pad_style": "wide", "velocity": 84, "swing": 0.0, "color": 0,
        "programs": {"keys": 16, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Statige rockballad (~64 BPM), B-mineur coupletten en een majeur-refrein, grote solo-ruimte.",
    },
    {
        "artist": "Gary Moore", "title": "Still Got The Blues", "aliases": ["still got the blues"],
        "genre": "blues_rock_ballad", "mood": "sad", "bpm": 80, "key": "Am",
        "verse": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i", "chorus": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i",
        "bridge": "VI - VII - i - i",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "wide", "velocity": 82, "swing": 0.0, "color": 1,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 48},
        "description": "Bluesballad over de mineur-kwintencirkel (~80 BPM), strijkers-pad en warme Rhodes.",
    },
    {
        "artist": "Gary Moore", "title": "Parisienne Walkways", "aliases": ["parisienne walkways"],
        "genre": "blues_rock_ballad", "mood": "sad", "bpm": 68, "key": "Am",
        "verse": "i - iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - V7", "chorus": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i",
        "bridge": "VI - VII - i - V",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "ballad_arp",
        "guitar_style": "clean_arp_delay", "pad_style": "wide", "velocity": 78, "swing": 0.0, "color": 1,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Romantische, trage mineurballad (~68 BPM) met kwintencirkel-harmonie en veel ruimte.",
    },
    {
        "artist": "Santana", "title": "Europa", "aliases": ["europa", "earth's cry heaven's smile"],
        "genre": "blues_rock_ballad", "mood": "sad", "bpm": 72, "key": "Cm",
        "verse": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i", "chorus": "iv7 - VII7 - IIImaj7 - VImaj7 - iiø - V7 - i - i",
        "bridge": "VI - V - i - i",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "wide", "velocity": 80, "swing": 0.0, "color": 1,
        "programs": {"keys": 16, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Latin-getinte instrumentale ballad (~72 BPM) in C-mineur, orgel en zachte pads.",
    },
    {
        "artist": "Eagles", "title": "Hotel California", "aliases": ["hotel california"],
        "genre": "rock", "mood": "dark", "bpm": 74, "key": "Bm",
        "verse": "i - V - VII - IV - VI - III - iv - V", "chorus": "VI - III - V - i - VI - III - iv - V",
        "bridge": "i - V - VII - IV",
        "drum_style": "ballad", "bass_style": "root_fifth", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "soft", "velocity": 86, "swing": 0.0, "color": 0,
        "programs": {"keys": 16, "guitar": 25, "bass": 33, "pad": 89},
        "description": "Mysterieuze, rustig rollende rock (~74 BPM) in B-mineur met de typische dalende progressie.",
    },
    {
        "artist": "Dire Straits", "title": "Sultans Of Swing", "aliases": ["sultans of swing"],
        "genre": "rock", "mood": "energetic", "bpm": 148, "key": "Dm",
        "verse": "i - VII - VI - V", "chorus": "III - VII - VI - VI", "bridge": "VI - VII - i - i",
        "drum_style": "pop", "bass_style": "root_fifth", "keys_style": "comp_offbeat",
        "guitar_style": "strum_8", "pad_style": "soft", "velocity": 92, "swing": 0.0, "color": 0,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Strakke, droge rock-shuffle (~148 BPM) in D-mineur, lichte clean gitaar.",
    },
    {
        "artist": "Stevie Ray Vaughan", "title": "Pride And Joy", "aliases": ["pride and joy"],
        "genre": "blues", "mood": "energetic", "bpm": 118, "key": "E",
        "verse": BLUES_12, "chorus": BLUES_12, "bridge": "IV7:2 - I7:2 - V7:2 - IV7 - V7",
        "drum_style": "shuffle", "bass_style": "blues_shuffle", "keys_style": "blues_comp",
        "guitar_style": "blues_shuffle", "pad_style": "soft", "velocity": 100, "swing": 1.0, "color": 1,
        "programs": {"keys": 16, "guitar": 29, "bass": 33, "pad": 89},
        "description": "Texas-shuffle (~118 BPM) in E, 12-maats blues met triolengevoel.",
    },
    {
        "artist": "B.B. King", "title": "The Thrill Is Gone", "aliases": ["thrill is gone"],
        "genre": "blues", "mood": "sad", "bpm": 92, "key": "Bm",
        "verse": MINOR_BLUES_12, "chorus": MINOR_BLUES_12, "bridge": "iv7:2 - i7:2 - VI7:2 - V7:2",
        "drum_style": "ballad", "bass_style": "root_fifth", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "wide", "velocity": 82, "swing": 0.25, "color": 1,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 48},
        "description": "Mineurblues (~92 BPM) in B-mineur, strijkers-pad, ingetogen groove.",
    },
    {
        "artist": "Journey", "title": "Don't Stop Believin'", "aliases": ["dont stop believin", "don't stop believing"],
        "genre": "pop", "mood": "happy", "bpm": 119, "key": "E",
        "verse": "I - V - vi - IV", "chorus": "IV - I - V - vi", "bridge": "vi - IV - I - V",
        "drum_style": "rock", "bass_style": "eighth_drive", "keys_style": "comp_offbeat",
        "guitar_style": "strum_8", "pad_style": "wide", "velocity": 98, "swing": 0.0, "color": 0,
        "programs": {"keys": 0, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Optimistische arena-rock (~119 BPM) in E, piano-riff en rechte achtsten op de bas.",
    },
    {
        "artist": "Coldplay", "title": "Fix You", "aliases": ["fix you"],
        "genre": "cinematic", "mood": "sad", "bpm": 69, "key": "Eb",
        "verse": "I - iii - vi - V", "chorus": "IV - I - V - V", "bridge": "IV - I - V - vi",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "swell", "velocity": 78, "swing": 0.0, "color": 0,
        "programs": {"keys": 16, "guitar": 27, "bass": 33, "pad": 89},
        "description": "Ingetogen, zwellende popballad (~69 BPM) in Es, orgel-pad die opbouwt naar een groots einde.",
    },
    {
        "artist": "Adele", "title": "Someone Like You", "aliases": ["someone like you"],
        "genre": "pop", "mood": "sad", "bpm": 67, "key": "A",
        "verse": "I - iii - vi - IV", "chorus": "I - V - vi - IV", "bridge": "IV - V - vi - IV",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "ballad_arp",
        "guitar_style": "arpeggio", "pad_style": "soft", "velocity": 74, "swing": 0.0, "color": 0,
        "programs": {"keys": 0, "guitar": 25, "bass": 33, "pad": 89},
        "description": "Pianoballad (~67 BPM) in A met doorlopende gebroken akkoorden.",
    },
    {
        "artist": "Daft Punk", "title": "Get Lucky", "aliases": ["get lucky"],
        "genre": "funk", "mood": "happy", "bpm": 116, "key": "Bm",
        "verse": "i7 - III - v7 - IV", "chorus": "i7 - III - v7 - IV", "bridge": "VI - VII - i7 - i7",
        "drum_style": "funk", "bass_style": "funk_16", "keys_style": "funk_stabs",
        "guitar_style": "funk_chops", "pad_style": "swell", "velocity": 96, "swing": 0.08, "color": 1,
        "programs": {"keys": 4, "guitar": 27, "bass": 33, "pad": 90},
        "description": "Disco-funk (~116 BPM): 16e-gitaarchops, strakke four-on-the-floor-achtige groove.",
    },
    {
        "artist": "Herbie Hancock", "title": "Cantaloupe Island", "aliases": ["cantaloupe island"],
        "genre": "jazz", "mood": "calm", "bpm": 112, "key": "Fm",
        "verse": "i7:4 - VI7:4 - #vi7:4 - i7:4", "chorus": "i7:4 - VI7:4 - #vi7:4 - i7:4",
        "bridge": "iv7:2 - VII7:2 - i7:4",
        "drum_style": "funk", "bass_style": "root_fifth", "keys_style": "jazz_comp",
        "guitar_style": "jazz_quarters", "pad_style": "soft", "velocity": 82, "swing": 0.2, "color": 2,
        "programs": {"keys": 4, "guitar": 26, "bass": 32, "pad": 89},
        "description": "Modale soul-jazz (~112 BPM) in F-mineur, 16-maats vorm met piano-vamp.",
    },
    {
        "artist": "Miles Davis", "title": "So What", "aliases": ["so what"],
        "genre": "jazz", "mood": "calm", "bpm": 136, "key": "Dm",
        "verse": "i7:8", "chorus": "bii7:4 - i7:4", "bridge": "bii7:8",
        "drum_style": "jazz_swing", "bass_style": "walking", "keys_style": "jazz_comp",
        "guitar_style": "jazz_quarters", "pad_style": "soft", "velocity": 74, "swing": 1.0, "color": 2,
        "programs": {"keys": 0, "guitar": 26, "bass": 32, "pad": 89},
        "description": "Modale cool-jazz (~136 BPM), D-dorisch met een halve toon omhoog in het midden.",
    },
    {
        "artist": "Metallica", "title": "Nothing Else Matters", "aliases": ["nothing else matters"],
        "genre": "rock", "mood": "epic", "bpm": 69, "key": "Em",
        "verse": "i - VII - VI - VI", "chorus": "VI - VII - i - i", "bridge": "iv - VI - VII - VII",
        "drum_style": "ballad", "bass_style": "root_long", "keys_style": "pad_sustain",
        "guitar_style": "arpeggio", "pad_style": "wide", "velocity": 84, "swing": 0.0, "color": 0,
        "programs": {"keys": 4, "guitar": 25, "bass": 34, "pad": 48},
        "description": "Ballad (~69 BPM) in E-mineur met arpeggio-gitaar en strijkers.",
    },
]

# Artiest -> (genre, sfeer) voor de heuristische parser
ARTIST_HINTS: dict[str, tuple[str, str]] = {
    "gary moore": ("blues_rock_ballad", "sad"), "joe bonamassa": ("blues_rock_ballad", "sad"),
    "santana": ("blues_rock_ballad", "sad"), "pink floyd": ("cinematic", "epic"),
    "david gilmour": ("blues_rock_ballad", "epic"), "eric clapton": ("blues", "calm"),
    "stevie ray vaughan": ("blues", "energetic"), "srv": ("blues", "energetic"),
    "b.b. king": ("blues", "sad"), "bb king": ("blues", "sad"), "john mayer": ("blues", "calm"),
    "albert king": ("blues", "energetic"), "metallica": ("rock", "energetic"), "ac/dc": ("rock", "energetic"),
    "led zeppelin": ("rock", "energetic"), "foo fighters": ("rock", "energetic"), "nirvana": ("rock", "energetic"),
    "guns n' roses": ("rock", "energetic"), "toto": ("pop", "happy"), "journey": ("pop", "happy"),
    "bon jovi": ("rock", "energetic"), "dire straits": ("rock", "calm"), "mark knopfler": ("rock", "calm"),
    "daft punk": ("funk", "happy"), "chic": ("funk", "happy"), "nile rodgers": ("funk", "happy"),
    "prince": ("funk", "energetic"), "james brown": ("funk", "energetic"), "jamiroquai": ("funk", "happy"),
    "vulfpeck": ("funk", "happy"), "earth, wind & fire": ("funk", "happy"), "earth wind and fire": ("funk", "happy"),
    "miles davis": ("jazz", "calm"), "john coltrane": ("jazz", "calm"), "herbie hancock": ("jazz", "calm"),
    "bill evans": ("jazz", "calm"), "chet baker": ("jazz", "sad"), "norah jones": ("jazz", "calm"),
    "nujabes": ("lofi", "calm"), "j dilla": ("lofi", "calm"), "tom misch": ("lofi", "calm"),
    "coldplay": ("pop", "epic"), "adele": ("pop", "sad"), "ed sheeran": ("pop", "happy"),
    "taylor swift": ("pop", "happy"), "dua lipa": ("pop", "energetic"), "the weeknd": ("pop", "dark"),
    "hans zimmer": ("cinematic", "epic"), "john williams": ("cinematic", "epic"),
    "ludovico einaudi": ("cinematic", "calm"), "two steps from hell": ("cinematic", "epic"),
    "radiohead": ("cinematic", "dark"), "portishead": ("lofi", "dark"), "massive attack": ("lofi", "dark"),
    "joe satriani": ("rock", "epic"), "steve vai": ("rock", "epic"), "eagles": ("rock", "calm"),
    "u2": ("rock", "epic"), "queen": ("rock", "epic"), "the beatles": ("pop", "happy"),
}

GENRE_KEYWORDS = {
    "blues": "blues", "jazz": "jazz", "funk": "funk", "lofi": "lofi", "lo-fi": "lofi", "chill": "lofi",
    "rock": "rock", "pop": "pop", "ballad": "blues_rock_ballad", "epic": "cinematic", "soundtrack": "cinematic",
}

MOOD_KEYWORDS: dict[str, list[str]] = {
    "sad": ["empty", "rain", "tears", "alone", "lonely", "goodbye", "cry", "crying", "sorrow", "gone", "cold",
            "room", "rooms", "memory", "memories", "hurt", "broken", "still", "lost", "miss", "verdriet",
            "tranen", "alleen", "blue", "without", "farewell", "fade"],
    "happy": ["happy", "sun", "sunshine", "dance", "good", "smile", "party", "summer", "lucky", "joy",
              "vrolijk", "zon", "feest", "walking", "shine", "celebrate", "fun", "sweet"],
    "epic": ["diamond", "heroes", "hero", "war", "rise", "glory", "legend", "kingdom", "epic", "battle",
             "eternal", "sky", "heaven", "forever", "infinity", "anthem", "majesty"],
    "calm": ["calm", "slow", "sleep", "dream", "dreams", "chill", "moon", "ocean", "breeze", "rustig",
             "sunday", "morning", "easy", "gentle", "quiet", "peace", "stil"],
    "energetic": ["fire", "run", "power", "highway", "thunder", "wild", "fast", "drive", "burn", "jump",
                  "electric", "rock", "storm", "rebel", "speed", "crazy train"],
    "dark": ["dark", "shadow", "black", "ghost", "devil", "evil", "mystery", "midnight", "death", "night",
             "nacht", "donker", "fear", "haunted", "hell", "paranoid"],
}


def mood_options() -> list[dict]:
    return [{"value": k, "label": v["label"], "genre": v["genre"], "bpm": v["bpm"], "key": v["key"]}
            for k, v in MOODS.items()]


def genre_options() -> list[dict]:
    return [{"value": k, "label": v["label"]} for k, v in GENRES.items()]


def progression_options() -> list[dict]:
    return [{"value": k, "label": v["label"], "text": v["text"]} for k, v in PROGRESSION_PRESETS.items()]


def reference_titles() -> list[str]:
    return [f"{r['artist']} - {r['title']}" for r in REFERENCE_LIBRARY]
