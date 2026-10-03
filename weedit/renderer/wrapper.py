"""
weedit.renderer.wrapper — FFmpeg Production Wrapper, GPU Auto-Detection & Bass-Wobble Engine
"""
import os
import sys
import subprocess
from pathlib import Path

class HardwareEngine:
    @staticmethod
    def detect_gpu() -> dict:
        info = {"gpu_type": "cpu", "encoder": "libx264", "device_name": "CPU Fallback"}
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=5)
            stdout = out.stdout
            if "h264_nvenc" in stdout:
                info = {"gpu_type": "nvidia", "encoder": "h264_nvenc", "device_name": "NVIDIA NVENC (CUDA Accelerated)"}
            elif "h264_qsv" in stdout:
                info = {"gpu_type": "intel", "encoder": "h264_qsv", "device_name": "Intel QuickSync"}
            elif "h264_amf" in stdout:
                info = {"gpu_type": "amd", "encoder": "h264_amf", "device_name": "AMD AMF"}
        except Exception:
            pass
        return info

class FFmpegGraphRenderer:
    def __init__(self, target_resolution=(3840, 2160), fps=30):
        self.resolution = target_resolution
        self.fps = fps
        self.hw_info = HardwareEngine.detect_gpu()

    def build_bass_wobble_filter(self, duration: float) -> str:
        # Center-outward wobble zoom pulsing on bass beats
        w, h = self.resolution
        total_frames = max(1, round(duration * self.fps))
        t_expr = f"(on/{total_frames})"
        z_expr = f"1.05+0.12*abs(sin(2*PI*4*{t_expr}))*exp(-1.5*{t_expr})"
        margin_x = "(iw-iw/zoom)/2"
        margin_y = "(ih-ih/zoom)/2"
        return f"zoompan=z='{z_expr}':x='{margin_x}':y='{margin_y}':d=1:s={w}x{h}:fps={self.fps}"

    def render_segment(self, clip_path: str, clip_in: float, duration: float, out_path: Path, use_wobble: bool = False) -> bool:
        w, h = self.resolution
        
        if use_wobble:
            vf = self.build_bass_wobble_filter(duration)
        else:
            # 16:9 crop-fill maintaining aspect ratio
            margin_x = "(iw-iw/zoom)/2"
            margin_y = "(ih-ih/zoom)/2"
            vf = f"zoompan=z='1.05':x='{margin_x}':y='{margin_y}':d=1:s={w}x{h}:fps={self.fps}"

        cmd = [
            "ffmpeg", "-y", "-nostdin", "-ss", f"{clip_in:.3f}", "-i", clip_path,
            "-vf", vf, "-an", "-c:v", self.hw_info["encoder"], "-pix_fmt", "yuv420p"
        ]

        if self.hw_info["gpu_type"] == "nvidia":
            cmd += ["-rc", "vbr", "-cq", "20", "-b:v", "0"]
        else:
            cmd += ["-crf", "20", "-preset", "fast"]

        cmd += ["-t", f"{duration:.3f}", str(out_path)]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return res.returncode == 0 and out_path.exists()
        except Exception:
            return False
