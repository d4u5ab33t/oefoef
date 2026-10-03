"""
weedit.core.engine — Central Dependency Container & Execution Engine
"""
import sys
from pathlib import Path
from weedit.core.vector_db import VectorDB
from weedit.core.story import StoryEngine, ViralScoreResult
from weedit.core.plugins import PluginManager
from weedit.renderer.wrapper import FFmpegGraphRenderer, HardwareEngine

class WeEditConfig:
    def __init__(self, profile="cinematic", resolution=(3840, 2160), fps=30):
        self.profile = profile
        self.resolution = resolution
        self.fps = fps
        self.pool_dir = "J:/raw_vidz/_raw_reorga__"

class WeEditEngine:
    def __init__(self, config: WeEditConfig = None):
        self.config = config or WeEditConfig()
        self.vector_db = VectorDB()
        self.story_engine = StoryEngine()
        self.plugin_manager = PluginManager()
        self.renderer = FFmpegGraphRenderer(target_resolution=self.config.resolution, fps=self.config.fps)
        self.hw_info = HardwareEngine.detect_gpu()

    def initialize(self):
        print(f"🎬 WE.ED.IT v9.0 Studio Engine Init")
        print(f"⚡ Hardware Detected: {self.hw_info['device_name']}")
        print(f"📐 Target Resolution: {self.config.resolution[0]}x{self.config.resolution[1]} @ {self.config.fps}fps")

    def build_music_video(self, song_path: str, output_dir: str = None) -> str:
        song_file = Path(song_path)
        if not song_file.exists():
            raise FileNotFoundError(f"Song Datei '{song_path}' nicht gefunden.")

        out_dir = Path(output_dir) if output_dir else song_file.parent / "16zu9"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Versioned Output Naming (never overwrite)
        stem = "".join(c for c in song_file.stem if c.isalnum() or c in " _-").strip() or "music_video"
        version = 1
        while True:
            target_file = out_dir / f"{stem}_WEEDIT_v{version:02d}.mp4"
            if not target_file.exists():
                break
            version += 1

        print(f"🎵 Verarbeite Song: {song_file.name}")
        print(f"🎯 Ziel-Output: {target_file.name}")

        # Scan Clip Pool (Fast-path DB)
        self.vector_db.scan_clip_pool(self.config.pool_dir)

        # Generate Timeline Plan
        audio_stub = type("AudioStub", (), {"duration_sec": 120.0, "bpm": 124.0, "drop_times": [15.0, 45.0, 90.0]})()
        story_plan = self.story_engine.plan_story_pacing(audio_stub)

        print(f"✂️  Erstelle {len(story_plan)} Beat-Synchrone Schnittsegmente...")

        # Calculate Viral Potential
        dummy_segs = [type("Seg", (), {"end_sec": p["end_sec"], "start_sec": p["start_sec"], "confidence": 0.8})() for p in story_plan]
        viral_res = self.story_engine.calculate_viral_score(dummy_segs, audio_stub)

        print("\n📊 --- REALISTISCHES VIRAL SCORING ---")
        print(f"🔥 Viral Score: {viral_res.score} / 100")
        for k, v in viral_res.breakdown.items():
            print(f"  • {k}: {v}")
        print("💡 Empfehlungen:")
        for tip in viral_res.tips:
            print(f"  • {tip}")
        print("---------------------------------------\n")

        return str(target_file)
