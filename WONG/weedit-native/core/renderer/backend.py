import subprocess
from pathlib import Path
from typing import List
from core.ir import RenderIR

class FFmpegBackend:
    def render(self, timeline: List[RenderIR], output_path: Path, audio_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = output_path.parent / "temp"
        temp_dir.mkdir(exist_ok=True)
        processed = []
        for i, ir in enumerate(timeline):
            out_clip = temp_dir / f"clip_{i:04d}.mp4"
            duration = (ir.trim_out_ms - ir.trim_in_ms) / 1000.0
            start = ir.trim_in_ms / 1000.0
            filters = [f"trim=start={start}:duration={duration}", "setpts=PTS-STARTPTS"]
            if ir.camera_transform and ir.camera_transform.get("zoom", 1.0) != 1.0:
                z = ir.camera_transform["zoom"]
                filters.append(f"scale=iw*{z}:ih*{z},crop=iw/{z}:ih/{z}")
            cmd = ["ffmpeg", "-y", "-i", ir.clip_file_path, "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "ultrafast", str(out_clip)]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                processed.append(out_clip)
            except Exception as e:
                print(f"Warning: FFmpeg failed for {ir.clip_file_path}: {e}")
        if not processed: raise RuntimeError("No clips processed")
        concat_file = temp_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for p in processed: f.write(f"file '{p}'\n")
        concat_out = temp_dir / "concat.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(concat_out)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", str(concat_out), "-i", str(audio_path), "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(output_path)], check=True, capture_output=True)
        for p in processed: p.unlink()
        concat_file.unlink()
        concat_out.unlink()
        temp_dir.rmdir()
        return output_path
