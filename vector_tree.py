"""vector_tree.py — Hierarchischer Semantischer Vektor-Baum (Hierarchical Vector Tree Index).

Ermöglicht eine stetig wachsende, baumbasierte Indexierung und blitzschnelle
semantische Abfrage von Video-Clips im Clip-Pool:
- Multi-Level Hierarchie:
    * Ebene 0: Semantische Hauptdomänen (Urban, Bavarian, Cyber, Weed/420, Night, Action, Nature, Abstract)
    * Ebene 1: Feingliedrige Sub-Cluster (Voronoi/K-Means Centroids, Motion/Energy-Zonen)
    * Ebene 2: Blattknoten (Clips mit Vektor, Metadaten, gelernten Prioritäten)
- Stetige / inkrementelle Updates:
    * insert_clip() / update_clip() / rebalance()
    * reinforce_path(): Propagiert Render-Rewards durch den Baum nach oben
- Gezieltes Pruning & Branch-Traversierung für ultraschnelle Candidate-Retrievals
- Vollständige JSON/Cache-Persistenz in data/vector_tree_index.json
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from config import DATA_DIR, TAG_VOCAB
from cxx_accel.bridge import get_cxx_engine


# ── Vordefinierte Semantische DNA-Hauptdomänen ───────────────────────────────
SEMANTIC_DOMAINS: dict[str, list[str]] = {
    "URBAN_STREET": [
        "street", "urban", "hood", "block", "graffiti", "lowrider", "car", "bmw", "mercedes",
        "city", "concrete", "beton", "underground", "hiphop", "rap", "crew", "gang"
    ],
    "BAVARIAN_ROOTS": [
        "oida", "oidaheim", "bavaria", "munich", "bayern", "eisbach", "089", "tracht", "lederhose",
        "bier", "wiesn", "isar", "alpen", "weisswurst", "tradition"
    ],
    "CYBER_FUTURE": [
        "cyber", "cyberpunk", "future", "neon", "matrix", "synth", "laser", "hologram", "tech",
        "robot", "ai", "digital", "glitch", "hud", "grid", "circuit"
    ],
    "WEED_420_PSYCH": [
        "weed", "420", "smoke", "joint", "blunt", "high", "stoned", "psychedelic", "cloud",
        "trip", "cannabis", "ganja", "daze", "chill", "vibes", "purple", "green"
    ],
    "NIGHT_DARK": [
        "night", "dark", "shadow", "moon", "midnight", "dunkel", "nacht", "noir", "gloomy",
        "mystery", "smoke", "fog", "club", "party", "rave"
    ],
    "HIGH_ENERGY_ACTION": [
        "action", "fast", "speed", "drift", "fight", "fire", "explosion", "jump", "power",
        "intense", "rush", "adrenaline", "burn", "chase", "moshpit"
    ],
    "NATURE_ATMOSPHERIC": [
        "nature", "forest", "mountain", "sky", "water", "river", "sun", "sunset", "clouds",
        "wald", "berge", "fluss", "landscape", "drone", "space", "stars"
    ],
    "ABSTRACT_GLITCH": [
        "abstract", "glitch", "vfx", "texture", "pattern", "motion", "fractal", "kaleidoscope",
        "distort", "overlay", "visual", "art", "noise", "wave"
    ],
}

VECTOR_TREE_CACHE_FILE = DATA_DIR / "vector_tree_index.json"


def _norm(vec: list[float] | np.ndarray) -> float:
    if isinstance(vec, np.ndarray):
        return float(np.linalg.norm(vec))
    return math.sqrt(sum(v * v for v in vec))


def _cosine_dist(vec_a: list[float] | np.ndarray, vec_b: list[float] | np.ndarray) -> float:
    """Berechnet Cosine-Distanz (0.0 = identisch, 1.0 = orthogonal, 2.0 = entgegengesetzt)."""
    return get_cxx_engine().vtree_cosine_distance(vec_a, vec_b)



@dataclass
class LeafEntry:
    path: str
    vector: list[float]
    tags: list[str]
    motion_score: float
    motion_direction: float
    face_score: float
    gender: str
    duration: float
    information_density: float
    reward_prior: float = 0.5
    usage_count: int = 0
    last_reward: float = 0.0
    last_updated: float = field(default_factory=time.time)
    domain: str = "URBAN_STREET"

    @property
    def mean_reward(self) -> float:
        return self.reward_prior

    @property
    def uses(self) -> int:
        return self.usage_count

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "vector": self.vector,
            "tags": self.tags,
            "motion_score": self.motion_score,
            "motion_direction": self.motion_direction,
            "face_score": self.face_score,
            "gender": self.gender,
            "duration": self.duration,
            "information_density": self.information_density,
            "reward_prior": round(self.reward_prior, 4),
            "usage_count": self.usage_count,
            "last_reward": round(self.last_reward, 4),
            "last_updated": self.last_updated,
            "domain": self.domain,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LeafEntry:
        return cls(
            path=d["path"],
            vector=d.get("vector") or [],
            tags=d.get("tags") or [],
            motion_score=float(d.get("motion_score") or 0.5),
            motion_direction=float(d.get("motion_direction") or 0.0),
            face_score=float(d.get("face_score") or 0.0),
            gender=d.get("gender") or "neutral",
            duration=float(d.get("duration") or 0.0),
            information_density=float(d.get("information_density") or 0.5),
            reward_prior=float(d.get("reward_prior") or 0.5),
            usage_count=int(d.get("usage_count") or 0),
            last_reward=float(d.get("last_reward") or 0.0),
            last_updated=float(d.get("last_updated") or time.time()),
            domain=d.get("domain") or "URBAN_STREET",
        )


@dataclass
class TreeNode:
    node_id: str
    name: str
    level: int
    center_vector: list[float]
    radius: float = 1.0
    domain: str = "GENERAL"
    sub_clusters: list[TreeNode] = field(default_factory=list)
    leaf_keys: list[str] = field(default_factory=list)
    mean_motion: float = 0.5
    mean_energy: float = 0.5
    mean_reward: float = 0.5
    sample_count: int = 0
    last_reinforced: float = field(default_factory=time.time)

    def is_leaf_cluster(self) -> bool:
        return len(self.sub_clusters) == 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "level": self.level,
            "center_vector": [round(v, 4) for v in self.center_vector] if self.center_vector else [],
            "radius": round(self.radius, 4),
            "domain": self.domain,
            "sub_clusters": [c.to_dict() for c in self.sub_clusters],
            "leaf_keys": self.leaf_keys,
            "mean_motion": round(self.mean_motion, 4),
            "mean_energy": round(self.mean_energy, 4),
            "mean_reward": round(self.mean_reward, 4),
            "sample_count": self.sample_count,
            "last_reinforced": self.last_reinforced,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TreeNode:
        node = cls(
            node_id=d["node_id"],
            name=d.get("name", "Node"),
            level=int(d.get("level", 0)),
            center_vector=d.get("center_vector", []),
            radius=float(d.get("radius", 1.0)),
            domain=d.get("domain", "GENERAL"),
            leaf_keys=d.get("leaf_keys", []),
            mean_motion=float(d.get("mean_motion", 0.5)),
            mean_energy=float(d.get("mean_energy", 0.5)),
            mean_reward=float(d.get("mean_reward", 0.5)),
            sample_count=int(d.get("sample_count", 0)),
            last_reinforced=float(d.get("last_reinforced", time.time())),
        )
        node.sub_clusters = [cls.from_dict(c) for c in d.get("sub_clusters", [])]
        return node


class HierarchicalVectorTree:
    """Hierarchischer Semantischer Vektor-Baum mit stetigem Lernen und Pruning."""

    def __init__(self, vocab: Optional[list[str]] = None, cache_file: Optional[Path] = None):
        self.vocab = list(vocab or TAG_VOCAB)
        self.vocab_map = {term.lower(): i for i, term in enumerate(self.vocab)}
        self.cache_file = Path(cache_file or VECTOR_TREE_CACHE_FILE)
        self.leaves: dict[str, LeafEntry] = {}
        self.root: Optional[TreeNode] = None
        self.dimension: int = len(self.vocab)
        self.last_rebuild: float = 0.0
        self.is_dirty: bool = False

        # Domain Centroids vorbereiten
        self._init_empty_tree()

    def _init_empty_tree(self):
        """Initialisiert die Standard-Domänenstruktur."""
        self.root = TreeNode(
            node_id="ROOT",
            name="Oidaheim Semantic Vector Root",
            level=0,
            center_vector=[0.0] * self.dimension,
            radius=2.0,
            domain="ROOT",
        )
        for domain_name, terms in SEMANTIC_DOMAINS.items():
            center = [0.0] * self.dimension
            for term in terms:
                idx = self.vocab_map.get(term.lower())
                if idx is not None and idx < self.dimension:
                    center[idx] = 1.0
            norm_val = _norm(center)
            if norm_val > 0:
                center = [v / norm_val for v in center]

            domain_node = TreeNode(
                node_id=f"DOMAIN_{domain_name}",
                name=domain_name,
                level=1,
                center_vector=center,
                radius=1.2,
                domain=domain_name,
            )
            self.root.sub_clusters.append(domain_node)

    def build_from_globe(self, globe: dict[str, Any], force_rebuild: bool = False) -> int:
        """Baut den Vektor-Baum vollständig oder inkrementell aus dem Flat-Globe-Cache auf."""
        if not force_rebuild and self.load_tree():
            if len(self.leaves) == len(globe) and len(self.leaves) > 0:
                return len(self.leaves)

        self._init_empty_tree()
        self.leaves.clear()

        # 1. Blätter erfassen
        entries_added = 0
        for path, meta in globe.items():
            if meta.get("failed"):
                continue
            entry = self._meta_to_leaf(path, meta)
            if entry:
                self.leaves[path] = entry
                entries_added += 1

        if not self.leaves:
            return 0

        # 2. Den Blättern Domänen-Knoten und Sub-Cluster zuordnen
        for domain_node in self.root.sub_clusters:
            domain_node.sub_clusters.clear()
            domain_node.leaf_keys.clear()

        domain_nodes = self.root.sub_clusters
        domain_centers = np.asarray([d.center_vector for d in domain_nodes], dtype=np.float32)
        leaf_paths = list(self.leaves.keys())
        leaf_vectors = np.asarray([self.leaves[p].vector for p in leaf_paths], dtype=np.float32)

        # Batch-Cosine-Similarity zwischen allen Blättern und Domänenzentren
        sims = np.dot(leaf_vectors, domain_centers.T)
        domain_tagsets = [set(SEMANTIC_DOMAINS.get(d.domain, [])) for d in domain_nodes]

        for i, path in enumerate(leaf_paths):
            leaf = self.leaves[path]
            tagset = set(t.lower() for t in leaf.tags)
            bonus = np.array([len(tagset & dtags) * 0.4 for dtags in domain_tagsets], dtype=np.float32)
            scores = sims[i] + bonus
            best_domain_idx = int(np.argmax(scores))
            domain_nodes[best_domain_idx].leaf_keys.append(path)
            leaf.domain = domain_nodes[best_domain_idx].domain

        # 3. Sub-Clustering pro Domänenknoten (K-Means/Voronoi Sub-Partitions)
        for domain_node in self.root.sub_clusters:
            self._sub_cluster_domain_node(domain_node)
            self._update_node_aggregates(domain_node)

        self._update_node_aggregates(self.root)
        self.last_rebuild = time.time()
        self.is_dirty = True
        self.save_tree()
        return entries_added

    def _meta_to_leaf(self, path: str, meta: dict[str, Any]) -> Optional[LeafEntry]:
        """Konvertiert Globe-Metadaten in einen LeafEntry."""
        raw_vec = meta.get("vector") or meta.get("tag_vector")
        vec: list[float] = []
        if isinstance(raw_vec, (list, tuple)):
            vec = [float(v) for v in raw_vec]
            if len(vec) < self.dimension:
                vec.extend([0.0] * (self.dimension - len(vec)))
            elif len(vec) > self.dimension:
                vec = vec[:self.dimension]
        elif isinstance(raw_vec, dict):
            vec = [0.0] * self.dimension
            for k, v in raw_vec.items():
                idx = self.vocab_map.get(str(k).lower())
                if idx is not None and idx < self.dimension:
                    vec[idx] = float(v)
        else:
            # Baue Vektor aus Tags
            tags = meta.get("tags") or []
            vec = [0.0] * self.dimension
            for t in tags:
                idx = self.vocab_map.get(str(t).lower())
                if idx is not None and idx < self.dimension:
                    vec[idx] = 1.0

        norm_val = _norm(vec)
        if norm_val > 0:
            vec = [v / norm_val for v in vec]

        learned = meta.get("learned") or {}
        reward_prior = float(learned.get("avg_reward") or 0.5) if learned else 0.5
        usage_count = int(learned.get("uses") or 0) if learned else 0
        last_reward = float(learned.get("last_reward") or 0.0) if learned else 0.0

        return LeafEntry(
            path=path,
            vector=vec,
            tags=meta.get("tags") or [],
            motion_score=float(meta.get("motion_score") or 0.5),
            motion_direction=float(meta.get("motion_direction") or 0.0),
            face_score=float(meta.get("face_score") or 0.0),
            gender=meta.get("gender") or "neutral",
            duration=float(meta.get("duration") or 0.0),
            information_density=float(meta.get("information_density") or 0.5),
            reward_prior=reward_prior,
            usage_count=usage_count,
            last_reward=last_reward,
        )

    def _find_best_domain_node(self, leaf: LeafEntry) -> TreeNode:
        """Findet den passendsten Domänenknoten für ein Blatt."""
        # 1. Tag Match mit Domänen-Schlüsselwörtern
        leaf_tagset = {t.lower() for t in leaf.tags}
        best_score = -1.0
        best_node = self.root.sub_clusters[0]

        for domain_node in self.root.sub_clusters:
            domain_terms = set(SEMANTIC_DOMAINS.get(domain_node.domain, []))
            overlap = len(leaf_tagset & domain_terms)
            cos_dist = _cosine_dist(leaf.vector, domain_node.center_vector)
            sim_score = (1.0 - cos_dist) + (overlap * 0.4)
            if sim_score > best_score:
                best_score = sim_score
                best_node = domain_node

        return best_node

    def _sub_cluster_domain_node(self, domain_node: TreeNode, max_leafs_per_sub: int = 100):
        """Erstellt Sub-Cluster innerhalb eines Domänenknotens (Ebene 2)."""
        leaf_keys = domain_node.leaf_keys
        if len(leaf_keys) <= max_leafs_per_sub:
            return

        k = max(2, min(8, len(leaf_keys) // max_leafs_per_sub))
        valid_keys = [k for k in leaf_keys if k in self.leaves]
        if len(valid_keys) < k:
            return

        vectors = [self.leaves[k].vector for k in valid_keys]
        centers = self._quick_kmeans(vectors, k=k, max_iter=8)
        domain_node.sub_clusters.clear()

        # Erstelle Sub-Knoten
        for idx, center in enumerate(centers):
            sub_node = TreeNode(
                node_id=f"{domain_node.node_id}_SUB_{idx:02d}",
                name=f"{domain_node.name} Sub-{idx+1}",
                level=2,
                center_vector=center,
                radius=0.8,
                domain=domain_node.domain,
            )
            domain_node.sub_clusters.append(sub_node)

        # Schnelle Zuweisung mittels Vektormatrix-Dot-Product
        X = np.asarray(vectors, dtype=np.float32)
        C = np.asarray(centers, dtype=np.float32)
        sims = np.dot(X, C.T)
        labels = np.argmax(sims, axis=1)

        for l_key, label_idx in zip(valid_keys, labels):
            domain_node.sub_clusters[label_idx].leaf_keys.append(l_key)

        # Aktualisiere Aggregationen für alle Sub-Knoten
        for sub_node in domain_node.sub_clusters:
            self._update_node_aggregates(sub_node)

    def _quick_kmeans(self, vectors: list[list[float]], k: int = 4, max_iter: int = 8) -> list[list[float]]:
        """Ultraschnelle, SIMD/C++ beschleunigte K-Means Implementierung."""
        return get_cxx_engine().vtree_kmeans(vectors, k=k, max_iter=max_iter)

    def _update_node_aggregates(self, node: TreeNode):
        """Aktualisiert Centroids, Radius und Metrik-Durchschnitte eines Knotens mittels NumPy."""
        all_leaf_keys: list[str] = []
        if node.sub_clusters:
            for sub in node.sub_clusters:
                all_leaf_keys.extend(sub.leaf_keys)
        else:
            all_leaf_keys = node.leaf_keys

        node.sample_count = len(all_leaf_keys)
        if not all_leaf_keys:
            return

        leaf_objs = [self.leaves[k] for k in all_leaf_keys if k in self.leaves]
        if not leaf_objs:
            return

        motions = np.fromiter((l.motion_score for l in leaf_objs), dtype=np.float32, count=len(leaf_objs))
        energies = np.fromiter((l.information_density for l in leaf_objs), dtype=np.float32, count=len(leaf_objs))
        rewards = np.fromiter((l.reward_prior for l in leaf_objs), dtype=np.float32, count=len(leaf_objs))

        node.mean_motion = float(np.mean(motions))
        node.mean_energy = float(np.mean(energies))
        node.mean_reward = float(np.mean(rewards))

        if node.center_vector:
            c_vec = np.asarray(node.center_vector, dtype=np.float32)
            l_mat = np.asarray([l.vector for l in leaf_objs], dtype=np.float32)
            dists = 1.0 - np.dot(l_mat, c_vec)
            node.radius = float(max(0.1, np.max(dists)))

    # ── Stetige / Inkrementelle Updates & Feedback-Schleife ─────────────────────
    def insert_or_update_clip(self, path: str, meta: dict[str, Any]):
        """Fügt einen Clip inkrementell in den Vektor-Baum ein oder aktualisiert ihn."""
        leaf = self._meta_to_leaf(path, meta)
        if not leaf:
            return
        self.leaves[path] = leaf
        self.is_dirty = True

        best_domain_node = self._find_best_domain_node(leaf)
        target_node = best_domain_node
        if best_domain_node.sub_clusters:
            best_sub = min(best_domain_node.sub_clusters, key=lambda s: _cosine_dist(leaf.vector, s.center_vector))
            target_node = best_sub

        if path not in target_node.leaf_keys:
            target_node.leaf_keys.append(path)

        self._update_node_aggregates(target_node)
        self._update_node_aggregates(best_domain_node)
        self._update_node_aggregates(self.root)

    def reinforce_path(self, clip_path: str, reward: float, learning_rate: float = 0.15):
        """Propagiert Render-Feedback / Belohnung stetig durch den Baum nach oben."""
        leaf = self.leaves.get(clip_path)
        if not leaf:
            return

        leaf.usage_count += 1
        leaf.last_reward = reward
        # Exponential Moving Average (EMA)
        leaf.reward_prior = round(get_cxx_engine().ema_update(leaf.reward_prior, reward, learning_rate), 4)
        leaf.last_updated = time.time()
        self.is_dirty = True

        # Propagiere durch die Baumebenen
        for domain_node in self.root.sub_clusters:
            in_domain = False
            if domain_node.sub_clusters:
                for sub in domain_node.sub_clusters:
                    if clip_path in sub.leaf_keys:
                        sub.mean_reward = round(get_cxx_engine().ema_update(sub.mean_reward, reward, learning_rate * 0.5), 4)
                        sub.last_reinforced = time.time()
                        in_domain = True
            elif clip_path in domain_node.leaf_keys:
                in_domain = True

            if in_domain:
                domain_node.mean_reward = round(get_cxx_engine().ema_update(domain_node.mean_reward, reward, learning_rate * 0.3), 4)
                domain_node.last_reinforced = time.time()

    def query(
        self,
        target_vector: list[float] | np.ndarray,
        target_motion: Optional[float] = None,
        target_gender: Optional[str] = None,
        top_k: int = 40,
        branch_pruning: bool = True,
        use_learned_priors: bool = True,
    ) -> list[tuple[str, float]]:
        """Führt eine blitzschnelle baumbasierte semantische Suche mit Ast-Pruning durch.

        Returns:
            Liste von (clip_path, final_score) sortiert nach absteigendem Score.
        """
        if not self.root or not self.leaves:
            return []

        if isinstance(target_vector, (list, tuple)):
            t_vec = list(target_vector)
            if len(t_vec) < self.dimension:
                t_vec.extend([0.0] * (self.dimension - len(t_vec)))
            elif len(t_vec) > self.dimension:
                t_vec = t_vec[:self.dimension]
        else:
            t_vec = target_vector.tolist()

        norm_t = _norm(t_vec)
        if norm_t > 0:
            t_vec = [v / norm_t for v in t_vec]

        # 1. Domänen-Ranking (Ebene 1)
        domain_candidates: list[tuple[TreeNode, float]] = []
        for domain_node in self.root.sub_clusters:
            dist = _cosine_dist(t_vec, domain_node.center_vector)
            domain_candidates.append((domain_node, dist))

        domain_candidates.sort(key=lambda x: x[1])

        # Wenn Branch Pruning aktiv ist: Untersuche nur die relevantesten Domänen
        active_domains = domain_candidates[:4] if branch_pruning else domain_candidates

        # 2. Sub-Cluster & Blatt-Kandidaten sammeln
        candidate_keys: set[str] = set()
        for domain_node, _ in active_domains:
            if domain_node.sub_clusters:
                # Untersuche die 2 besten Sub-Cluster
                sub_dists = [(sub, _cosine_dist(t_vec, sub.center_vector)) for sub in domain_node.sub_clusters]
                sub_dists.sort(key=lambda x: x[1])
                for sub, _ in sub_dists[:3]:
                    candidate_keys.update(sub.leaf_keys)
            else:
                candidate_keys.update(domain_node.leaf_keys)

        # Fallback falls wenige Kandidaten gefunden wurden
        if len(candidate_keys) < top_k:
            candidate_keys.update(self.leaves.keys())

        cand_list = [k for k in candidate_keys if k in self.leaves]
        if not cand_list:
            return []

        gender_map = {"neutral": 0, "male": 1, "female": 2, "dual": 3}
        target_g_code = gender_map.get(str(target_gender).lower(), 0) if target_gender else 0
        target_m_val = float(target_motion) if target_motion is not None else -1.0

        leaf_vecs = [self.leaves[k].vector for k in cand_list]
        leaf_mots = [self.leaves[k].motion_score for k in cand_list]
        leaf_gens = [gender_map.get(self.leaves[k].gender.lower(), 0) for k in cand_list]
        leaf_rews = [self.leaves[k].reward_prior for k in cand_list]

        # Fast C++ Top-K candidate evaluation
        top_results = get_cxx_engine().vtree_query_candidates(
            query_vec=t_vec,
            leaf_vectors=leaf_vecs,
            leaf_motions=leaf_mots,
            leaf_genders=leaf_gens,
            leaf_rewards=leaf_rews,
            target_motion=target_m_val,
            target_gender=target_g_code,
            use_learned_priors=use_learned_priors,
            top_k=top_k,
        )

        return [(cand_list[idx], score) for idx, score in top_results]


    # ── Persistenz ─────────────────────────────────────────────────────────────
    def save_tree(self, path: Optional[Path] = None) -> bool:
        """Speichert den Vektor-Baum atomar auf die Festplatte."""
        target_path = Path(path or self.cache_file)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")

        try:
            data = {
                "version": "oida_vector_tree_v2",
                "dimension": self.dimension,
                "vocab_sample": self.vocab[:20],
                "last_rebuild": self.last_rebuild,
                "root": self.root.to_dict() if self.root else None,
                "leaves": {k: l.to_dict() for k, l in self.leaves.items()},
            }
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if target_path.exists():
                bak = target_path.with_suffix(".bak")
                try:
                    target_path.replace(bak)
                except OSError:
                    pass
            tmp_path.replace(target_path)
            self.is_dirty = False
            return True
        except Exception as e:
            print(f"[vector_tree] Fehler beim Speichern von {target_path}: {e}")
            return False

    def load_tree(self, path: Optional[Path] = None) -> bool:
        """Lädt den Vektor-Baum von der Festplatte."""
        target_path = Path(path or self.cache_file)
        if not target_path.exists():
            return False

        try:
            with target_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            self.dimension = int(data.get("dimension", len(self.vocab)))
            self.last_rebuild = float(data.get("last_rebuild", 0.0))
            if data.get("root"):
                self.root = TreeNode.from_dict(data["root"])
            if data.get("leaves"):
                self.leaves = {k: LeafEntry.from_dict(v) for k, v in data["leaves"].items()}
                if self.root:
                    for domain_node in self.root.sub_clusters:
                        for k in domain_node.leaf_keys:
                            if k in self.leaves:
                                self.leaves[k].domain = domain_node.domain
            self.is_dirty = False
            return True
        except Exception as e:
            print(f"[vector_tree] Fehler beim Laden von {target_path}: {e}")
            return False

    def stats(self) -> dict[str, Any]:
        """Gibt Diagnose- und Baum-Metriken zurück."""
        domain_counts = {}
        if self.root:
            for d in self.root.sub_clusters:
                total_leafs = len(d.leaf_keys)
                if d.sub_clusters:
                    total_leafs = sum(len(s.leaf_keys) for s in d.sub_clusters)
                domain_counts[d.domain] = {
                    "leaf_count": total_leafs,
                    "sub_clusters": len(d.sub_clusters),
                    "mean_reward": d.mean_reward,
                }

        return {
            "total_leaves": len(self.leaves),
            "dimension": self.dimension,
            "domains": domain_counts,
            "last_rebuild": self.last_rebuild,
        }


# Globales Singleton für nahtlose Pipeline-Nutzung
_GLOBAL_TREE: Optional[HierarchicalVectorTree] = None


def get_global_vector_tree() -> HierarchicalVectorTree:
    global _GLOBAL_TREE
    if _GLOBAL_TREE is None:
        _GLOBAL_TREE = HierarchicalVectorTree()
        _GLOBAL_TREE.load_tree()
    return _GLOBAL_TREE
