import pytest
from semantic_matching import (
    calculate_semantic_match,
    semantic_match_reason,
    gender_alignment_score,
    mood_tag_overlap_score,
    extract_clip_terms,
    compute_cluster_mask,
    object_grounding_score,
    cosine_similarity,
    calculate_vector_match,
    CONCEPT_CLUSTERS,
    CLUSTER_BITS,
)


def test_extract_clip_terms():
    meta = {
        "tags": ["weed", "smoke", "420"],
        "objects": ["car", {"label": "person"}],
        "scenarios": ["night", "street"],
        "path": "j:/clips/drift_089_speed.mp4",
        "domain": "URBAN_STREET"
    }
    terms = extract_clip_terms(meta)
    assert "weed" in terms
    assert "smoke" in terms
    assert "car" in terms
    assert "person" in terms
    assert "street" in terms
    assert "drift" in terms
    assert "urban_street" in terms


def test_compute_cluster_mask():
    weed_terms = ["joint", "kush", "chilling"]
    mask = compute_cluster_mask(weed_terms)
    assert (mask & CLUSTER_BITS["weed_420"]) != 0
    assert (mask & CLUSTER_BITS["speed_motion"]) == 0

    speed_terms = ["drift", "bmw", "fast"]
    mask_speed = compute_cluster_mask(speed_terms)
    assert (mask_speed & CLUSTER_BITS["speed_motion"]) != 0


def test_gender_alignment():
    # Female MC against female clip
    meta_female = {"gender": "female", "gender_vector": {"female": 1.0, "male": 0.0}}
    assert gender_alignment_score(meta_female, "female") == 1.0
    assert gender_alignment_score(meta_female, "male") == 0.0

    # Dual MC against group/duet clip
    meta_duet = {"gender": "dual", "person_count": 2, "gender_vector": {"female": 1.0, "male": 1.0}}
    assert gender_alignment_score(meta_duet, "dual") == 1.0

    # No person in clip (scenery)
    meta_scenery = {"tags": ["nature", "mountain"]}
    assert gender_alignment_score(meta_scenery, "male") is None


def test_object_grounding_score():
    meta = {
        "tags": ["urban"],
        "objects": ["train", "person"]
    }
    score, hits = object_grounding_score(meta, song_mood_tags=["train", "mvv", "graffiti"])
    assert score > 0.5
    assert "train" in hits


def test_calculate_semantic_match_with_clusters():
    meta = {
        "tags": ["weed", "kush"],
        "objects": ["smoke"],
        "gender": "male",
        "vector": [1.0, 0.0, 0.0, 0.0]
    }
    song_vec = [1.0, 0.0, 0.0, 0.0]
    song_moods = ["weed", "kush", "smoke"]
    
    score_full = calculate_semantic_match(
        clip_meta=meta,
        song_tag_vector=song_vec,
        song_mood_tags=song_moods,
        song_mc_gender="male"
    )
    assert score_full is not None
    assert score_full > 0.85

    # Partial synonym overlap (weed vs joint/420)
    score_partial = calculate_semantic_match(
        clip_meta=meta,
        song_tag_vector=song_vec,
        song_mood_tags=["weed", "joint", "420"],
        song_mc_gender="male"
    )
    assert score_partial is not None
    assert score_partial > 0.70


def test_semantic_match_reason():
    meta = {
        "tags": ["weed", "joint"],
        "objects": ["person"],
        "gender": "male",
        "vector": [1.0, 0.0, 0.0, 0.0]
    }
    song_vec = [1.0, 0.0, 0.0, 0.0]
    song_moods = ["weed", "joint"]
    
    reason = semantic_match_reason(
        clip_meta=meta,
        song_tag_vector=song_vec,
        song_mood_tags=song_moods,
        song_mc_gender="male"
    )
    assert "Weed/420" in reason
    assert "MC: male" in reason
