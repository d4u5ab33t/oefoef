# Oidasheim C++ Semantic Video Slicer (`oidasheim_slicer`)

High-Performance C++ Modul zum semantischen, inhaltlichen und takt-synchronen Schneiden langer Videoloops (wie `D:\Oidasheim\NFOs\longloops`), automatischem Export in den ClipPool (`J:\raw_vidz\_raw_reorga__`), Generierung semantischer Beschreibungen und Eintragen in die SQLite-Datenbank (`beat_sync.db`) sowie den Flat-Globe-Cache (`libsync-flat-globe.db.json`).

---

## 🚀 Features

1. **Inhaltliche & Semantische Schnitt-Erkennung**:
   - Erkennt Szenenwechsel und dynamische Transitionspunkte.
   - Filtert unbrauchbare Sequenzen heraus (Schwarzbilder, ultra-dunkle Bereiche, eingefrorene Standbilder/Freezes).
   - Taktgenaue Quantisierung (1 Bar, 2 Bars, 4 Bars bei konfigurierbarem BPM, Default 140 BPM).

2. **Dynamik- & Feature-Analyse**:
   - **Motion-Score**: Berechnet visuelle Bewegungsenergie.
   - **Motion-Direction**: Erkennt horizontale Driftrichtung (links / rechts) für spätere Push/Fade-Übergänge.
   - **Spitting-Score & DJ-Action-Score**: Erkennt Nahaufnahmen / Rap-Performances und DJ/Turntable-Szenen.
   - **Highlight-Score**: Bewertet die Eignung als visueller Fokus-Shot.

3. **ClipPool-Export**:
   - Exportiert die geschnittenen Clips mit Frame-Präzision und optimalen Keyframe-Intervallen nach `J:\raw_vidz\_raw_reorga__\longloops_cuts`.
   - Optionaler schneller Stream-Copy-Modus (`--fast-copy`).

4. **Datenbank & Flat-Globe-Synchronisation**:
   - Trägt die Slices direkt in die SQLite-Tabelle `longloops_slices` in `beat_sync.db` ein.
   - Aktualisiert `libsync-flat-globe.db.json` atomar, sodass der gesamte Oidasheim-Render-Stack (`main.py`, `renderer.py`, `timeline_builder.py`) die neuen Clips sofort ohne Neuscan nutzen kann.

---

## 🛠️ Kompilierung & Ausführung

### Über das Build-Skript:
```bat
cd cpp_slicer
build.bat
```

### Manuelle CMake-Kompilierung:
```bat
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
```

### Ausführung:
```bat
oidasheim_slicer.exe --input "D:\Oidasheim\NFOs\longloops" --clip-pool "J:\raw_vidz\_raw_reorga__" --bpm 140.0
```

### Parameter:
| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| `--input <path>` | `D:\Oidasheim\NFOs\longloops` | Quellordner mit langen Videos |
| `--clip-pool <path>` | `J:\raw_vidz\_raw_reorga__` | Zielordner im ClipPool |
| `--db <path>` | `J:\Oidasheim\mo.gen\beat_sync.db` | SQLite Datenbankpfad |
| `--globe <path>` | `J:\Oidasheim\mo.gen\libsync-flat-globe.db.json` | Flat Globe Cache JSON |
| `--bpm <val>` | `140.0` | Takt-Referenz für Schnittlängen |
| `--min-dur <sec>` | `1.8` | Minimale Clipdauer |
| `--max-dur <sec>` | `8.5` | Maximale Clipdauer |
| `--fast-copy` | `false` | Schneller Stream-Copy ohne Re-Encode |
