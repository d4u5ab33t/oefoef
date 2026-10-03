# 🎬 WE.ED.IT DIRECTOR & OIDASHEIM BEATSYNC — VOLLSTÄNDIGE ANLEITUNG

> **Version:** 4.0 Pro / Ultra-Evolution  
> **Architektur:** C++20 Native Acceleration + Direct-Subprocess FFmpeg + Adaptive Hardware Intelligence + Self-Learning Reinforcement Loop

---

## 📑 Inhaltsverzeichnis
1. [Systemarchitektur & Überblick](#1-systemarchitektur--überblick)
2. [Kernmodule & Funktionsweise](#2-kernmodule--funktionsweise)
   - [Audio-Analyse & DSP Engine](#21-audio-analyse--dsp-engine)
   - [MixMeister BPM Analyzer Integration](#22-mixmeister-bpm-analyzer-integration)
   - [Stem-Separation & Vocal Ducking](#23-stem-separation--vocal-ducking)
   - [Dual-Frame Highlight-Erkennung & 140 BPM Sync](#24-dual-frame-highlight-erkennung--140-bpm-sync)
   - [Master 1-Click Director & Council](#25-master-1-click-director--council)
   - [Cinematic Camera Motion (VCAM) & 2.5D Perspektive](#26-cinematic-camera-motion-vcam--25d-perspektive)
   - [Übergangs-Engine (Push/Fade, Dissolve, Scratch)](#27-übergangs-engine-pushfade-dissolve-scratch)
   - [Viral Strategy & Hip-Hop Nischen-Lernen](#28-viral-strategy--hip-hop-nischen-lernen)
   - [C++ Native Acceleration Stack](#29-c-native-acceleration-stack)
3. [Vollständige CLI-Befehlsliste (`cmd list`)](#3-vollständige-cli-befehlsliste-cmd-list)
4. [Praktische Use Cases & Workflows](#4-praktische-use-cases--workflows)
5. [Konfigurations-Referenz (`config.py`)](#5-konfigurations-referenz-configpy)
6. [Hardware-Erkennung, Setup & Wartung](#6-hardware-erkennung-setup--wartung)

---

## 1. Systemarchitektur & Überblick

WE.ED.IT DIRECTOR ist eine professionelle, autonome Videoproduktions-Engine für Musikvideos, Teaser und Social-Media-Releases mit direktem Fokus auf Hip-Hop, Deutschrap, 140 BPM Trap, Boom-Bap und elektronische Musik.

```
                      ┌────────────────────────────────────────┐
                      │            AUDIO INPUT (.mp3)          │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │  DSP & BEAT-TRACKING   │                      │  MIXMEISTER BPM FALLBACK│
     │  (librosa, Transient-  │                      │  (BpmAnalyzer.exe      │
     │   Snapping, Felt-BPM)  │                      │   bei bpm ≤ 20)        │
     └────────────┬───────────┘                      └────────────┬───────────┘
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          ▼
                      ┌────────────────────────────────────────┐
                      │   STEM SEPARATION & VOCAL DUCKING      │
                      │   (Demucs 4-Stem, Sidechain Duck,      │
                      │    Harmonic 808 / Vocal Doublets)      │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │   30k+ CLIP-POOL GLOBE │                      │  DUAL-FRAME HIGHLIGHT  │
     │   (Flat-Globe Index,   │                      │  (P10-P90 Spread,      │
     │    Semantic Matching)  │                      │   140 BPM Bar Snapping)│
     └────────────┬───────────┘                      └────────────┬───────────┘
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          ▼
                      ┌────────────────────────────────────────┐
                      │  DIRECTOR COUNCIL & TIMELINE BUILDER   │
                      │  (Native C++ SIMD Candidate Scoring,   │
                      │   Markov Transitions, Softmax Temp)    │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │   DIRECT-SUBPROCESS FFMPEG RENDERER    │
                      │   (Adaptive Workers, NVENC / CPU,      │
                      │    VCAM Rubber-Band, 2.5D Perspective) │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │ MASTERED 1080p/4K MP4  │                      │ VIRAL STRATEGY BRIEF   │
     │ (+ OTIO Project Export)│                      │ (+ Hashtags & Chapters)│
     └────────────────────────┘                      └────────────────────────┘
```

---

## 2. Kernmodule & Funktionsweise

### 2.1 Audio-Analyse & DSP Engine (`audio_analysis.py`)
- **Beat-Tracking & Drum Transient Alignment:** Erkennt das Beat-Grid und rastet Schnittmarken mit Sub-Frame-Präzision auf die echten Attack-Peaks von Kick und Snare ein (`DRUM_STEM_SYNC_ENABLED`).
- **Felt-Tempo Rhythmus-Erkennung:** Erkennt automatisch, ob ein Track mit nominellem 140-BPM-Raster als **70 BPM Half-Time** (Trap, Drill – Snare auf Beat 3) oder **140 BPM Double-Time** (Boom-Bap, Jersey – Snare auf Beat 2 und 4) empfunden wird.
- **DJ Sync Actions:** Detektiert Scratches, Backspins, Vinyl-Brakes, Drops und Beat-Juggles anhand spektraler ZCR-Flips und Onset-Dichten.
- **MC Spitting Bursts:** Erkennt High-Speed Silben-Kadenzen und schaltet auf Close-Up Performance-Clips.

### 2.2 MixMeister BPM Analyzer Integration (`bpm_analyzer.py`)
- Nutzt die professionelle MixMeister BPM-Engine (`C:\Program Files (x86)\MixMeister BPM Analyzer\BpmAnalyzer.exe`) als automatischen Fallback bei schwer erkennbaren Beats, starkem Reverb oder Ambient-Intros (`bpm <= 20`).
- Parst alle Ausgabeformate (`"BPM: 140.00"`, `"140.00"`, `"140.00 BPM"`) und führt parallele Batch-Scans im ThreadPool aus.

### 2.3 Stem-Separation & Vocal Ducking (`stem_separator.py`)
- **4-Stem Demucs:** Trennt Songs in `vocals`, `drums`, `bass`, `other`.
- **Intelligentes Vocal-Ducking:** Duckt Instrumental-Stems sanft im Takt der Gesangs-/Rap-Energie via FFmpeg `sidechaincompress`, damit die Vocals transparent im Mix stehen.
- **Harmonic Stem Doubling:**
  - *Vocal-Double:* 20 ms Micro-Shift mit L/R-Panning-Offset für breite Stereo-Präsenz.
  - *808-Harmonic-Double:* Harmonischer Mid-Layer (100–400 Hz + Tanh Röhrensättigung) bei -6 dB für massive Hörbarkeit auf Smartphones.

### 2.4 Dual-Frame Highlight-Erkennung & 140 BPM Sync (`clip_highlight.py`)
- **5-Signal Kompositionsanalyse:**
  1. *Schärfe:* Laplacian Variance (30%)
  2. *Dynamikumfang:* Robuster P10→P90 Histogramm-Interquartilabstand gegen Fade-Artefakte (25%)
  3. *Farbtemperatur:* Warm/Kalt-Shift + Sättigungs-Proxy (20%)
  4. *Rule-of-Thirds:* Vordergrund/Hintergrund-Kontrast (15%)
  5. *Horizontale Balance:* Symmetrie-Signal (10%)
- **Visuelle Differenz:** 3×3 Block-Grid-Differenz + Hue-Shift zur Unterscheidung echter Szenenwechsel von bloßen Schwarzblenden.
- **140 BPM Quantisierung:**
  - `H >= 0.90` (FULL_HOLD): 4 Bars (6.857 s) + Hold/Freeze auf Peak-Frame
  - `H >= 0.80` (FULL): 4 Bars (6.857 s) On-Beat Schnitt
  - `H 0.60–0.80` (CROSSFADE): 3.5 Bars (6.000 s) + Crossfade
  - `H < 0.60` (SHORT): 3 Bars (5.143 s) Fast-Cut

### 2.5 Master 1-Click Director & Council (`weedit_director.py`)
- **Council of Directors:** 5 spezialisierte Regie-Stile (`HYPER_STREET`, `CINEMATIC_PUNCH`, `VIRAL_TIKTOK`, `MINIMAL_DARK`, `NARRATIVE_FLOW`).
- **Pacing-Strategien:** `AGGRESSIVE` (0.5–1.8s Schnitte), `BALANCED` (1.2–3.5s), `SLOW_BURN` (2.5–6.0s).
- **Self-Learning Bandit:** Reinforcement-Learning-Schleife, die erfolgreiche Director-Pacing-Kombinationen lernt und belohnt.

### 2.6 Cinematic Camera Motion (VCAM) & 2.5D Perspektive (`renderer.py`)
- **Smoothstep Easing:** $S(t) = 3t^2 - 2t^3$ für fließende Kamerabeschleunigung.
- **Rubber-Band Elasticity:** Gedämpfte Oszillation bei harten Beat-Einschlägen (`CAMERA_ELASTIC_DECAY`, `CAMERA_RUBBER_BAND_ENABLED`).
- **Beat-Dancing & Groove:** Organisches rhythmisches Atmen und Bouncen im Takt des Songs (`BEAT_DANCE_AMPLITUDE`, `BEAT_DANCE_POWER_EXPONENT`).
- **2.5D Fake-3D Perspektiven-Warping:** Räumliches Fluchtpunkt-Warping via FFmpeg `perspective` und `lenscorrection`.

### 2.7 Übergangs-Engine (`renderer.py`)
- **Push/Fade Transition:** Dynamischer Kameraschub mit Richtungsnachführung (`prev_seg.motion_direction`).
- **Dissolve Crossfade:** Echter Video-Crossfade unter Nutzung des bewegten Quellmaterials am Segmentende.
- **Scratch Cutaways:** Schnelle Vor- und Rücklauf-Flicks auf DJ-Scratch-Events.

### 2.8 Viral Strategy & Hip-Hop Nischen-Lernen (`viral-strategy.py`)
- **Standard-Nische:** Vollständig auf `hiphop` kalibriert.
- **Hashtag-Tiers:** Breit (`#foryou`, `#viral`, `#fyp`), Nische (`#deutschrap`, `#hiphop`, `#boombap`, `#trap`, `#808bass`, `#undergroundhiphop`), Marke (`#label`).
- **Social Media Briefing:** Generiert posting-optimierte Metadaten für YouTube, TikTok und Instagram Reels.

### 2.9 C++ Native Acceleration Stack (`cxx_accel/bridge.py`)
- Kompilierte C++20 DLL (`cxx_accel.dll`) mit AVX2/SIMD Vektorisierung für:
  - Batch-Kandidatenscoring über 30.000+ Clips
  - Sub-Frame Beat- und Transient-Snapping
  - Schnelle Cosinus-Ähnlichkeitsberechnung
  - Instant NumPy-Fallback bei Systemen ohne C++-Compiler.

---

## 3. Vollständige CLI-Befehlsliste (`cmd list`)

### 🎬 1-Click Master Director (`weedit_director.py`)
```bash
# Einzelner Song vollautomatisch produzieren
python weedit_director.py single "J:\MyMusic\track.mp3"

# Einzelner Song mit 4K-Auflösung und spezifischem Director
python weedit_director.py single "J:\MyMusic\track.mp3" --platform 4k --director HYPER_STREET --pacing AGGRESSIVE

# Batch-Verarbeitung eines kompletten Musik-Ordners
python weedit_director.py batch "J:\MyMusic\Album_2026" --output-dir "J:\RenderOutput"

# Batch mit Rebuild des Clip-Index
python weedit_director.py batch "J:\MyMusic" --rebuild-globe --limit 10

# Dry-Run (Planung & Timeline ohne finalen FFmpeg-Render)
python weedit_director.py single "J:\MyMusic\track.mp3" --dry-run
```

### ⚡ Klassischer CLI-Runner (`main.py`)
```bash
# Standard-Render mit automatischer Erkennung
python main.py "J:\MyMusic\track.mp3"

# Style-Override (z.B. Boom-Bap oder Drill)
python main.py "J:\MyMusic\track.mp3" --style boombap

# TikTok / Reels 9:16 Vertikal-Modus
python main.py "J:\MyMusic\track.mp3" --platform vertical --tiktok-mode

# Begrenzung auf bestimmte Clip-Unterordner
python main.py "J:\MyMusic\track.mp3" --clip-subdir "StreetFootage" --clip-subdir "StudioShots"

# OpenTimelineIO Projekt exportieren
python main.py "J:\MyMusic\track.mp3" --export-otio
```

### 📈 Viral Strategy Tool (`viral-strategy.py`)
```bash
# Release-Briefing für einen Song generieren
python viral-strategy.py brief --artist "MC Oida" --track "Beton Gold" --release "EP-01" --label "oefoef"

# Plattform-spezifischer Hashtag-Mix (TikTok / YouTube / Instagram)
python viral-strategy.py hashtags --platform tiktok --niche hiphop --label oefoef

# Optimale Posting-Zeiten abfragen
python viral-strategy.py posting --platform instagram

# Kompletter JSON-Snapshot für Scheduling-Tools
python viral-strategy.py snapshot --artist "MC Oida" --track "Beton Gold" --release "EP-01" --output "brief.json"
```

### 🧠 Hardware & System-Diagnose (`hardware_check.py`)
```bash
# Detailliertes Hardware-Profiling & Render-Empfehlungen
python hardware_check.py
```

### 🧪 Setup, Update, Fix & Test-Suite
```bash
# Windows PowerShell All-in-One Runner
powershell -ExecutionPolicy Bypass -File .\setup_and_fix.ps1

# Windows Batch 1-Click Starter
.\setup_and_fix.bat

# Linux / WSL All-in-One Runner
bash ./setup_and_fix.sh

# PyTest Unit- & E2E-Tests ausführen
pytest tests/ -q
```

---

## 4. Praktische Use Cases & Workflows

### Use Case 1: 140 BPM Deutschrap / Trap Musikvideo (1080p HD)
1. Lege die MP3-Datei bereit: `track_140bpm.mp3`
2. Starte den 1-Click Director:
   ```bash
   python weedit_director.py single "track_140bpm.mp3" --director HYPER_STREET
   ```
3. **Was passiert:**
   - Librosa & MixMeister detektieren 140 BPM und klassifizieren den Rhythmus als 70 BPM Half-Time (Trap).
   - Die 6s-Clips im Pool werden über die Dual-Frame-Analyse bewertet und auf 4 Bars (6.857s) oder 3.5 Bars (6.000s) On-Beat eingerastet.
   - FFmpeg encodiert parallel mit GPU-Beschleunigung (NVENC).
   - Audio wird mit 808-Punch (+3dB @ 65Hz) und Mono-Sub (<120Hz) gemastert.

---

### Use Case 2: TikTok & Instagram Reels Vertical Video (9:16)
```bash
python main.py "track.mp3" --platform vertical --tiktok-mode
```
- Schneidet automatisch auf 1080x1920 Vertikal-Format.
- Aktiviert schnelle Schnitte und Punch-Drop Hook-Frameworks (F1).
- Generiert ein passendes `track_viral_brief.json` mit optimierten `#deutschrap #hiphop #viral #fyp` Hashtags.

---

### Use Case 3: NLE-Export für DaVinci Resolve / Premiere Pro
```bash
python weedit_director.py single "track.mp3"
```
- Neben dem finalen MP4 wird automatisch eine `.otio` (OpenTimelineIO) Datei erzeugt.
- Ziehe die `.otio`-Datei direkt in DaVinci Resolve für manuelles Color-Grading oder Feinschnitt.

---

## 5. Konfigurations-Referenz (`config.py`)

| Parameter | Default | Beschreibung |
|---|---|---|
| `OUTPUT_RESOLUTION` | `(1920, 1080)` | Standard-Zielauflösung (Full HD) |
| `OUTPUT_FPS` | `24` | Projekt-Framerate (Film-Look) |
| `VIDEO_CODEC_CPU` | `libx264` | CPU-Encoding-Codec |
| `VIDEO_CODEC_NVENC` | `h264_nvenc` | NVIDIA Hardware-Encoder |
| `CRF` | `18` | Visuell verlustfreie Videoqualität |
| `DEFAULT_HASHTAG_NICHE` | `"hiphop"` | Standard-Nische für Social Media |
| `MIXMEISTER_BPM_FALLBACK_ENABLED` | `True` | MixMeister Analyzer bei bpm<=20 nutzen |
| `DUAL_FRAME_HIGHLIGHT_ENABLED` | `True` | Dual-Frame Analyse für 6s-Clips |
| `BEAT_DANCE_ENABLED` | `True` | Organischer Beat-Groove / VCam-Bounce |
| `AUDIO_MASTER_808_BOOST_DB` | `3.0` | 808-Subbass-Anhebung in dB |
| `AUDIO_MASTER_808_BOOST_HZ` | `65.0` | Center-Frequenz für 808-Punch |
| `AUDIO_MASTER_MS_LOWCUT_HZ` | `120.0` | Mono-Sub Grenze (Phasenstabilität) |
| `AUDIO_MASTER_VOCAL_DUCK_ENABLED` | `True` | Automatisches Vocal-Sidechain-Ducking |

---

## 6. Hardware-Erkennung, Setup & Wartung

### Automatisierte Ressourcen-Dimensionierung
Das System berechnet vor jedem Render-Pass das ideale Verhältnis zwischen parallelen Workern und Threads pro Worker:
$$\text{Workers} = \min(\text{Usable Cores}, \lfloor \text{Available RAM} \times \text{Safety} / \text{RAM per Worker} \rfloor, \text{Hard Cap})$$

- **1080p HD:** ~220 MB RAM pro Worker → hohe Parallelität (4–8 Worker).
- **4K UHD:** ~900 MB RAM pro Worker → adaptive Drosselung gegen Memory-Overflow (1–2 Worker mit mehr Threads).

### 1-Click Update & Fix
Um das System nach Updates auf den neuesten Stand zu bringen und alle Komponenten zu validieren:
```bash
# Windows
.\setup_and_fix.bat

# Linux / WSL
bash ./setup_and_fix.sh
```
Das Skript aktualisiert alle Abhängigkeiten, prüft die C++ Beschleunigung, bereinigt temporäre Caches und führt alle **177 Unit- & Integrationstests** durch.
