"""semantic_matching.py — Song<->Clip semantische Matching-Funktionen.

Ausgelagert aus main.py (Refactor: main.py war auf > 1150 Zeilen angewachsen
und vermischte Pipeline-Orchestrierung mit reiner Score-Berechnung). Enthält
alles, was einen Clip anhand von Tag-Vektor/Gender/Mood-Overlap gegen ein
Song-Segment bewertet:

- calculate_semantic_match(): gewichteter Gesamt-Score (0..1) mit C++ Native Acceleration
- semantic_match_reason(): menschenlesbare Begründung dafür, landet pro
  Segment im EDL als "match_reason" (siehe main.py::_build_render_script)
- concept_cluster_overlap(): semantische Konzept-Cluster-Affinität (Weed/420, Urban, Speed, Bavaria, etc.)
- object_grounding_score(): visuelle Bestätigung durch Object-Detection-Grounding

Reines Scoring/Text -- kein main.py-spezifischer Zustand, keine Seiteneffekte.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import TAG_VOCAB


# ── Semantische Konzept-Cluster & Synonym-Graphen ────────────────────────────
CONCEPT_CLUSTERS: Dict[str, Set[str]] = {
    "weed_420": {
        "weed", "420", "kush", "blunt", "joint", "bong", "gras", "kiffen",
        "thc", "stoned", "dope", "haze", "hasch", "tüte", "grinder", "smoke",
        "high", "spliff", "cannabis", "ganja", "rauchen", "pot", "herb", "paper",
    },
    "urban_street": {
        "street", "hood", "gang", "crew", "underground", "graffiti", "sprayer",
        "spraydose", "knast", "jva", "haftstrafenquartett", "acab", "mvv", "zug",
        "zuege", "train", "trains", "spray", "wall", "tunnel", "subway", "ubahn",
        "sbahn", "gleis", "bahnhof", "yard", "hustle", "grind", "bars", "ghetto",
        "asphalt", "block", "corner", "sidewalk",
    },
    "speed_motion": {
        "car", "cars", "auto", "drift", "speed", "race", "bmw", "mercedes",
        "porsche", "audi", "drive", "burnout", "motor", "engine", "exhaust",
        "rapid", "hyper", "fast", "action", "chase", "wheels", "turbo", "nitro",
        "acceleration", "vehicle", "highway", "rennen",
    },
    "party_night": {
        "party", "club", "night", "rave", "dj", "lights", "laser", "dance",
        "dancing", "crowd", "bar", "drinks", "bass", "festival", "stage", "neon",
        "vip", "disco", "strobe", "alcohol", "shot", "beer", "bier", "vodka",
        "celebration", "feiern",
    },
    "bavarian_culture": {
        "oida", "oidasheim", "minga", "089", "stadelheim", "oktoberfest",
        "wiesn", "dirndl", "lederhosen", "tracht", "trachten", "bier", "beer",
        "wurscht", "weisswurscht", "bavaria", "bayern", "isarnetz", "mia san mia",
        "tuetue", "oefoef",
    },
    "luxury_wealth": {
        "cash", "money", "geld", "gold", "golden", "diamond", "rolex", "luxury",
        "rich", "bling", "flex", "scheine", "million", "boss", "champagne",
        "yacht", "penthouse", "ice", "stack", "wealth", "crown",
    },
    "cyber_tech": {
        "cyber", "glitch", "neon", "matrix", "future", "robot", "ai", "hologram",
        "tech", "digital", "terminal", "synth", "virtual", "data", "wireframe",
        "laser", "code", "hacker", "futuristic", "sci-fi",
    },
    "nature_chill": {
        "nature", "mountain", "forest", "sky", "cloud", "sunset", "sunrise",
        "sea", "ocean", "river", "chill", "dreamy", "ambient", "zen", "peaceful",
        "rain", "fog", "storm", "landscape", "water", "sun", "calm",
    },
    "combat_action": {
        "fight", "punch", "kick", "boxing", "martial", "aggressive", "menacing",
        "battle", "war", "soldier", "sword", "combat", "shadow", "duel", "intense",
    },
}

CLUSTER_BITS: Dict[str, int] = {
    "weed_420": 1 << 0,
    "urban_street": 1 << 1,
    "speed_motion": 1 << 2,
    "party_night": 1 << 3,
    "bavarian_culture": 1 << 4,
    "luxury_wealth": 1 << 5,
    "cyber_tech": 1 << 6,
    "nature_chill": 1 << 7,
    "combat_action": 1 << 8,
}

CLUSTER_EMOJIS: Dict[str, str] = {
    "weed_420": "🌿 Weed/420",
    "urban_street": "🏙️ Urban/Street",
    "speed_motion": "🏎️ Speed/Cars",
    "party_night": "🎉 Party/Club",
    "bavarian_culture": "🥨 Bavaria/089",
    "luxury_wealth": "💎 Luxury/Cash",
    "cyber_tech": "⚡ Cyber/Tech",
    "nature_chill": "🏔️ Nature/Chill",
    "combat_action": "🥊 Combat/Action",
}

VISUAL_SCENE_VOCAB: Dict[str, List[str]] = {
    "CAR_VEHICLE": [
        "car", "cars", "bmw", "mercedes", "benz", "lowrider", "auto", "porsche", "audi",
        "drive", "drift", "speed", "motor", "wheels", "ride", "highway", "autobahn", "engine"
    ],
    "WEAPON_COMBAT": [
        "fist", "fists", "blade", "knife", "punch", "fight", "war", "battle", "gun",
        "cage", "coliseum", "hit", "strike", "blood", "scar", "chokehold", "boxen", "schlagen", "weapon"
    ],
    "WEED_SMOKE": [
        "weed", "smoke", "joint", "blunt", "kush", "bong", "high", "stoned", "puff",
        "cloud", "purple", "green", "daze", "trip", "kiffen", "tüte", "ganja", "cannabis"
    ],
    "CASH_LUXURY": [
        "money", "cash", "gold", "dollar", "euro", "chain", "chains", "diamonds",
        "rich", "boss", "queen", "king", "crown", "linen", "silk", "geld", "million"
    ],
    "NIGHT_CLUB": [
        "night", "dark", "moon", "shadow", "club", "party", "rave", "lights",
        "disco", "drink", "bar", "cocktail", "stage", "dunkel", "nacht"
    ],
    "CYBER_NEON": [
        "neon", "cyber", "laser", "matrix", "synth", "glitch", "screen",
        "digital", "tech", "future", "hud", "circuit", "robot", "grid"
    ],
    "BAVARIAN_ROOTS": [
        "oida", "bier", "beer", "wiesn", "eisbach", "089", "munich", "bayern",
        "lederhose", "weisswurst", "isar", "alpen", "minga"
    ],
    "NATURE_OUTDOORS": [
        "nature", "forest", "mountain", "sky", "water", "river", "sun", "rain",
        "tree", "clouds", "stars", "sea", "ocean", "wald", "berge", "fluss"
    ],
}


def compute_cluster_mask(terms: Set[str] | List[str] | str) -> int:
    """Berechnet die 32-Bit-Maske der aktivierten Konzept-Cluster für eine Term-Menge oder Text."""
    if not terms:
        return 0
    if isinstance(terms, str):
        term_set = set(re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{2,}", terms.lower()))
    else:
        term_set = set(str(t).lower() for t in terms if t)
    mask = 0
    for cluster_name, cluster_words in CONCEPT_CLUSTERS.items():
        if term_set & cluster_words:
            mask |= CLUSTER_BITS.get(cluster_name, 0)
    return mask


def extract_clip_terms(clip_meta: Any) -> Set[str]:
    """Extrahiert alle normalisierten Tags, erkannten Objekte, Szenarien und Pfad-Tokens
    eines Clips zu einer gemeinsamen semantischen Term-Menge."""
    if not clip_meta or not isinstance(clip_meta, dict):
        return set()

    terms: Set[str] = set()

    # 1. Tags
    for t in clip_meta.get("tags") or []:
        if isinstance(t, str):
            terms.add(t.strip().lower())

    # 2. Visuelle Objekte (YOLO / Vision Model)
    for obj in clip_meta.get("objects") or []:
        if isinstance(obj, str):
            terms.add(obj.strip().lower())
        elif isinstance(obj, dict) and "label" in obj:
            terms.add(str(obj["label"]).strip().lower())

    # 3. Szenarien / Scene
    for sc in clip_meta.get("scenarios") or []:
        if isinstance(sc, str):
            terms.add(sc.strip().lower())
    if "scene" in clip_meta and isinstance(clip_meta["scene"], str):
        terms.add(clip_meta["scene"].strip().lower())

    # 4. Domain
    if "domain" in clip_meta and isinstance(clip_meta["domain"], str):
        terms.add(clip_meta["domain"].strip().lower())

    # 5. Filename / Path Tokens
    path = clip_meta.get("path") or ""
    if path:
        stem = re.split(r"[\\/_.\-\s]+", str(path).lower())
        for token in stem:
            if len(token) >= 3 and token not in ("mp4", "mov", "mkv", "avi", "clip", "video"):
                terms.add(token)

    return terms


def extract_vector(obj: Any, key: str = "tag_vector"):
    if obj is None:
        return None
    vec = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    return vec if vec else None


def cosine_similarity(vec_a, vec_b) -> float | None:
    """Gibt None zurück, wenn KEIN echtes Signal vorliegt (mind. einer der
    beiden Vektoren hat Norm 0, d.h. keine einzige TAG_VOCAB-Komponente ist
    gesetzt). Beschleunigt über C++ Native AVX2 SIMD Engine mit Fallback."""
    if not vec_a or not vec_b:
        return None
    if isinstance(vec_a, dict) or isinstance(vec_b, dict):
        a = vec_a if isinstance(vec_a, dict) else dict(enumerate(vec_a))
        b = vec_b if isinstance(vec_b, dict) else dict(enumerate(vec_b))
        smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
        dot = sum(v * larger[k] for k, v in smaller.items() if k in larger)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
    else:
        n = min(len(vec_a), len(vec_b))
        if n == 0:
            return None

        # C++ AVX2 Native Acceleration Path
        try:
            import cxx_accel
            import ctypes
            cxx = cxx_accel.get_cxx_engine()
            if cxx.is_native_active and cxx._dll:
                # Schnelle Prüfung auf Nullvektoren
                norm_a_zero = all(x == 0.0 for x in vec_a[:n])
                norm_b_zero = all(x == 0.0 for x in vec_b[:n])
                if norm_a_zero or norm_b_zero:
                    return None

                arr_a = (ctypes.c_float * n)(*(float(x) for x in vec_a[:n]))
                arr_b = (ctypes.c_float * n)(*(float(x) for x in vec_b[:n]))
                sim = cxx._dll.cxx_fast_cosine(arr_a, arr_b, n)
                return max(-1.0, min(1.0, float(sim)))
        except Exception:
            pass

        vec_a, vec_b = vec_a[:n], vec_b[:n]
        dot = sum(vec_a[i] * vec_b[i] for i in range(n))
        norm_a = math.sqrt(sum(v * v for v in vec_a))
        norm_b = math.sqrt(sum(v * v for v in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return None
    similarity = dot / (norm_a * norm_b)
    return max(-1.0, min(1.0, similarity))


def calculate_vector_match(clip_meta: Any, song_tag_vector) -> float | None:
    clip_vector = extract_vector(clip_meta, "vector")
    if clip_vector is None:
        clip_vector = extract_vector(clip_meta, "tag_vector")
    if clip_vector is None or not song_tag_vector:
        return None
    raw = cosine_similarity(song_tag_vector, clip_vector)
    if raw is None:
        return None
    return round((raw + 1.0) / 2.0, 4)


def gender_alignment_score(clip_meta: Any, song_mc_gender: str | None) -> float | None:
    """Bewertet die Übereinstimmung des Lead-MC-Geschlechts mit dem visuellen Clip-Inhalt.
    Berücksichtigt Personenanzahl, Faces und Gender-Vektoren."""
    if not song_mc_gender or song_mc_gender not in ("male", "female", "dual"):
        return None
    if not clip_meta or not isinstance(clip_meta, dict):
        return None

    gender_vector = extract_vector(clip_meta, "gender_vector") or {}
    clip_str_gender = clip_meta.get("gender")
    person_count = int(clip_meta.get("person_count", 0)) if clip_meta.get("person_count") is not None else 0
    faces_count = len(clip_meta.get("faces") or [])

    has_female = False
    has_male = False

    if isinstance(gender_vector, dict):
        has_female = bool(gender_vector.get("female"))
        has_male = bool(gender_vector.get("male"))
    if clip_str_gender:
        cs = str(clip_str_gender).lower()
        if cs in ("female", "f", "woman", "girl"):
            has_female = True
        elif cs in ("male", "m", "man", "boy"):
            has_male = True
        elif cs in ("dual", "both", "duet"):
            has_female = True
            has_male = True

    if not has_female and not has_male:
        # Kein Personen-/Gender-Signal -> Neutral / Scenery / B-Roll
        return None

    if song_mc_gender == "dual":
        if has_female and has_male:
            return 1.0
        if person_count >= 2 or faces_count >= 2:
            return 0.95
        return 0.75  # Entweder Mann oder Frau passt im Duett-Wechsel

    has_same = has_female if song_mc_gender == "female" else has_male
    has_opposite = has_male if song_mc_gender == "female" else has_female

    if has_same and not has_opposite:
        return 1.0
    if has_same and has_opposite:
        return 0.85  # Gruppen-/Mixed-Shot mit passendem Lead-Geschlecht
    if has_opposite and not has_same:
        return 0.0
    return 0.5


def mood_tag_overlap_score(clip_meta: Any, song_mood_tags: list | None,
                           song_style_weights: dict | None = None) -> float | None:
    """Overlap zwischen Song-Mood-Tags (song_semantics.analyze_lyrics) und
    Clip-Tags/Objects/Scenarios mit Term-Gewichtung."""
    if not song_mood_tags or not clip_meta:
        return None
    clip_terms = extract_clip_terms(clip_meta)
    if not clip_terms:
        return None
    mood_terms = [t.lower() for t in song_mood_tags if t]
    if not mood_terms:
        return None

    if song_style_weights:
        weights = {t.lower(): w for t, w in song_style_weights.items() if w}
        total_weight = sum(weights.get(t, 0) for t in mood_terms)
        if total_weight <= 0:
            hits = sum(1 for t in mood_terms if t in clip_terms)
            return round(hits / len(mood_terms), 4)
        matched_weight = sum(weights.get(t, 0) for t in mood_terms if t in clip_terms)
        return round(matched_weight / total_weight, 4)

    hits = sum(1 for t in mood_terms if t in clip_terms)
    return round(hits / len(mood_terms), 4)


def object_grounding_score(clip_meta: Any, song_mood_tags: list | None,
                           song_terms: Set[str] | None = None) -> Tuple[float, List[str]]:
    """Prüft, ob im Clip visuell erkannte Objekte (YOLO/Object-Detection) die Lyrics
    oder Song-Konzepte direkt bestätigen (z.B. 'train' / 'car' / 'bottle' / 'smoke')."""
    if not clip_meta or not isinstance(clip_meta, dict):
        return 0.0, []

    detected_objects: Set[str] = set()
    for obj in clip_meta.get("objects") or []:
        if isinstance(obj, str):
            detected_objects.add(obj.strip().lower())
        elif isinstance(obj, dict) and "label" in obj:
            detected_objects.add(str(obj["label"]).strip().lower())

    if not detected_objects:
        return 0.0, []

    target_terms = set(song_terms or set())
    if song_mood_tags:
        target_terms.update(t.lower() for t in song_mood_tags if t)

    if not target_terms:
        return 0.0, []

    direct_hits = sorted(detected_objects & target_terms)
    if direct_hits:
        score = min(1.0, 0.6 + 0.2 * len(direct_hits))
        return round(score, 4), direct_hits

    # Cluster-basierte Objekt-Affinität
    clip_mask = compute_cluster_mask(detected_objects)
    song_mask = compute_cluster_mask(target_terms)
    if clip_mask & song_mask:
        return 0.5, list(detected_objects)[:3]

    return 0.0, []


def calculate_semantic_match(clip_meta: Any, song_tag_vector,
                              song_mood_tags: list | None = None,
                              song_mc_gender: str | None = None,
                              song_style_weights: dict | None = None,
                              song_visual_objects: list | None = None,
                              song_cluster_mask: int | None = None) -> float | None:
    """Berechnet den multi-modalen, gewichteten semantischen Gesamtscore (0..1)
    unter Einbezug von Vector-Embedding, Mood-Tags, Konzept-Clustern, Object-Grounding
    und MC-Gender-Alignment. Beschleunigt über das native C++ Engine-Modul."""
    tag_score = calculate_vector_match(clip_meta, song_tag_vector)
    gender_score = gender_alignment_score(clip_meta, song_mc_gender)
    mood_score = mood_tag_overlap_score(clip_meta, song_mood_tags, song_style_weights)

    clip_terms = extract_clip_terms(clip_meta)
    song_terms = set(kw for kw, v in zip(TAG_VOCAB, song_tag_vector) if v) if song_tag_vector else set()
    if song_mood_tags:
        song_terms.update(t.lower() for t in song_mood_tags if t)
    if song_visual_objects:
        for v in song_visual_objects:
            if v:
                v_str = str(v).lower()
                song_terms.add(v_str)
                cat_words = VISUAL_SCENE_VOCAB.get(v) or VISUAL_SCENE_VOCAB.get(v.upper()) or []
                for cw in cat_words:
                    song_terms.add(cw.lower())

    clip_cluster_mask = compute_cluster_mask(clip_terms)
    computed_song_mask = compute_cluster_mask(song_terms)
    if song_cluster_mask is not None and song_cluster_mask > 0:
        computed_song_mask |= int(song_cluster_mask)

    obj_score, _ = object_grounding_score(clip_meta, song_mood_tags, song_terms)

    # Wenn überhaupt kein Signal vorhanden ist
    if tag_score is None and gender_score is None and mood_score is None and clip_cluster_mask == 0:
        return None

    # Vektor-Ähnlichkeit (-1..1 für die C++ Formel)
    vec_sim_raw = (tag_score * 2.0 - 1.0) if tag_score is not None else -2.0
    mood_val = mood_score if mood_score is not None else -1.0
    gender_val = gender_score if gender_score is not None else -1.0
    obj_val = obj_score if obj_score > 0.0 else -1.0

    # C++ Acceleration Bridge Call
    try:
        import cxx_accel
        cxx = cxx_accel.get_cxx_engine()
        score = cxx.compute_semantic_score(
            vector_similarity=vec_sim_raw,
            mood_score=mood_val,
            gender_score=gender_val,
            clip_cluster_mask=clip_cluster_mask,
            song_cluster_mask=computed_song_mask,
            object_grounding_score=obj_val
        )
        return round(float(score), 4)
    except Exception:
        pass

    # Python Fallback
    weighted: List[Tuple[float, float]] = []
    if tag_score is not None:
        weighted.append((tag_score, 0.40))
    if mood_score is not None:
        weighted.append((mood_score, 0.25))
    if gender_score is not None:
        weighted.append((gender_score, 0.20))
    if clip_cluster_mask & computed_song_mask:
        bits = bin(clip_cluster_mask & computed_song_mask).count("1")
        cluster_score = min(1.0, 0.5 + 0.2 * bits)
        weighted.append((cluster_score, 0.15))
    if obj_score > 0.0:
        weighted.append((obj_score, 0.10))

    if not weighted:
        return 0.5

    total_weight = sum(w for _, w in weighted)
    return round(sum(score * w for score, w in weighted) / total_weight, 4)


def semantic_match_reason(clip_meta: Any, song_tag_vector,
                           song_mood_tags: list | None = None,
                           song_mc_gender: str | None = None,
                           song_style_weights: dict | None = None,
                           song_visual_objects: list | None = None,
                           song_cluster_mask: int | None = None) -> str:
    """Baut eine strukturierte, aussagekräftige und verständliche Begründung,
    WARUM ein Clip zu diesem Song-Segment semantisch ausgewählt wurde."""
    if not clip_meta or not isinstance(clip_meta, dict):
        return "kein Clip-Metadaten-Treffer im Cache (--rebuild-globe empfohlen)"

    clip_terms = extract_clip_terms(clip_meta)
    reasons: List[str] = []

    song_terms = set(kw for kw, v in zip(TAG_VOCAB, song_tag_vector) if v) if song_tag_vector else set()
    if song_mood_tags:
        song_terms.update(t.lower() for t in song_mood_tags if t)
    if song_visual_objects:
        for v in song_visual_objects:
            if v:
                v_str = str(v).lower()
                song_terms.add(v_str)
                cat_words = VISUAL_SCENE_VOCAB.get(v) or VISUAL_SCENE_VOCAB.get(v.upper()) or []
                for cw in cat_words:
                    song_terms.add(cw.lower())
        song_terms.update(v.lower() for v in song_visual_objects if v)

    # 1. Konzept-Cluster-Affinität
    clip_mask = compute_cluster_mask(clip_terms)
    computed_song_mask = compute_cluster_mask(song_terms)
    if song_cluster_mask is not None and song_cluster_mask > 0:
        computed_song_mask |= int(song_cluster_mask)
    shared_mask = clip_mask & computed_song_mask
    if shared_mask:
        active_clusters = []
        for name, bit in CLUSTER_BITS.items():
            if shared_mask & bit:
                overlap_words = sorted((clip_terms & song_terms) & CONCEPT_CLUSTERS[name])
                label = CLUSTER_EMOJIS.get(name, name)
                if overlap_words:
                    active_clusters.append(f"{label} ({', '.join(overlap_words[:3])})")
                else:
                    active_clusters.append(label)
        if active_clusters:
            reasons.append(" | ".join(active_clusters[:2]))

    # 2. Visuelles Object-Grounding
    _, grounded_objects = object_grounding_score(clip_meta, song_mood_tags, song_terms)
    if grounded_objects:
        reasons.append(f"🔍 Obj: {', '.join(grounded_objects[:3])}")

    # 3. Direkter Lyrics / Tag Overlap
    clip_tags = set(t.lower() for t in (clip_meta.get("tags") or []))
    if song_mood_tags:
        mood_overlap = sorted(set(t.lower() for t in song_mood_tags) & clip_tags)
        if mood_overlap:
            reasons.append(f"Lyrics-Mood: {', '.join(mood_overlap[:4])}")

    # 4. MC-Gender Alignment
    if song_mc_gender in ("male", "female", "dual"):
        gender_vector = clip_meta.get("gender_vector") or {}
        clip_gender = clip_meta.get("gender")
        has_f = bool(gender_vector.get("female") or clip_gender == "female")
        has_m = bool(gender_vector.get("male") or clip_gender == "male")
        if song_mc_gender == "dual" and (has_f or has_m):
            reasons.append(f"🎤 MC: duet ({'female' if has_f else 'male'})")
        elif song_mc_gender == "female" and has_f:
            reasons.append("🎤 MC: female")
        elif song_mc_gender == "male" and has_m:
            reasons.append("🎤 MC: male")

    # 5. CLIP-Embedding / Vektor-Match Fallback
    if not reasons:
        vector_score = calculate_vector_match(clip_meta, song_tag_vector)
        if vector_score is not None and vector_score >= 0.5:
            reasons.append(f"🎯 CLIP-Vektor: {vector_score:.2f} (semantische Embedding-Nähe)")
        else:
            reasons.append("⚡ Rhythmus/Energie-Match (rein bewegungsbasiert)")

    return " ; ".join(reasons)
