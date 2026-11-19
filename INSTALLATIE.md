# BackingTrack Generator (FastAPI + webinterface)

Backingtracks voor Logic Pro: per instrument een MIDI-bestand én een WAV/AIFF-stem, plus een mix,
akkoordenoverzicht en ZIP-download. De backend is een REST API, zodat later een iOS-app kan aansluiten.

## 1. Installatie (macOS)

Automatisch: `./install.sh`. Handmatig doe je het volgende:

```bash
# Homebrew (als je dat nog niet hebt): https://brew.sh
brew install fluid-synth                      # audio-renderer
brew install python@3.12                      # alleen nodig als python3 ouder is dan 3.10

# Python-omgeving BUITEN OneDrive (OneDrive breekt symlinks/bestanden in venvs)
python3 -m venv ~/.venvs/backingtrack
~/.venvs/backingtrack/bin/pip install -r requirements.txt

# Gratis General MIDI SoundFont (GeneralUser GS, ~30 MB)
mkdir -p ~/Library/Audio/Sounds/Banks
curl -L -o ~/Library/Audio/Sounds/Banks/GeneralUser-GS.sf2 \
  https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2
```

Een alternatieve SoundFont (MuseScore General, groter, ~200 MB):
`https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2`.
Elke `.sf2` in `soundfonts/` of `~/Library/Audio/Sounds/Banks/` wordt automatisch gevonden;
je kunt er ook een kiezen met `BACKINGTRACK_SOUNDFONT=/pad/naar/bestand.sf2`.

## 2. Starten

```bash
./start.sh
```

- Mac: http://localhost:8000
- iPhone (zelfde wifi): http://<jouw-mac>.local:8000. `start.sh` toont het juiste adres.
- API-documentatie: http://localhost:8000/docs

### Starten met een icoon (zonder Terminal)

Maak eenmalig een icoon op je bureaublad:

```bash
./maak-bureaublad-icoon.sh
```

- **Dubbelklik op BackingTrack** start de server op de achtergrond en opent de app in je browser.
- **Eerste start vanaf een externe schijf:** macOS vraagt *"BackingTrack wil toegang tot bestanden op een verwijderbaar volume"*. Kies **OK**. Heb je dat gemist, zet dan in *Systeeminstellingen › Privacy en beveiliging › Bestanden en mappen* bij BackingTrack **Verwijderbare volumes** aan. Het icoon opent dat scherm ook zelf als de toegang ontbreekt.
- Staat de code op een externe schijf, dan gaan de tracks naar `<schijf>/BackingTrack Tracks`, anders naar `~/Music/BackingTrack`. Een andere map geef je mee als argument: `./maak-bureaublad-icoon.sh "/pad/naar/map"`.
- **Stoppen:** klik in de app rechtsboven op **⏻ Stoppen**, of dubbelklik nogmaals op het icoon en kies **Stoppen**. Dat werkt alleen vanaf de Mac zelf, niet vanaf de iPhone.
- **Automatisch stoppen:** sluit je het laatste tabblad van BackingTrack, dan stopt de server na ongeveer 10 seconden vanzelf. Dat gebeurt nooit tijdens het genereren, en niet zolang de app nog ergens open is (ook niet op je iPhone). Uitzetten kan met `BACKINGTRACK_AUTO_STOP=0`, bijvoorbeeld voor een iOS-app zonder browser.
- Hangt de externe schijf er niet aan, dan meldt het icoon dat.
- Het logbestand staat in `~/Library/Logs/BackingTrack.log`.
- Tip: sleep het icoon ook naar je Dock.

### Naam en intro

- **Naam van je nummer** (bovenaan, optioneel) wordt de titel en de mapnaam, bijv. `Zomeravond_Em_118BPM_4m`. Dat werkt met of zonder referentienummer. Leeg laten: de naam komt van de referentie of de sfeer.
- **Intro** (bij Structuur): uit = het nummer begint direct met het couplet. De gekozen duur blijft gelijk.

### Eerder gemaakte nummers openen

Rechtsonder staat **Mijn nummers**: alle nummers in je tracksmap, met een zoekveld. Daar horen ook de tracks bij die je met de online HTML-app maakte (die worden herkend aan hun *Lees mij - Logic Pro.txt*). Klik op een nummer om het te openen, met:
- speler (de mix, of per stem afspelen met ▶);
- bestanden en ZIP;
- akkoordenschema en **🎸 Gitaarakkoorden**;
- **⟳ Instellingen overnemen**, alleen bij nummers van de server: zet alle instellingen terug in de generator, inclusief de seed. Wis de seed voor een variatie;
- **📂 Toon in Finder**: opent de map van het nummer, handig voor Logic.

### Gitaarakkoorden

Bij elke track zit een knop **🎸 Gitaarakkoorden**. Die opent een overzicht met:
- de akkoordvolgorde per sectie;
- voor elk akkoord **4 grepen op verschillende posities** (standaardstemming), met vingerzetting, barré, x/o en tab.

Met **Afdrukken** krijg je een nette A4. De grepen worden berekend (`app/guitar.py`), dus ook kleurakkoorden als `Am(add9)`, `Bm7b5` of `G/B` krijgen speelbare grepen. API: `POST /api/guitar-chords {"chords": ["Am", "F"], "key": "Am"}`.

## 3. Projectstructuur

```
BackingTrack/
├── install.sh            # eenmalige installatie
├── start.sh              # server starten
├── maak-bureaublad-icoon.sh  # BackingTrack.app op je bureaublad
├── assets/BackingTrack.icns  # icoon
├── requirements.txt
├── app/
│   ├── main.py           # FastAPI: routes, CORS, static files
│   ├── models.py         # Pydantic-requests/responses (API-contract voor iOS)
│   ├── config.py         # paden, FluidSynth/SoundFont-detectie
│   ├── guitar.py         # gitaargrepen berekenen (4 posities per akkoord)
│   ├── theory.py         # toonsoorten (ook Nederlands: Fis, Bes, Esm), akkoorden, trapnummers, voicings
│   ├── library.py        # genres, sferen, akkoordenschema's, referentienummers
│   ├── analyzer.py       # referentie → profiel (bibliotheek / Claude API / heuristiek)
│   ├── arranger.py       # maten berekenen, songstructuur, akkoorden per sectie
│   ├── generators.py     # drums, bas, keys, gitaar, pad
│   ├── midi_writer.py    # MIDI (Type 0 per stem, Type 1 compleet), markers, CC7/CC11
│   ├── renderer.py       # FluidSynth, fade, mix, WAV/AIFF/M4A
│   ├── storage.py        # sessiemappen in ~/Music/BackingTrack, ZIP
│   └── engine.py         # alles aan elkaar: generate / preview
├── static/
│   ├── index.html        # webinterface (Tailwind, responsive)
│   └── app.js
└── soundfonts/           # optioneel: eigen .sf2-bestanden
```

## 4. Uitvoer

Elke sessie komt in een eigen map, bijvoorbeeld `~/Music/BackingTrack/RockBallad_Am_EmptyRooms_70BPM_5m/`.
Andere plek, bijv. je externe schijf: start met `BACKINGTRACK_OUTPUT="/Volumes/Externe_schijf/BackingTrack Tracks" ./start.sh`.

Inhoud van een sessiemap:

```
00_Arrangement.mid   alle sporen + tempo + sectiemarkers (Type 1)
00_Mix.wav / .m4a    volledige mix (m4a voor de speler/iPhone)
01_Drums.mid/.wav    (kanaal 10, GM-drums → werkt direct met Drum Kit Designer)
02_Bass.mid/.wav
03_Keys.mid/.wav
04_Guitar.mid/.wav
05_Pad.mid/.wav      (+ .aiff als je AIFF aanvinkt)
Akkoorden.txt        akkoordenschema per sectie
session.json         alle instellingen (seed!) om de track te reproduceren
```

**In Logic Pro:** zet het projecttempo op het BPM in de mapnaam, sleep de WAV-stems naar maat 1
("Maak nieuwe sporen"). Met `00_Arrangement.mid` krijg je ook de sectiemarkers (Intro, Couplet, …).

**Fade-out:** in de MIDI staat een CC11-curve (expression), CC7 is het vaste kanaalvolume.
De audio krijgt dezelfde equal-power curve, sample-nauwkeurig.

## 5. Akkoordenschema invoeren

- Trapnummers: `i - VI - III - VII`, `ii7 - V7 - Imaj7`, `bVII`, `iiø`, `i(add9)`, `VIIsus4`
- Akkoordnamen: `Am - F - C - G`, `F#m7`, `Bes`, `G/B`, `Cadd9`
- Duur: `Am:2` (2 maten), `G:0.5` (halve maat). `12-bar` geeft een 12-maats blues.
- Een majeurschema in een mineurtoonsoort (of andersom) wordt in de relatieve toonsoort gespeeld.

## 6. Claude API (optioneel)

Bekende nummers komen uit de lokale bibliotheek. Voor andere nummers vul je in de UI een API-key in
(of zet je `ANTHROPIC_API_KEY`). De server gebruikt `claude-opus-5-5` met structured output en valt
bij een fout terug op de lokale schatting. De key wordt niet op de server opgeslagen. Met
"Onthoud op dit apparaat" bewaart de browser hem in localStorage.

## 7. REST API (voor de iOS-app)

| Methode | Pad | Doel |
|---|---|---|
| GET  | `/api/health` | FluidSynth/SoundFont-status |
| GET  | `/api/options` | sferen, genres, toonsoorten, schema's, instrumenten |
| POST | `/api/analyze-reference` | `{reference, api_key?, use_claude}` → profiel |
| POST | `/api/generate` | volledige sessie (MIDI + audio) |
| POST | `/api/preview` | snelle preview (8 maten refrein) → `url` |
| GET  | `/api/preview/{session_id}` | mix van een sessie streamen |
| GET  | `/api/sessions` / `/api/sessions/{id}` | sessies opvragen |
| GET  | `/api/sessions/{id}/files/{naam}` | los bestand |
| GET  | `/api/sessions/{id}/zip` | alles als ZIP |

CORS staat standaard open (`*`); beperk dit met `BACKINGTRACK_CORS=https://...`.
Andere uitvoermap: `BACKINGTRACK_OUTPUT=/pad`.

## Gitaarsolo's toevoegen

Eerst genereer je het nummer. Daarna voeg je in het blok **🎸 Gitaarsolo's** (onder de structuur) solo's toe als **nieuwe delen**:

1. Klik **＋ Solo toevoegen**. Elke solo heeft eigen instellingen:
   - **Plaats**: *Na Couplet 2*, *Na Refrein 2*, *Na Tussenspel*, *Na Bridge* … of *Vóór de outro*.
   - **Lengte**: 2 tot 32 maten.
   - **Stijl**: *melodisch*, *bluesy* (bends en vibrato) of *virtuoos* (snelle loopjes).
   - **Klank**: overdrive, distortion, clean of jazz.
   - **Akkoorden**: de solo speelt over de akkoorden van het couplet, het refrein of de bridge.
2. Klik **🎸 Solo's maken**. Het nummer wordt in dezelfde map opnieuw opgebouwd, met dezelfde seed. Akkoorden en delen blijven gelijk; de solodelen komen erbij en het nummer wordt zoveel maten langer.
3. Klik nog een keer voor nieuwe varianten. Met **Alle solo's weghalen** krijgt het nummer zijn oorspronkelijke lengte terug.

Per solo krijg je een aparte `06_Solo_<n>_na<Deel>.wav` en `.mid`:

- Elk bestand is net zo lang als het nummer en begint op maat 1. Zet het in Logic op maat 1, dan valt de solo precies op zijn plek.
- `00_Mix` is de begeleiding zonder solo, om zelf mee te spelen. `00_Mix_met_solo` heeft de solo's erbij; in de speler wissel je met **Met solo** en **Zonder solo**.
- `00_Arrangement.mid` bevat de solo's ook.
- Gebruik je de MIDI met een eigen gitaarplugin, dan zitten de bends en het vibrato in de pitch bend (±2 halve tonen).

Let op: de begeleiding wordt opnieuw gerenderd, dus heb je de stems al in Logic staan, importeer ze dan opnieuw.

Solo's toevoegen kan alleen bij nummers die met deze app zijn gemaakt, niet bij tracks uit de online HTML-app.
