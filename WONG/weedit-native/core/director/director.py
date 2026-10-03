import yaml
from pathlib import Path
from typing import List, Dict, Any
from core.ir import SongAST, ShotIntent, CameraIntent

class StyleLoader:
    def __init__(self, styles_dir: Path = Path("./styles")):
        self.styles_dir = styles_dir
    def load(self, name: str) -> Dict[str, Any]:
        p = self.styles_dir / name / "camera.yaml"
        if p.exists():
            with open(p) as f: return yaml.safe_load(f)
        return {"default": {"movement": "static", "framing": "medium"}, "chorus": {"movement": "push", "framing": "closeup"}}

class Director:
    def __init__(self, style_name: str = "cinematic"):
        self.style = StyleLoader().load(style_name)

    def direct(self, song_ast: SongAST) -> List[ShotIntent]:
        intents = []
        for sec in song_ast.sections:
            for p_idx, phrase in enumerate(sec.phrases):
                cam_rules = self.style.get(sec.name, self.style.get("default", {}))
                movement = cam_rules.get("movement", "static")
                framing = cam_rules.get("framing", "medium")
                duration = phrase.end_ms - phrase.start_ms
                for i in range(2):
                    start = phrase.start_ms + (i * duration // 2)
                    end = start + (duration // 2)
                    intents.append(ShotIntent(
                        song_section=sec.name, phrase_id=f"{sec.name}_{p_idx}",
                        start_ms=start, end_ms=end,
                        need_energy=0.8 if sec.name=="chorus" else 0.5,
                        need_emotion=["high"] if sec.name=="chorus" else ["medium"],
                        need_color=[".warm", ".hero"] if sec.name=="chorus" else [".cold"],
                        need_camera=CameraIntent(movement=movement, framing=framing, persistence_id=f"{sec.name}_{p_idx}"),
                        need_rhythm="cut" if sec.name=="chorus" else "smooth",
                        continue_from_shot_id=None if i==0 else f"{sec.name}_{p_idx}_{i-1}"
                    ))
        return intents
