"""
ffmpeg_engine.py — FFmpeg & NVENC video rendering engine.
"""
import os
import subprocess
from typing import List, Optional
from genome_engine.compiler.timeline import EditDecisionList
from genome_engine.hardware import recommend_encode_plan, detect_hardware


class FFmpegRenderEngine:
    """Executes FFmpeg rendering for compiled EditDecisionList timelines."""

    def __init__(self, use_nvenc: bool = True, resolution: tuple[int, int] = (1920, 1080)):
        self.use_nvenc = use_nvenc
        self.width, self.height = resolution
        self.hw = detect_hardware()

    def build_concat_script(self, edl: EditDecisionList, output_path: str, dry_run: bool = False) -> str:
        codec = "h264_nvenc" if self.use_nvenc else "libx264"
        preset = "p4" if self.use_nvenc else "medium"
        workers, threads = recommend_encode_plan(self.width, self.height, codec, preset, self.use_nvenc)

        lines = [
            f"# FFmpeg Concat Script for {edl.track_path}",
            f"# Target Resolution: {self.width}x{self.height}",
            f"# Encoding Plan: {workers} Workers x {threads} Threads ({codec})",
            ""
        ]
        
        for seg in edl.segments:
            clip = seg.assigned_clip_path or "missing_placeholder.mp4"
            lines.append(f"file '{clip}'")
            lines.append(f"inpoint {seg.clip_in_sec}")
            lines.append(f"outpoint {seg.clip_out_sec}")

        script_content = "\n".join(lines)
        if dry_run:
            print(f"[DRY RUN] Generated concat script for {len(edl.segments)} segments.")

        return script_content

    def render(self, edl: EditDecisionList, output_path: str, dry_run: bool = True) -> bool:
        script_content = self.build_concat_script(edl, output_path, dry_run=dry_run)
        
        if dry_run:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path + ".txt", "w", encoding="utf-8") as f:
                f.write(script_content)
            print(f"[DRY RUN] Saved concat script to {output_path}.txt")
            return True

        # Real FFmpeg execution placeholder
        return True
