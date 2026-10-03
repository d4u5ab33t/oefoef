import sqlite3
import subprocess
import json
from pathlib import Path
from typing import List

# Annahme: Pydantic Modelle aus dem vorherigen Systemdesign
# from core.models import ShotAST

class RenderEmitter:
    def __init__(self, db_path: str, width: int = 1080, height: int = 1920, fps: int = 24):
        self.db_path = db_path
        self.width = width
        self.height = height
        self.fps = fps

    def _get_clip_path(self, genome_id: str, cursor: sqlite3.Cursor) -> str:
        cursor.execute("SELECT path FROM clips WHERE sha256 = ?", (genome_id,))
        result = cursor.fetchone()
        if not result:
            raise FileNotFoundError(f"Genome ID {genome_id} nicht in DB gefunden!")
        return result[0]

    def emit(self, ast: 'ShotAST', mp3_path: str, output_path: str):
        """
        Kompiliert den ShotAST in einen FFmpeg Filtergraph.
        Das Audio der Clips wird ignoriert, die MP3 ist der Master-Track.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        inputs = [mp3_path]
        filter_chains = []
        concat_labels = []

        # 1. Pipeline: Jeden Shot auf das Zielformat normalisieren
        for idx, shot in enumerate(ast.shots):
            clip_path = self._get_clip_path(shot.resolved_genome_id, cur)
            inputs.append(clip_path)
            
            # Index-Offset: 0 ist MP3, Clips starten bei 1
            file_idx = idx + 1 
            
            # Filterkette: Trim -> Normierung -> FPS -> Scaling
            filter_str = (
                f"[{file_idx}:v]"
                f"trim=duration={shot.target_duration},"
                f"setpts=PTS-STARTPTS,"
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"fps={self.fps}"
                f"[v{idx}]"
            )
            filter_chains.append(filter_str)
            concat_labels.append(f"[v{idx}]")

        # 2. Concat-Node: Alle Videospuren zusammenfügen
        concat_filter = f"{''.join(concat_labels)}concat=n={len(ast.shots)}:v=1:a=0[outv]"
        filter_chains.append(concat_filter)

        # 3. FFmpeg Befehl bauen
        cmd = ["ffmpeg", "-y"]
        for inp in inputs:
            cmd.extend(["-i", inp])
            
        cmd.extend([
            "-filter_complex", ";".join(filter_chains),
            "-map", "[outv]",    # Video-Output aus dem Filtergraphen
            "-map", "0:a",       # Audio nur vom ersten Input (der MP3)
            "-c:v", "libx264",   # H.264 für maximale Kompatibilität
            "-crf", "18",        # High Quality
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-shortest",         # Stoppt beim Ende des kürzesten Streams (MP3)
            str(output_path)
        ])

        try:
            print(f"[RENDER] Starte FFmpeg-Kompilierung für {output_path}...")
            # stdout/stderr umleiten, damit die Konsole sauber bleibt
            subprocess.run(cmd, check=True)
            print("[OK] Render abgeschlossen.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] FFmpeg Render fehlgeschlagen: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    # Test-Aufruf des Renderers
    # emitter = RenderEmitter(db_path="database/genome_os.db")
    # emitter.emit(resolved_ast, "test.mp3", "output.mp4")
    pass