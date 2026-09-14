# 🏔️ Native Genome Engine — Architecture Overview

## System Overview

The **Native Genome Engine** is a director-driven, beat-synchronized music video compilation engine. Unlike conventional auto-editors that perform naive cuts on peak audio transients, this engine decouples audio analysis, visual director heuristics, asset resolution, camera dynamics, and rendering into an end-to-end **Visual & Rhythm Genome** architecture.

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ Audio File      ├─────►│ Audio Scanner   ├─────►│ Rhythm Genome   │
│ (MP3 / WAV)     │      │ (BPM / Onsets)  │      │ & Visual Schema │
└─────────────────┘      └─────────────────┘      └────────┬────────┘
                                                           │
┌─────────────────┐      ┌─────────────────┐               ▼
│ Media Clip Pool ├─────►│ Genome Resolver ├◄──────┐ ┌──────────────┐
│ (Indexed Assets)│      │ (CLIP / Tags)   │      │ │ Song Compiler│
└─────────────────┘      └────────┬────────┘      │ └──────┬───────┘
                                  │               │        │
                                  ▼               │        ▼
                         ┌─────────────────┐      │ ┌──────────────┐
                         │ Edit Decision   ├──────┴─┤ Director     │
                         │ List (EDL)      │        │ Council      │
                         └────────┬────────┘        └──────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌─────────────────┐                               ┌─────────────────┐
│ FFmpeg Renderer │                               │ OTIO Exporter   │
│ (NVENC / H.264) │                               │ (NLE Import)    │
└─────────────────┘                               └─────────────────┘
```

---

## 📦 Package Layout (`src/genome_engine`)

- `scanner/` — DSP audio analysis, tempo detection, onset profiling, drop detection.
- `genome/` — Schema definition for `RhythmGenome`, `VisualGenome`, and `GenomeData`.
- `compiler/` — Song timeline compilation into `EditDecisionList` and `TimelineSegment` models.
- `directors/` — Multi-agent Director Council (`alpine_drill_comedy`, `boombap_hype`, `cyberpunk_glitch`).
- `resolver/` — Semantic clip pool indexing and tag-matching algorithm.
- `rl/` — Contextual Multi-Armed Bandit decision engine & user preference learning.
- `camera/` — Kinematic camera trajectories (push zooms, whip pans) & Unreal CineCamera exporter.
- `renderer/` — Hardware-accelerated FFmpeg/NVENC renderer & OpenTimelineIO (OTIO) exporter.
- `learning/` — Synapse closed-loop neural aesthetic learner.

---

## 🚀 CLI Commands

```bash
# Diagnostic hardware & encoder check
genome-engine hardware-check

# Scan track rhythm genome
genome-engine scan --song track.mp3

# Compile timeline EDL
genome-engine compile --song track.mp3 --style alpine_drill_comedy --dry-run

# Render video output
genome-engine render --edl output/final_edl.json --output output/final_video.mp4
```
