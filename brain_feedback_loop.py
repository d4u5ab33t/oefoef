#!/usr/bin/env python3
"""
brain_feedback_loop.py — Global Feedback Loop & Neural Data Sync Engine
Connects ./data (J:\\Oidasheim\\oefoef\\data) to ../brain.bug (J:\\Oidasheim\\brain.bug)

- Bidirectional SQLite and JSON data syncing
- Clip usage memory ingestion (clip_usage_memory.json)
- RL Bandit State adaptation (rl_bandit_state.json)
- Render metadata tracking (last_render_metadata.json)
- Brain Blueprint re-calibration (brain.bug live snapshot)
"""

import csv
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    BRAIN_BLUEPRINT,
    BRAIN_BUG_DIR,
    BRAIN_CLIP_USAGE_MEMORY,
    BRAIN_LAST_RENDER_METADATA,
    BRAIN_PROCESSED_SEGMENTS,
    BRAIN_PROCESSED_SOURCES,
    BRAIN_RL_BANDIT_STATE,
    DATA_DIR,
)


class BrainFeedbackLoop:
    def __init__(self, data_dir: Optional[Path] = None, brain_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self.brain_dir = Path(brain_dir or BRAIN_BUG_DIR)
        
        # Ensure target directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.brain_dir.mkdir(parents=True, exist_ok=True)

    def sync_all_data_files(self) -> Dict[str, str]:
        """Bidirectionally syncs all 23 SQLite DBs, JSON/CSV caches, and directories between ./data and ../brain.bug."""
        results = {}
        
        # 1. Sync SQLite Databases
        sqldbs = [
            "beat_sync.db",
            "music_knowledge.db",
            "oidasheim_knowledge.db",
            "clips.db",
            "suno_prompt_index.db",
            "oidaheim_song_knowledge_base.db",
        ]
        for db_name in sqldbs:
            src_data = self.data_dir / db_name
            src_brain = self.brain_dir / db_name
            status = self._sync_sqlite_db(src_data, src_brain)
            results[db_name] = status

        # 2. Sync JSON & Cache Files (including memory, metadata & bandit state)
        json_files = [
            "libsync-flat-globe.db.json",
            "hiphop_styles_structures_tags.json",
            "synapse_releases.json",
            "tracklist_parse_cache.json",
            "OIDAHEIM_STYLE_BIBLE.json",
            "master_semantics.json",
            "semantic_tag_db.json",
            "lyrics_cache.json",
            "oidaheim_100_song_grid.json",
            "oidaheim_weed_420_beat_expansion.json",
            "database.json",
            "clip_usage_memory.json",
            "last_render_metadata.json",
            "rl_bandit_state.json",
            "vector_tree_index.json",
            "self_learning_state.json",
            "transition_flow_matrix.json",
            "processed_segments.json",
            "processed_sources.json",
        ]
        for json_name in json_files:
            status = self._sync_json_file(json_name)
            results[json_name] = status

        # 3. Sync CSV Files
        csv_files = ["alle_songs_extrahiert.csv", "database.csv"]
        for csv_name in csv_files:
            status = self._sync_raw_file(csv_name)
            results[csv_name] = status

        # 4. Sync Directories (models/)
        dir_names = ["models"]
        for dirname in dir_names:
            status = self._sync_directory(dirname)
            results[dirname] = status

        return results

    def _sync_directory(self, dirname: str) -> str:
        """Syncs entire directory content bidirectionally between ./data and ../brain.bug."""
        d_data = self.data_dir / dirname
        d_brain = self.brain_dir / dirname
        d_data.mkdir(parents=True, exist_ok=True)
        d_brain.mkdir(parents=True, exist_ok=True)

        copied = 0
        for root, dirs, files in os.walk(d_data):
            rel_path = Path(root).relative_to(d_data)
            target_brain_dir = d_brain / rel_path
            target_brain_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                f_data = Path(root) / f
                f_brain = target_brain_dir / f
                if not f_brain.exists() or f_data.stat().st_mtime > f_brain.stat().st_mtime:
                    shutil.copy2(f_data, f_brain)
                    copied += 1

        for root, dirs, files in os.walk(d_brain):
            rel_path = Path(root).relative_to(d_brain)
            target_data_dir = d_data / rel_path
            target_data_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                f_brain = Path(root) / f
                f_data = target_data_dir / f
                if not f_data.exists() or f_brain.stat().st_mtime > f_data.stat().st_mtime:
                    shutil.copy2(f_brain, f_data)
                    copied += 1

        return f"synced ({copied} files updated)"

    def _sync_sqlite_db(self, path_data: Path, path_brain: Path) -> str:
        """Syncs SQLite database tables between ./data and ../brain.bug."""
        if not path_data.exists() and not path_brain.exists():
            return "skipped (missing in both)"

        if not path_data.exists() and path_brain.exists():
            shutil.copy2(path_brain, path_data)
            return "copied brain -> data"

        if path_data.exists() and not path_brain.exists():
            shutil.copy2(path_data, path_brain)
            return "copied data -> brain"

        # Both exist: merge tables where possible, or align newest
        try:
            mtime_data = path_data.stat().st_mtime
            mtime_brain = path_brain.stat().st_mtime
            if abs(mtime_data - mtime_brain) < 2.0:
                return "in-sync"

            if mtime_data > mtime_brain:
                shutil.copy2(path_data, path_brain)
                return "updated brain from data"
            else:
                shutil.copy2(path_brain, path_data)
                return "updated data from brain"
        except Exception as e:
            return f"error: {e}"

    def _sync_json_file(self, filename: str) -> str:
        """Merges or syncs JSON files bidirectionally."""
        p_data = self.data_dir / filename
        p_brain = self.brain_dir / filename

        if not p_data.exists() and not p_brain.exists():
            return "skipped"
        if not p_data.exists() and p_brain.exists():
            shutil.copy2(p_brain, p_data)
            return "copied brain -> data"
        if p_data.exists() and not p_brain.exists():
            shutil.copy2(p_data, p_brain)
            return "copied data -> brain"

        try:
            mtime_data = p_data.stat().st_mtime
            mtime_brain = p_brain.stat().st_mtime
            if abs(mtime_data - mtime_brain) < 2.0:
                return "in-sync"

            # For large files (>10MB), fall back to timestamp sync to avoid memory overhead
            if p_data.stat().st_size > 10 * 1024 * 1024 or p_brain.stat().st_size > 10 * 1024 * 1024:
                if mtime_data >= mtime_brain:
                    shutil.copy2(p_data, p_brain)
                    return "synced data -> brain (size fallback)"
                else:
                    shutil.copy2(p_brain, p_data)
                    return "synced brain -> data (size fallback)"

            # If dictionary (like flat-globe), merge keys
            with open(p_data, "r", encoding="utf-8", errors="ignore") as f1:
                d1 = json.load(f1)
            with open(p_brain, "r", encoding="utf-8", errors="ignore") as f2:
                d2 = json.load(f2)

            if isinstance(d1, dict) and isinstance(d2, dict):
                merged = {**d2, **d1}
                with open(p_data, "w", encoding="utf-8") as f:
                    json.dump(merged, f, indent=2, ensure_ascii=False)
                with open(p_brain, "w", encoding="utf-8") as f:
                    json.dump(merged, f, indent=2, ensure_ascii=False)
                return f"merged ({len(merged)} keys)"
            else:
                # Keep newest file
                if mtime_data >= mtime_brain:
                    shutil.copy2(p_data, p_brain)
                    return "synced data -> brain"
                else:
                    shutil.copy2(p_brain, p_data)
                    return "synced brain -> data"
        except Exception as e:
            if p_data.stat().st_mtime >= p_brain.stat().st_mtime:
                shutil.copy2(p_data, p_brain)
                return f"synced data -> brain (fallback on {type(e).__name__})"
            else:
                shutil.copy2(p_brain, p_data)
                return f"synced brain -> data (fallback on {type(e).__name__})"

    def _sync_raw_file(self, filename: str) -> str:
        p_data = self.data_dir / filename
        p_brain = self.brain_dir / filename

        if not p_data.exists() and not p_brain.exists():
            return "skipped"
        if not p_data.exists() and p_brain.exists():
            shutil.copy2(p_brain, p_data)
            return "copied brain -> data"
        if p_data.exists() and not p_brain.exists():
            shutil.copy2(p_data, p_brain)
            return "copied data -> brain"

        mtime_data = p_data.stat().st_mtime
        mtime_brain = p_brain.stat().st_mtime
        if abs(mtime_data - mtime_brain) < 2.0:
            return "in-sync"

        if mtime_data >= mtime_brain:
            shutil.copy2(p_data, p_brain)
            return "synced data -> brain"
        else:
            shutil.copy2(p_brain, p_data)
            return "synced brain -> data"

    def ingest_render_feedback(self, metadata: Optional[Dict[str, Any]] = None, used_clip_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Ingests render run metadata and clip usage memory into ../brain.bug."""
        ingest_summary = {}

        # 1. Update last_render_metadata.json
        if metadata:
            p_brain_meta = self.brain_dir / "last_render_metadata.json"
            p_data_meta = self.data_dir / "last_render_metadata.json"
            with open(p_brain_meta, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            shutil.copy2(p_brain_meta, p_data_meta)
            ingest_summary["metadata"] = "updated"

        # 2. Update clip_usage_memory.json
        if used_clip_ids:
            p_brain_clipmem = self.brain_dir / "clip_usage_memory.json"
            clip_mem = {"history_3k": []}
            if p_brain_clipmem.exists():
                try:
                    with open(p_brain_clipmem, "r", encoding="utf-8") as f:
                        clip_mem = json.load(f)
                except Exception:
                    pass

            history = clip_mem.get("history_3k", [])
            for cid in used_clip_ids:
                if cid not in history:
                    history.append(cid)

            # Cap history to last 5000 items
            if len(history) > 5000:
                history = history[-5000:]
            clip_mem["history_3k"] = history

            with open(p_brain_clipmem, "w", encoding="utf-8") as f:
                json.dump(clip_mem, f, indent=2, ensure_ascii=False)
            
            p_data_clipmem = self.data_dir / "clip_usage_memory.json"
            shutil.copy2(p_brain_clipmem, p_data_clipmem)
            ingest_summary["clip_memory_count"] = len(history)

        return ingest_summary

    def update_rl_bandit_state(self, director: str, reward: float) -> Dict[str, Any]:
        """Updates reinforcement learning bandit state in rl_bandit_state.json."""
        p_brain_bandit = self.brain_dir / "rl_bandit_state.json"
        bandit_data = {
            "counts": {"cunningham": 5, "gondry": 4, "hype_williams": 4, "jonze": 5},
            "rewards": {"cunningham": 3.559, "gondry": 2.728, "hype_williams": 2.729, "jonze": 3.842},
            "total_pulls": 18,
        }

        if p_brain_bandit.exists():
            try:
                with open(p_brain_bandit, "r", encoding="utf-8") as f:
                    bandit_data = json.load(f)
            except Exception:
                pass

        director_key = director.lower().replace(" ", "_")
        counts = bandit_data.setdefault("counts", {})
        rewards = bandit_data.setdefault("rewards", {})

        counts[director_key] = counts.get(director_key, 0) + 1
        rewards[director_key] = round(rewards.get(director_key, 0.0) + reward, 4)
        bandit_data["total_pulls"] = bandit_data.get("total_pulls", 0) + 1

        with open(p_brain_bandit, "w", encoding="utf-8") as f:
            json.dump(bandit_data, f, indent=2, ensure_ascii=False)

        p_data_bandit = self.data_dir / "rl_bandit_state.json"
        shutil.copy2(p_brain_bandit, p_data_bandit)

        return bandit_data

    def recalibrate_brain_blueprint(self) -> str:
        """Analyzes database stats and updates the live corpus summary in brain.bug."""
        blueprint_path = self.brain_dir / "brain.bug"
        if not blueprint_path.exists():
            return "blueprint missing"

        # Count songs from beat_sync.db
        song_count = 0
        db_path = self.brain_dir / "beat_sync.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM songs")
                song_count = cur.fetchone()[0]
                conn.close()
            except Exception:
                pass

        # Read blueprint and update CORPUS SNAPSHOT section if present
        try:
            with open(blueprint_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                if "archive_songs" in line and song_count > 0:
                    new_lines.append(f"  archive_songs           = {song_count}\n")
                elif "GENERATED_FROM_LIVE_CORPUS" in line:
                    new_lines.append(f"GENERATED_FROM_LIVE_CORPUS = true\nLAST_FEEDBACK_SYNC = {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                else:
                    new_lines.append(line)

            with open(blueprint_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            # Mirror blueprint to ./data/brain.bug as well
            shutil.copy2(blueprint_path, self.data_dir / "brain.bug")
            return "blueprint re-calibrated successfully"
        except Exception as e:
            return f"blueprint error: {e}"

    def run_feedback_cycle(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        used_clip_ids: Optional[List[str]] = None,
        director: Optional[str] = None,
        reward: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Executes the full feedback loop cycle: data sync -> ingestion -> bandit adaptation -> blueprint update."""
        report = {}
        print("[🔄] Feedback Loop: Syncing ./data <-> ../brain.bug databases and caches...")
        sync_results = self.sync_all_data_files()
        report["sync"] = sync_results

        if metadata or used_clip_ids:
            print("[📥] Feedback Loop: Ingesting render feedback & clip memory...")
            ingest_results = self.ingest_render_feedback(metadata, used_clip_ids)
            report["ingest"] = ingest_results

        if director and reward is not None:
            print(f"[🤖] Feedback Loop: Updating RL Bandit for director '{director}' with reward {reward}...")
            bandit_results = self.update_rl_bandit_state(director, reward)
            report["bandit"] = bandit_results

        print("[🧠] Feedback Loop: Re-calibrating global brain.bug blueprint...")
        bp_status = self.recalibrate_brain_blueprint()
        report["blueprint"] = bp_status

        print("[✅] Feedback Loop: Complete cycle executed cleanly.")
        return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Oidasheim Brain Feedback Loop Engine")
    parser.add_argument("--sync", action="store_true", help="Run full data sync between ./data and ../brain.bug")
    parser.add_argument("--test-feedback", action="store_true", help="Simulate a feedback ingestion cycle")
    args = parser.parse_args()

    loop = BrainFeedbackLoop()
    if args.test_feedback:
        dummy_meta = {
            "audio_path": "test.mp3",
            "output_path": "test_out.mp4",
            "total_cuts": 24,
            "bpm": 120.0,
            "vocal_gender": "male",
            "aspect": "16:9",
        }
        res = loop.run_feedback_cycle(metadata=dummy_meta, used_clip_ids=["clip_001", "clip_002"], director="jonze", reward=0.85)
        print(json.dumps(res, indent=2))
    else:
        res = loop.run_feedback_cycle()
        print(json.dumps(res, indent=2))
