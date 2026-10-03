import os, subprocess, json, sys, shutil
from pathlib import Path

class OidasheimSoldatV46:
    def __init__(self):
        print("--- ⚔️ DER SOLDAT V46: KINETIC EXECUTION ---")
        self.temp_dir = Path(os.environ.get('TEMP', './')) / "oidasheim_v46_render"
        if self.temp_dir.exists(): shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, job_file):
        with open(job_file, 'r') as f:
            plan = json.load(f)
        
        chunks = []
        freq = round(plan['bpm'] / 60.0, 4)

        for i, entry in enumerate(plan['timeline']):
            out_chunk = self.temp_dir / f"c_{i}.mp4"
            
            # BASIS: Panzer-Pump
            amp = 0.04 + (entry['intensity'] * 0.1)
            z = f"(1.0+({amp}*abs(sin(2*PI*{freq}*t))))"
            
            vf = (f"scale=1440:810:force_original_aspect_ratio=increase,crop=1440:810,"
                  f"scale='iw*{z}':-1,crop=1280:720:(iw-ow)/2:(ih-oh)/2")

            # HARD HITTER EFFECT (RGB Split + Shake bei Punchlines)
            if entry['is_punchline']:
                # RGB Split via lutyuv
                vf += ",rgbashift=rh=5:bv=-5" 
                # Zusätzlicher Motion Blur
                vf += ",tblend=all_mode=average"

            # SWITCH EFFECT (Invert + Farbsprung)
            if entry['is_switch']:
                vf += ",hue=h=90:s=2,negate"

            # DRILL / FLOW SHIFT (Stutter)
            if entry['intensity'] > 0.85:
                vf += ",random=frames=2" # Erzeugt nervöses Zittern

            vf += ",format=yuv420p"

            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", "0", "-t", str(entry['duration']),
                "-i", entry['src'], "-vf", vf,
                "-c:v", "libx264", "-preset", "ultrafast", "-r", "24", "-an", str(out_chunk)
            ]
            subprocess.run(cmd)
            chunks.append(out_chunk)
            sys.stdout.write(f"\r⚔️ Mission {plan['track_id']}: Chunk {i+1} - Intensity {entry['intensity']}")

        # Final Muxing (NVENC)
        list_file = Path("final_list.txt")
        with open(list_file, "w") as f:
            for c in chunks: f.write(f"file '{c.as_posix()}'\n")

        final_out = Path(r'I:\Oidasheim\abfuck\honestly\done') / f"KINETIC_OVERLORD_{plan['track_id']}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                        "-i", plan['mp3_path'], "-c:v", "h264_nvenc", "-preset", "fast", 
                        "-shortest", str(final_out)], capture_output=True)
        print(f"\n✅ MASTERPIECE READY: {final_out.name}")

if __name__ == "__main__":
    # Erst General starten, dann Soldat
    soldier = OidasheimSoldatV46()
    for job in Path(r'I:\Oidasheim\abfuck\honestly\production_jobs').glob("*.json"):
        soldier.execute(job)