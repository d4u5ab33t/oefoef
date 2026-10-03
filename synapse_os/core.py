"""Deterministic, local-first Synapse OS release orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
from pathlib import Path


class ReleaseStage(str, Enum):
    DEMO = "demo"
    PRODUCTION = "production"
    RECORDING = "recording"
    EDITING = "editing"
    MIX = "mix"
    MASTER = "master"
    METADATA = "metadata"
    ARTWORK = "artwork"
    VIDEO = "video"
    CONTENT = "content"
    DISTRIBUTION = "distribution"
    PITCH = "pitch"
    CAMPAIGN = "campaign"
    ANALYTICS = "analytics"
    OPTIMIZATION = "optimization"
    ARCHIVE = "archive"


class Department(str, Enum):
    KAIRO = "kairo"
    VEGA = "vega"
    JINX = "jinx"
    ORION = "orion"
    ATLAS = "atlas"
    ECHO = "echo"
    NOVA = "nova"
    HELIX = "helix"
    AETHER = "aether"
    SENTINEL = "sentinel"


PIPELINE = (
    ReleaseStage.DEMO, ReleaseStage.PRODUCTION, ReleaseStage.RECORDING,
    ReleaseStage.EDITING, ReleaseStage.MIX, ReleaseStage.MASTER,
    ReleaseStage.METADATA, ReleaseStage.ARTWORK, ReleaseStage.VIDEO,
    ReleaseStage.CONTENT, ReleaseStage.DISTRIBUTION, ReleaseStage.PITCH,
    ReleaseStage.CAMPAIGN, ReleaseStage.ANALYTICS, ReleaseStage.OPTIMIZATION,
    ReleaseStage.ARCHIVE,
)

DEPARTMENT_OUTPUTS = {
    Department.KAIRO: ("production_session", "mix_ready_stems"),
    Department.VEGA: ("streaming_master", "instrumental", "tv_mix"),
    Department.JINX: ("shorts", "visualizer", "lyric_video", "promo_assets"),
    Department.ORION: ("distribution_plan", "playlist_pitch", "sync_targets"),
    Department.ATLAS: ("budget", "royalty_report", "forecast"),
    Department.ECHO: ("daily_report", "trend_report", "audience_snapshot"),
    Department.NOVA: ("artist_profile", "development_plan"),
    Department.HELIX: ("community_campaign", "newsletter"),
    Department.AETHER: ("render_manifest", "system_health"),
    Department.SENTINEL: ("quality_report", "release_approval"),
}


@dataclass
class ReleaseArtifact:
    kind: str
    path: str = ""
    status: str = "planned"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Release:
    release_id: str
    artist: str
    title: str
    stage: ReleaseStage = ReleaseStage.DEMO
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
    kpis: dict[str, float] = field(default_factory=dict)
    learning_events: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stage"] = self.stage.value
        return value


class ReleaseManager:
    """Plans releases and enforces stage/QC rules without external services."""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.releases: dict[str, Release] = {}
        if self.storage_path and self.storage_path.exists():
            self._load()

    def create_release(self, release_id: str, artist: str, title: str) -> Release:
        if release_id in self.releases:
            raise ValueError(f"Release already exists: {release_id}")
        release = Release(release_id, artist, title)
        self.releases[release_id] = release
        self._save()
        return release

    def get_release(self, release_id: str) -> Release:
        return self._get(release_id)

    def plan(self, release_id: str) -> list[ReleaseArtifact]:
        release = self._get(release_id)
        planned = list(release.artifacts)
        existing = {(artifact.kind, artifact.metadata.get("department"))
                    for artifact in release.artifacts}
        for department, kinds in DEPARTMENT_OUTPUTS.items():
            for kind in kinds:
                key = (kind, department.value)
                if key in existing:
                    continue
                artifact = ReleaseArtifact(kind, metadata={"department": department.value})
                release.artifacts.append(artifact)
                planned.append(artifact)
                existing.add(key)
        release.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return planned

    def advance(self, release_id: str, target: ReleaseStage | str,
                approvals: set[str] | None = None) -> Release:
        release = self._get(release_id)
        target = ReleaseStage(target)
        current_index = PIPELINE.index(release.stage)
        target_index = PIPELINE.index(target)
        if target_index != current_index + 1:
            raise ValueError(f"Invalid transition: {release.stage.value} -> {target.value}")
        required = {"sentinel", "aether"} if target in {
            ReleaseStage.VIDEO, ReleaseStage.DISTRIBUTION, ReleaseStage.ARCHIVE,
        } else set()
        if required - (approvals or set()):
            raise ValueError(f"Missing approvals: {sorted(required - (approvals or set()))}")
        release.stage = target
        release.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return release

    def record_kpis(self, release_id: str, values: dict[str, float]) -> Release:
        release = self._get(release_id)
        release.kpis.update({key: float(value) for key, value in values.items()})
        release.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return release

    def learn(self, release_id: str, situation: dict[str, Any], decision: str,
              result: float, why: str = "") -> None:
        release = self._get(release_id)
        release.learning_events.append({
            "situation": situation, "decision": decision,
            "result": float(result), "why": why,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def _get(self, release_id: str) -> Release:
        try:
            return self.releases[release_id]
        except KeyError as error:
            raise KeyError(f"Unknown release: {release_id}") from error

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps({key: release.to_dict() for key, release in self.releases.items()}, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.storage_path)

    def _load(self) -> None:
        raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        for key, value in raw.items():
            value["stage"] = ReleaseStage(value["stage"])
            value["artifacts"] = [ReleaseArtifact(**item) for item in value.get("artifacts", [])]
            self.releases[key] = Release(**value)
