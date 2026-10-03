import json
from pathlib import Path
from typing import List
from core.ir import ReplayLog

class ReplayLogger:
    def __init__(self, project_dir: Path = Path.cwd()):
        self.replay_dir = project_dir / ".weed_cache" / "replay"
        self.replay_dir.mkdir(parents=True, exist_ok=True)
    def save_logs(self, logs: List[ReplayLog]):
        for log in logs:
            with open(self.replay_dir / f"{log.shot_id}.json", "w") as f:
                json.dump(log.model_dump(), f, indent=2, default=str)
    def load_all(self) -> List[ReplayLog]:
        logs = []
        for f in self.replay_dir.glob("*.json"):
            with open(f) as fp: logs.append(ReplayLog.model_validate(json.load(fp)))
        return logs
