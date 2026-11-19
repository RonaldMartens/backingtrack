# BackingTrack Studio

**Online:** https://ronaldmartens.github.io/backingtrack/ (werkt op elke computer en op de iPhone).

**Lokaal:** open **`BackingTrack Studio.html`** met een dubbelklik, bij voorkeur in **Chrome** (of Edge). Er is geen installatie of internet nodig.

## Wat het doet
- **Referentienummer = inspiratie, geen kopie**: typ bijvoorbeeld `Gary Moore - Empty Rooms` en klik op **Analyseer sfeer**.
  - Alleen het stijl-DNA wordt ingesteld: genre, sfeer, tempo, toonsoort-kleur (bijv. harmonisch mineur of dorian), harmonisch palet en instrumenten.
  - De **grondtoon blijft je eigen keuze**, en het akkoordenschema gaat op **Automatisch (geïnspireerd op stijl)**.
  - Er is een ingebouwde bibliotheek met 21 stijlprofielen. Andere nummers worden geanalyseerd met een slimme trefwoord-analyse (artiest, genre- en sfeerwoorden).
  - Optioneel kan Claude het stijlprofiel bepalen. Vul daarvoor je API-key in onder *Claude API*; dat vereist internet. Claude levert alleen een stijlprofiel, nooit akkoorden.
- **Originele akkoorden (Automatisch)**: de engine stelt bij elke klik op *Genereer track* of *Nieuwe variatie* een nieuw schema samen.
  - Couplet, refrein en (indien aangevinkt) bridge krijgen elk een eigen schema. Het refrein opent met een ander akkoord, en de bridge contrasteert en eindigt op de dominant.
  - De harmonie volgt de toonsoort-kleur. De kleurakkoorden komen uit het palet van de stijl, bijv. maj7/add9/sus bij een emotionele ballad, of septiemen en ii-V bij jazz.
  - De engine controleert dat de bekende akkoordreeks van het referentienummer er níet in zit.
  - **Akkoorden vasthouden** houdt een schema dat je goed vindt vast, terwijl je bijvoorbeeld tempo of instrumenten verandert.
  - **Schema overnemen** zet het schema in het tekstveld, zodat je het zelf kunt aanpassen.
- **Sfeer / Mood**: Blij, Verdrietig, Episch, Rustig, Energiek of Mysterieus. De sfeer beïnvloedt:
  - de akkoordkleuren (alleen tonen die in de toonsoort passen);
  - de aanslagsterkte;
  - de ritmische drukte.
- **Toonsoort**: grondtoon met enharmonische keuzes (Fis / F#, Ges / Gb, Bes / Bb …) en een type: Majeur, Mineur (natuurlijk of harmonisch), Diminished, Dorian, Mixolydian of Blues-schaal. Per type krijg je passende akkoordenschema's.
- **Lengte**: kies een **duur in minuten** (1–10) of het oude aantal **herhalingen**.
  - Bij een duur rekent de app uit hoeveel maten er nodig zijn bij het gekozen BPM.
  - Daarna bouwt hij een opbouw met Intro, Couplet, Refrein (Solo), Bridge en Outro.
- **Genre**: Rock, Blues shuffle, Pop, Funk, Jazz swing, Reggae, Metal, Country, Hip-hop/Lo-fi of Ballad.
- **Opties**:
  - **Count-in** en **Slotakkoord**.
  - **Bridge toevoegen**: een contrasterend middendeel met een eigen schema en een snare-roll naar het laatste refrein.
  - **Fading Outro**: een fade over de laatste 4, 6 of 8 maten, op de audio én als CC11-automatisering in de MIDI.
- **Preview** met mixer (mute/solo/volume), loop en een sectiebalk die meeloopt.

## Opslaan
- **Automatisch in `~/Music/BackingTrack/`** (Chrome/Edge):
  - Klik één keer op **Opslagmap koppelen…** en kies je map *Muziek*. De app maakt daarin `BackingTrack` aan.
  - Daarna komt elke gegenereerde track in een eigen submap, bijvoorbeeld `~/Music/BackingTrack/Country_Em_110BPM_4m/`. Bestaat die al, dan wordt het `…_2`.
  - Na het herstarten van de browser vraagt Chrome bij de eerste keer genereren opnieuw om toestemming.
- **Safari** laat webpagina's niet zelf in mappen schrijven. Gebruik daar **Download ZIP**; die komt in Downloads.

Inhoud van elke submap/ZIP:

```
Audio/01 Drums - Country_Em_110BPM_4m.wav   ← 24-bit / 44,1 kHz stereo, alle stems even lang
Audio/02 Bass  - …
MIDI/00 Alle instrumenten - ….mid           ← alle sporen + tempo + sectiemarkers
MIDI/01 Drums - ….mid …                     ← losse MIDI per instrument
Lees mij - Logic Pro.txt
```

## In Logic Pro
1. Zet het projecttempo op het BPM uit de mapnaam.
2. Sleep alle WAV-bestanden tegelijk naar maat 1 en kies **"Maak nieuwe sporen"**. Past Logic het tempo aan? Zet Smart Tempo dan op **KEEP**.
3. Optioneel kun je het MIDI-bestand `00 Alle instrumenten` erin slepen. Dat geeft sporen per instrument, plus markers voor Intro, Couplet, Refrein enzovoort. Drums staan op kanaal 10 (General MIDI).

## Eigen akkoordenschema
- Trappen: `I V vi IV`, `bVII7`, `ii7b5`, `Imaj7`, `iadd9`, `IVsus4`. Hoofdletter is majeur, kleine letter is mineur. `b`/`#` zijn ten opzichte van de majeurtoonladder.
- Of letternamen: `Am F C G`, `Bb7`, `F#m7`.
- Een spatie of `|` begint een nieuwe maat. `IV-V` zet twee akkoorden in één maat.

---
De map `app/` en `INSTALLATIE.md` horen bij een aparte variant: een Python/FastAPI-server met FluidSynth-rendering en een REST API, bedoeld voor een latere iPhone-app. Deze HTML-app gebruikt die niet.
