"""
ffmpeg_engine.py — FFmpeg & NVENC video rendering engine.
"""
import os
import subprocess
import shutil
from typing import List, Optional, Tuple
from genome_engine.compiler.timeline import EditDecisionList
from genome_engine.hardware import recommend_encode_plan, detect_hardware


class FFmpegRenderEngine:
    """Executes hardware-accelerated video rendering for EditDecisionList timelines."""

    def __init__(self, use_nvenc: bool = True, resolution: Tuple[int, int] = (1920, 1080)):
        self.use_nvenc = use_nvenc
        self.width, self.height = resolution
        self.hw = detect_hardware()
        self._check_nvenc_support()

    def _check_nvenc_support(self):
        """Verifies if NVENC is supported by ffmpeg on this system."""
        if not self.use_nvenc:
            return
        if not shutil.which("ffmpeg"):
            self.use_nvenc = False
            return
        try:
            res = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if "h264_nvenc" not in res.stdout:
                self.use_nvenc = False
        except Exception:
            self.use_nvenc = False

    def build_concat_script(self, edl: EditDecisionList, output_path: str) -> str:
        """Generates an FFmpeg concat demuxer script."""
        codec = "h264_nvenc" if self.use_nvenc else "libx264"
        preset = "p4" if self.use_nvenc else "medium"
        workers, threads = recommend_encode_plan(self.width, self.height, codec, preset, self.use_nvenc)

        lines = [
            f"# FFmpeg Concat Script for: {edl.track_path}",
            f"# Target Resolution: {self.width}x{self.height}",
            f"# Codec: {codec} (Preset: {preset}, Workers: {workers}, Threads: {threads})",
            ""
        ]
        
        for seg in edl.segments:
            clip = seg.assigned_clip_path or "placeholder.mp4"
            # Normalize path for FFmpeg concat script (forward slashes)
            clip_clean = os.path.abspath(clip).replace("\\", "/")
            lines.append(f"file '{clip_clean}'")
            lines.append(f"inpoint {seg.clip_in_sec:.3f}")
            lines.append(f"outpoint {seg.clip_out_sec:.3f}")

        return "\n".join(lines)

    def render(self, edl: EditDecisionList, output_path: str, dry_run: bool = True) -> bool:
        """Renders the timeline EDL into a final MP4 video file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        concat_script_path = output_path + ".concat.txt"
        script_content = self.build_concat_script(edl, output_path)
        
        with open(concat_script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        if dry_run:
            print(f"[DRY RUN] Generated concat script for {len(edl.segments)} segments at {concat_script_path}")
            return True

        if not shutil.which("ffmpeg"):
            print("[ERROR] ffmpeg executable not found on PATH. Cannot execute render.")
            return False

        codec = "h264_nvenc" if self.use_nvenc else "libx264"
        preset = "p4" if self.use_nvenc else "medium"

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_script_path,
        ]

        if edl.track_path and os.path.exists(edl.track_path):
            cmd.extend(["-i", os.path.abspath(edl.track_path)])
            cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-c:a", "aac"])

        cmd.extend([
            "-c:v", codec,
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-s", f"{self.width}x{self.height}",
            output_path
        ])

        try:
            print(f"[RENDER] Executing FFmpeg: {' '.join(cmd)}")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            if res.returncode != 0:
                print(f"[RENDER ERROR] FFmpeg failed with exit code {res.returncode}: {res.stderr[-300:]}")
                return False
            print(f"✅ Render Complete: {output_path}")
            return True
        except Exception as e:
            print(f"[RENDER EXCEPTION] {e}")
            return False
