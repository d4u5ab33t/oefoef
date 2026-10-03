#!/usr/bin/env python3
"""
Oidasheim Video Pipeline - Complete System
==========================================

This canvas contains the full Oidasheim video pipeline system:
- Oidasheim_Core_V22.py: Audio analysis & prompt generation
- Oidasheim_Soldat_V22.py: Video rendering with FFmpeg  
- Oidasheim_General_V22.py: HTML management & job coordination
- main.py: Pipeline orchestrator

Trigger: "Clip ist online!"
"""

# ============================================================================
# FILE: Oidasheim_Core_V22.py
# ============================================================================
import math
import gc
import librosa
import numpy as np

class OidasheimCoreV22:
    def analyze(self, path):
        y, sr = librosa.load(path, sr=11025, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        # Generierung von Video-Prompts und Analysedaten
        energy_avg = np.mean(rms)
        prompt = "Cyberpunk aesthetic, fast cuts, glitch art" if energy_avg > 0.1 else "Slow motion, aesthetic lo-fi, cinematic lighting"
        viral = "High" if energy_avg > 0.15 else "Medium"
        
        res = {
            "bpm": float(np.atleast_1d(tempo)[0]),
            "duration_ms": int(len(y)/sr * 1000),
            "energy_map": (rms / (np.max(rms) + 1e-9)).tolist(),
            "meta": {"prompt": prompt, "viral": viral}
        }
        return res

class VirtualCameraV22:
    def get_zoom_params(self, t_ms, avd_dict):
        a = avd_dict.get('a', 0.5)
        return {"z": round(1.0 + (a * 0.2), 3), "x": round(0.5 + (math.sin(t_ms / 1500.0) * 0.05), 3)}


# ============================================================================
# FILE: Oidasheim_Soldat_V22.py
# ============================================================================
import subprocess
import os
import json
from pathlib import Path

class SoldatV22:
    def execute(self, job_path):
        with open(job_path, 'r') as f:
            plan = json.load(f)
        
        # DJ-Style Rendering: Volle Länge, kein -ss 1.0 (startet bei 0)
        # afade für nahtlose Übergänge (Fade-in 2s, Fade-out 2s)
        duration_sec = plan.get('duration_sec', 0)
        fade_out_start = max(0, duration_sec - 2)
        
        cmd = [
            "ffmpeg", "-y", "-i", plan['mp3'],
            "-filter_complex", f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start}:d=2",
            "-c:v", "libx264", "-crf", "22", "-preset", "medium",
            str(Path(plan['mp3']).parent / f"FINAL_{Path(plan['mp3']).stem}.mp4")
        ]
        subprocess.run(cmd)


# ============================================================================
# FILE: Oidasheim_General_V22.py
# ============================================================================
import sqlite3
import json
import os
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

class GeneralV22:
    def __init__(self):
        self.audio_hub = Path(r"I:\Oidasheim\Musik\[BeatSync] Verst__rker Oida")
        self.jobs_dir = self.audio_hub / "production_jobs"
        self.jobs_dir.mkdir(exist_ok=True)
        self.compiler = OidasheimCoreV22()

    def update_html_and_plan(self):
        html_path = self.audio_hub / "FAVs07072026.html"
        with open(html_path, 'r+', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            # Hier Logik zur Tabellenerweiterung um Spalten: Prompt, Viral, Voting
            # ... (HTML Manipulation)
            f.seek(0)
            f.write(str(soup))


# ============================================================================
# FILE: main.py - Pipeline Orchestrator
# ============================================================================
import sys
from pathlib import Path
from bs4 import BeautifulSoup

class VideoPipeline:
    def __init__(self):
        self.audio_hub = Path(r"I:\Oidasheim\Musik\[BeatSync] Verst__rker Oida")
        self.jobs_dir = self.audio_hub / "production_jobs"
        self.jobs_dir.mkdir(exist_ok=True)
        self.compiler = OidasheimCoreV22()
        self.renderer = SoldatV22()
        self.html_path = self.audio_hub / "FAVs07072026.html"
        
    def find_mp3s(self):
        """Find all MP3 files in audio_hub that don't have a corresponding FINAL_*.mp4"""
        mp3_files = list(self.audio_hub.glob("*.mp3"))
        processed = set()
        
        for mp4 in self.audio_hub.glob("FINAL_*.mp4"):
            stem = mp4.stem.replace("FINAL_", "")
            processed.add(stem)
        
        return [mp3 for mp3 in mp3_files if mp3.stem not in processed]
    
    def create_job_plan(self, mp3_path):
        """Create a job plan for a single MP3"""
        analysis = self.compiler.analyze(str(mp3_path))
        duration_sec = analysis["duration_ms"] / 1000
        
        job = {
            "mp3": str(mp3_path),
            "output": str(Path(mp3_path).parent / f"FINAL_{mp3_path.stem}.mp4"),
            "analysis": analysis,
            "duration_sec": duration_sec,
            "fade_out_start": max(0, duration_sec - 2)
        }
        return job
    
    def save_job(self, job):
        """Save job to production_jobs directory"""
        job_path = self.jobs_dir / f"{Path(job['mp3']).stem}.json"
        with open(job_path, 'w') as f:
            json.dump(job, f, indent=2)
        return job_path
    
    def render_video(self, job):
        """Render video using SoldatV22"""
        temp_job = {
            "mp3": job["mp3"],
            "duration_sec": job["duration_sec"]
        }
        
        temp_job_path = self.jobs_dir / f"temp_{Path(job['mp3']).stem}.json"
        with open(temp_job_path, 'w') as f:
            json.dump(temp_job, f)
        
        self.renderer.execute(str(temp_job_path))
        temp_job_path.unlink(missing_ok=True)
    
    def update_html(self, job):
        """Update FAVs07072026.html with new video entry"""
        if not self.html_path.exists():
            with open(self.html_path, 'w', encoding='utf-8') as f:
                f.write("""<!DOCTYPE html>
<html>
<head><title>Oidasheim FAVs</title></head>
<body>
<table border="1">
<tr><th>Track</th><th>BPM</th><th>Duration</th><th>Energy</th><th>Prompt</th><th>Viral</th><th>Video</th><th>Voting</th></tr>
</table>
</body>
</html>""")
        
        with open(self.html_path, 'r+', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            table = soup.find('table')
            
            if not table:
                table = soup.new_tag('table', border="1")
                soup.body.append(table)
                header = soup.new_tag('tr')
                headers = ['Track', 'BPM', 'Duration', 'Energy', 'Prompt', 'Viral', 'Video', 'Voting']
                for h in headers:
                    th = soup.new_tag('th')
                    th.string = h
                    header.append(th)
                table.append(header)
            
            analysis = job['analysis']
            row = soup.new_tag('tr')
            
            # Track name
            td = soup.new_tag('td')
            td.string = Path(job['mp3']).stem
            row.append(td)
            
            # BPM
            td = soup.new_tag('td')
            td.string = f"{analysis['bpm']:.1f}"
            row.append(td)
            
            # Duration
            td = soup.new_tag('td')
            td.string = f"{analysis['duration_ms']/1000:.1f}s"
            row.append(td)
            
            # Energy
            td = soup.new_tag('td')
            energy_avg = sum(analysis['energy_map']) / len(analysis['energy_map']) if analysis['energy_map'] else 0
            td.string = f"{energy_avg:.3f}"
            row.append(td)
            
            # Prompt
            td = soup.new_tag('td')
            td.string = analysis['meta']['prompt']
            row.append(td)
            
            # Viral
            td = soup.new_tag('td')
            td.string = analysis['meta']['viral']
            row.append(td)
            
            # Video link
            td = soup.new_tag('td')
            video_path = Path(job['mp3']).parent / f"FINAL_{Path(job['mp3']).stem}.mp4"
            a = soup.new_tag('a', href=str(video_path))
            a.string = "Watch"
            td.append(a)
            row.append(td)
            
            # Voting
            td = soup.new_tag('td')
            td.string = ""
            row.append(td)
            
            table.append(row)
            
            f.seek(0)
            f.write(str(soup))
            f.truncate()
    
    def process_all(self):
        """Process all new MP3s in the audio hub"""
        mp3_files = self.find_mp3s()
        
        if not mp3_files:
            print("✅ No new MP3s to process")
            return 0
        
        print(f"🎵 Found {len(mp3_files)} new MP3(s) to process")
        
        for mp3_path in mp3_files:
            print(f"\n🔍 Processing: {mp3_path.name}")
            
            print("  📊 Analyzing audio...")
            job = self.create_job_plan(mp3_path)
            
            job_path = self.save_job(job)
            print(f"  💾 Job saved: {job_path.name}")
            
            print("  🎥 Rendering video...")
            self.render_video(job)
            
            print("  📄 Updating HTML...")
            self.update_html(job)
            
            print(f"  ✅ Completed: {mp3_path.name}")
        
        print(f"\n🎉 All {len(mp3_files)} videos rendered successfully!")
        return len(mp3_files)


if __name__ == "__main__":
    pipeline = VideoPipeline()
    
    if not pipeline.audio_hub.exists():
        print(f"❌ Error: Audio hub not found at {pipeline.audio_hub}")
        print("Please ensure the path I:\\Oidasheim\\Musik\\[BeatSync] Verst__rker Oida exists")
        sys.exit(1)
    
    print("🚀 Oidasheim Video Pipeline Started")
    print(f"📁 Scanning: {pipeline.audio_hub}")
    
    processed = pipeline.process_all()
    
    if processed > 0:
        print(f"\n🎬 {processed} music video(s) created and ready!")
    else:
        print("\n⏭️  No new MP3s found. Waiting for new content...")