import librosa
import numpy as np
from pathlib import Path
from core.ir import SongAST, SectionAST, PhraseAST, BeatAST

class SongCompiler:
    def compile(self, mp3_path: Path) -> SongAST:
        y, sr = librosa.load(str(mp3_path), sr=None)
        duration_ms = int(len(y) / sr * 1000)

        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])  # FIX: scalar conversion
        beat_times = librosa.frames_to_time(beats, sr=sr)
        beat_times_ms = [int(t * 1000) for t in beat_times]

        rms = librosa.feature.rms(y=y)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

        energy_curve = []
        for i in range(100):
            t = (i / 99) * (duration_ms / 1000)
            idx = np.argmin(np.abs(rms_times - t))
            energy_curve.append(float(rms[idx]))
        max_e = max(energy_curve) or 1.0
        energy_curve = [e / max_e for e in energy_curve]

        beat_objs = [
            BeatAST(time_ms=bt, is_downbeat=(i % 4 == 0), energy=energy_curve[min(99, int((bt / duration_ms) * 100))]) 
            for i, bt in enumerate(beat_times_ms)
        ]

        section_defs = [
            ("intro", 0.0, 0.15, 0.3),
            ("verse", 0.15, 0.4, 0.5),
            ("chorus", 0.4, 0.7, 0.8),
            ("outro", 0.7, 1.0, 0.4)
        ]

        sections = []
        for name, start_ratio, end_ratio, dyn_range in section_defs:
            start_ms = int(duration_ms * start_ratio)
            end_ms = int(duration_ms * end_ratio)
            sec_beats = [b for b in beat_objs if start_ms <= b.time_ms <= end_ms]

            phrase = PhraseAST(
                start_ms=start_ms, end_ms=end_ms, beats=sec_beats, 
                dominant_emotion="high" if name == "chorus" else "medium",
                energy_curve=energy_curve
            )

            # FIX: Pass phrases directly in constructor, do not mutate frozen object
            sec = SectionAST(
                name=name, start_ms=start_ms, end_ms=end_ms, 
                phrases=[phrase], bpm=tempo, dynamic_range=dyn_range
            )
            sections.append(sec)

        return SongAST(
            title=mp3_path.stem.split(" - ")[-1] if " - " in mp3_path.stem else mp3_path.stem,
            artist=mp3_path.stem.split(" - ")[0] if " - " in mp3_path.stem else "Unknown",
            total_duration_ms=duration_ms, sections=sections,
            global_energy_curve=energy_curve, global_emotion_curve=energy_curve
        )
