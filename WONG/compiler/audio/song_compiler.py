import librosa
import numpy as np
import hashlib
from pathlib import Path
from core.models import SongAST, SectionNode, PhraseNode, BeatNode

class SongCompiler:
    def __init__(self, beats_per_phrase=16):
        self.bpp = beats_per_phrase

    def compile(self, mp3_path: Path) -> SongAST:
        # 1. Audio laden
        y, sr = librosa.load(mp3_path, sr=None)
        
        # 2. Analyse
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        rms_norm = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
        
        # 3. Beats als Nodes
        beats = []
        for i, t in enumerate(beat_times):
            energy = float(rms_norm[int(t * sr / 512)]) # RMS-Fenster-Mapping
            beats.append(BeatNode(timestamp=float(t), energy=energy, is_downbeat=(i % 4 == 0)))

        # 4. Phrasen & Sections (Compiler-Logik)
        # Wir gruppieren Beats zu Phrasen und bestimmen die Sektion
        sections = []
        for i in range(0, len(beats), self.bpp):
            chunk = beats[i:i + self.bpp]
            if len(chunk) < 4: continue
            
            avg_energy = sum(b.energy for b in chunk) / len(chunk)
            # Sektions-Heuristik
            sec_type = "chorus" if avg_energy > 0.6 else "verse"
            
            sections.append(SectionNode(
                id=f"sec_{i}", type=sec_type,
                start_time=chunk[0].timestamp, end_time=chunk[-1].timestamp,
                phrases=[PhraseNode(id=f"phr_{i}", start_time=chunk[0].timestamp, end_time=chunk[-1].timestamp, beats=chunk)],
                energy_level=avg_energy
            ))

        return SongAST(
            id=f"song_{hashlib.md5(mp3_path.read_bytes()).hexdigest()[:8]}",
            duration=float(librosa.get_duration(y=y, sr=sr)),
            bpm=float(tempo),
            sections=sections
        )