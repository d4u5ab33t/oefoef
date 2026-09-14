# 🚀 Native Genome Engine (Oidasheim BeatSync)

> **The Visual & Rhythm Genome Music Video Engine**

Native Genome Engine is a modular, AI-assisted video editing & compilation engine built to transform raw audio tracks (MP3/WAV) and video clip pools into dynamic, cinematic music videos.

---

## ⚡ Key Features

- **Audio Rhythm Genome**: High-precision BPM detection, onset tracking, energy curve profiling, and drop detection.
- **Visual Genome Directives**: Custom director presets (`alpine_drill_comedy`, `boombap_hype`, `cyberpunk_glitch`).
- **Director Council**: Dynamic multi-agent style orchestration and camera directive injection.
- **Semantic Asset Resolver**: Automatic clip pool indexing and tag-matching.
- **Contextual RL-Bandit**: Online reinforcement learning for edit retention optimization.
- **Cinematic Kinematics**: Dynamic push zooms, whip pans, and Unreal Engine CineCamera export.
- **Professional Renderer**: Hardware-accelerated FFmpeg / NVENC video rendering and OpenTimelineIO (OTIO) export.
- **Closed-Loop Synapse Learner**: Aesthetic parameter auto-tuning from reference videos.

---

## 💻 Quick Start

### 1. Installation
```bash
# Clone repository
git clone https://github.com/oidasheim/beatsync.git
cd beatsync

# Quick installation
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Hardware Diagnostic
```bash
genome-engine hardware-check
```

### 3. Compile a Music Video Timeline
```bash
genome-engine compile --song path/to/track.mp3 --style alpine_drill_comedy --dry-run
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📜 License

MIT License. Developed by Oidasheim Engine Team.
