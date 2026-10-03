from pathlib import Path
from typing import List
from core.ir import ReplayLog, SongAST

class ReportGenerator:
    def __init__(self, song: SongAST, logs: List[ReplayLog]):
        self.song = song
        self.logs = logs
    def generate_html(self, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        avg_reward = sum(l.final_reward for l in self.logs) / len(self.logs) if self.logs else 0
        rows = "".join([f"<tr><td>{log.shot_id}</td><td>{log.intent.song_section}</td><td>{log.final_reward:.2f}</td><td>{', '.join(log.optimizer_passes_applied)}</td></tr>\n" for log in self.logs])
        html = f"""<!DOCTYPE html><html><head><title>WE.ED.IT Report</title>
        <style>body{{font-family:sans-serif;background:#111;color:#eee;padding:20px}}
        h1{{color:#0f0}}.stat{{background:#222;padding:15px;margin:10px 0;border-left:4px solid #0f0}}
        table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border-bottom:1px solid #444;text-align:left}}
        </style></head><body><h1>🧬 WE.ED.IT OIDA Report</h1>
        <p><b>{self.song.artist} - {self.song.title}</b></p>
        <div class="stat"><h3>Average Reward: {avg_reward:.2f}</h3></div>
        <div class="stat"><h3>Total Shots: {len(self.logs)}</h3></div>
        <h2>Shot Timeline</h2><table><tr><th>Shot ID</th><th>Section</th><th>Reward</th><th>Passes</th></tr>{rows}</table></body></html>"""
        with open(output_path, "w") as f: f.write(html)
        return output_path
