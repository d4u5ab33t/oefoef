import pytest
from pathlib import Path
import tempfile
import json

from song_semantics import (
    analyze_lyrics,
    parse_suno_txt_file,
    build_filename_index,
    resolve_mp3_path,
    RawTrackEntry,
    _extract_visual_objects,
    _vocal_style,
)
from semantic_matching import (
    calculate_semantic_match,
    semantic_match_reason,
    compute_cluster_mask,
    CLUSTER_BITS,
)
from audio_analysis import AudioAnalysis
from timeline_builder import build_timeline, precompute_candidates


def test_analyze_lyrics_deep_features():
    lyrics_sample = """
[Verse 1: Male Rap]
Ich fahr im BMW durch Minga 089,
der Rauch steigt auf, Kush im Joint, wir drehn frei.
Oida, die Straßen brennen heiß im Neon-Licht,
kein Zweifel, echte Krieger weichen nicht.

[Chorus: Female Hook]
Gold an der Kette, Diamanten in der Nacht,
Millionen im Kopf, wir haben die Macht.
Komm mit mir in den Club, wenn der Laser strahlt,
alles bezahlt, die Zukunft gemalt.

[Bridge: SFX: Gunshot, Siren] [140 BPM] [BEAT SWITCH]
Komm in den Käfig, Fäuste fliegen schnell,
das Adrenalin pumpt hart und grell.
"""
    prompt_desc = "Energetic German Trap Boom-Bap with heavy 808s and Bavarian Rap"
    tags = "trap, phonk, aggressive, bavaria, 089"

    sem = analyze_lyrics(lyrics_sample, prompt_description=prompt_desc, tags_string=tags)

    assert sem["beat_switch_count"] >= 1
    assert "dual" in (sem["mc_gender"],) or sem["mc_gender"] in ("dual", "male", "female")
    assert sem["tension_score"] > 0.4
    assert sem["punchline_density"] > 0.0
    
    # Visual Objects
    assert "CAR_VEHICLE" in sem["visual_objects"]
    assert "WEED_SMOKE" in sem["visual_objects"]
    assert "CASH_LUXURY" in sem["visual_objects"]
    assert "CYBER_NEON" in sem["visual_objects"]
    assert "BAVARIAN_ROOTS" in sem["visual_objects"]

    # Cluster Mask
    mask = sem["cluster_mask"]
    assert (mask & CLUSTER_BITS["weed_420"]) != 0
    assert (mask & CLUSTER_BITS["speed_motion"]) != 0
    assert (mask & CLUSTER_BITS["luxury_wealth"]) != 0
    assert (mask & CLUSTER_BITS["bavarian_culture"]) != 0

    # Sections validation
    assert len(sem["sections"]) >= 3
    verse = sem["sections"][0]
    assert "CAR_VEHICLE" in verse["visual_cues"] or "WEED_SMOKE" in verse["visual_cues"]


def test_parse_suno_txt_file(tmp_path: Path):
    suno_content = r"""Metadata for: 48130fa8-sample-track.mp3
Title: Oida Drift King
Track ID: 48130fa8-1111-2222-3333-444444444444

--- Lyrics ---
[Verse]
Drift um die Kurve, Rauch aus den Reifen,
Oida wir lassen uns niemals ergreifen.

[Chorus]
Bass ballert laut, 089 in der Brust.

--- Raw API Response ---
{"metadata": {"prompt": "[Verse]\nDrift...", "gpt_description_prompt": "Bavarian Phonk Drift Rap", "tags": "phonk, drift, bavaria", "duration": 142.5}}
"""
    txt_file = tmp_path / "48130fa8-sample-track.txt"
    txt_file.write_text(suno_content, encoding="utf-8")

    entries = parse_suno_txt_file(txt_file)
    assert len(entries) == 1
    e = entries[0]
    assert e.title == "Oida Drift King"
    assert e.track_id == "48130fa8-1111-2222-3333-444444444444"
    assert e.prompt_description == "Bavarian Phonk Drift Rap"
    assert "Drift" in e.lyrics
    assert e.duration == 142.5


def test_build_filename_index_and_resolution(tmp_path: Path):
    # Setup dummy mp3 file
    mp3_file = tmp_path / "48130fa8-sample-track.mp3"
    mp3_file.write_bytes(b"\x00" * 100)

    index = build_filename_index(tmp_path)
    assert "48130fa8" in index["short_ids"]

    entry = RawTrackEntry(
        source_file="test.txt",
        title="Sample Track",
        artist="",
        bpm=130.0,
        musical_key="",
        comment="",
        lyrics="",
        dir_hint="",
        file_hint="48130fa8-sample-track.mp3",
        track_id="48130fa8-1111-2222-3333-444444444444",
    )

    resolved = resolve_mp3_path(entry, tmp_path / "test.txt", tmp_path, index)
    assert resolved == str(mp3_file)


def test_semantic_matching_with_lyrics_visuals():
    clip_meta = {
        "tags": ["bmw", "drift", "car"],
        "objects": ["car", "wheel"],
        "scenarios": ["street", "night"],
        "path": "j:/clips/bmw_drift_night.mp4",
        "domain": "SPEED_MOTION"
    }

    score = calculate_semantic_match(
        clip_meta=clip_meta,
        song_tag_vector=[0.0] * 128,
        song_mood_tags=["drift", "speed"],
        song_visual_objects=["CAR_VEHICLE", "NIGHT_CLUB"],
        song_cluster_mask=CLUSTER_BITS["speed_motion"] | CLUSTER_BITS["party_night"]
    )
    assert score is not None
    assert score > 0.65

    reason = semantic_match_reason(
        clip_meta=clip_meta,
        song_tag_vector=[0.0] * 128,
        song_mood_tags=["drift", "speed"],
        song_visual_objects=["CAR_VEHICLE", "NIGHT_CLUB"],
        song_cluster_mask=CLUSTER_BITS["speed_motion"] | CLUSTER_BITS["party_night"]
    )
    assert "Obj:" in reason or "Speed/Cars" in reason


def test_timeline_builder_with_lyrics_semantics():
    globe = {
        "clip1.mp4": {
            "duration": 5.0,
            "motion_score": 0.6,
            "motion_direction": 0.5,
            "face_score": 0.2,
            "tags": ["bmw", "car", "speed"],
            "playback_ok": True,
            "domain": "SPEED_MOTION",
        },
        "clip2.mp4": {
            "duration": 6.0,
            "motion_score": 0.3,
            "motion_direction": -0.2,
            "face_score": 0.1,
            "tags": ["chill", "nature", "cloud"],
            "playback_ok": True,
            "domain": "NATURE_CHILL",
        }
    }

    audio = AudioAnalysis(
        bpm=120.0,
        beat_times=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        downbeats=[0.0, 2.0, 4.0],
        duration_sec=4.0,
        energy=[0.6, 0.7, 0.8, 0.5],
        sections=[(0.0, 4.0, "high")],
        structure=[(0.0, 4.0, "verse")],
        mc_gender="male"
    )

    lyrics_sem = {
        "visual_objects": ["CAR_VEHICLE"],
        "cluster_mask": CLUSTER_BITS["speed_motion"],
        "sections": [{
            "order": 0,
            "label": "Verse",
            "visual_cues": ["CAR_VEHICLE"],
            "cluster_mask": CLUSTER_BITS["speed_motion"],
        }],
        "tension_score": 0.8,
        "punchline_density": 0.5,
    }

    pool, _ = precompute_candidates(
        globe, song_vector=[0.0] * 128, mc_gender="male",
        song_visual_objects=lyrics_sem["visual_objects"],
        song_cluster_mask=lyrics_sem["cluster_mask"],
    )
    clip1_cand = next(c for c in pool if c.path == "clip1.mp4")
    clip2_cand = next(c for c in pool if c.path == "clip2.mp4")
    assert clip1_cand.semantic_match > clip2_cand.semantic_match

    timeline = build_timeline(
        song_vector=[0.0] * 128,
        audio=audio,
        globe=globe,
        recent_used=[],
        song_semantics=lyrics_sem,
    )
    assert len(timeline) >= 1
    assert timeline[0].camera in ("dominance", "snap", "focus_zoom", "explosion", "push", "drift")


def test_multilingual_vocal_and_duet_recognition():
    # German / Bavarian
    assert _vocal_style("Rapperin am Mic mit Dirndl und Chaya") == "female"
    assert _vocal_style("Haberer Rapper Oida Kerl") == "male"
    assert _vocal_style("Er & Sie singen zusammen im Duett") == "dual"

    # Spanish / Latino
    assert _vocal_style("La chica canta como una reina mami") == "female"
    assert _vocal_style("El chico con su hermano y el rey del rap") == "male"
    assert _vocal_style("Chico y chica dueto latino") == "dual"

    # French
    assert _vocal_style("Une femme qui chante avec sa fille reine") == "female"
    assert _vocal_style("Un homme et son frère rappeur mec") == "male"
    assert _vocal_style("Homme et femme ensemble dialogue") == "dual"

    # Italian
    assert _vocal_style("Una donna ragazza signora bellissima") == "female"
    assert _vocal_style("Un uomo ragazzo signore fratello") == "male"
    assert _vocal_style("Uomo e donna duetto d'amore") == "dual"

    # Russian / Slavic
    assert _vocal_style("Девушка читает рэп как певица") == "female"
    assert _vocal_style("Парень на битах братан рэпер") == "male"
    assert _vocal_style("Парень и девушка дуэт трек") == "dual"


def test_line_level_gender_flip_flop():
    from song_semantics import parse_line_genders

    lyrics_dialogue = """
    M: Ich roll im 089er Mercedes durch die Nacht.
    F: Und ich hab die ganze Stadt mit Glanz aufgewacht.
    M: Gib mir den Beat, wir übernehmen das Spiel.
    F: Zu zweit am Steuer erreichen wir das Ziel.
    Both: Oidaheim für immer, alles real!
    """

    parsed_lines, is_flip_flop, gender_timeline = parse_line_genders(lyrics_dialogue)

    assert len(parsed_lines) == 5
    assert parsed_lines[0]["gender"] == "male"
    assert parsed_lines[1]["gender"] == "female"
    assert parsed_lines[2]["gender"] == "male"
    assert parsed_lines[3]["gender"] == "female"
    assert parsed_lines[4]["gender"] == "dual"

    # Flip-flop must be detected
    assert is_flip_flop is True
    assert len(gender_timeline) >= 4

    # Full analyze_lyrics integration
    sem = analyze_lyrics(lyrics_dialogue)
    assert sem["is_flip_flop"] is True
    assert sem["mc_gender"] == "dual"
    assert len(sem["line_genders"]) == 5


def test_dynamic_timeline_gender_and_flip_flop_cuts():
    globe = {
        "female_clip.mp4": {
            "duration": 5.0,
            "motion_score": 0.6,
            "face_score": 0.8,
            "gender_vector": {"female": ["frau", "chica"], "male": []},
            "playback_ok": True,
            "domain": "URBAN_STREET",
        },
        "male_clip.mp4": {
            "duration": 5.0,
            "motion_score": 0.6,
            "face_score": 0.8,
            "gender_vector": {"female": [], "male": ["mann", "bro"]},
            "playback_ok": True,
            "domain": "URBAN_STREET",
        },
        "duet_clip.mp4": {
            "duration": 5.0,
            "motion_score": 0.6,
            "face_score": 0.9,
            "gender_vector": {"female": ["frau"], "male": ["mann"]},
            "playback_ok": True,
            "domain": "URBAN_STREET",
        }
    }

    audio = AudioAnalysis(
        bpm=120.0,
        beat_times=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        downbeats=[0.0, 2.0, 4.0, 6.0, 8.0],
        duration_sec=8.0,
        energy=[0.6] * 8,
        sections=[(0.0, 8.0, "high")],
        structure=[(0.0, 8.0, "verse")],
        mc_gender="dual"
    )

    lyrics_sem = {
        "visual_objects": ["URBAN_STREET"],
        "cluster_mask": 0,
        "is_flip_flop": True,
        "gender_timeline": [
            {"start_frac": 0.0, "end_frac": 0.5, "gender": "male"},
            {"start_frac": 0.5, "end_frac": 1.0, "gender": "female"},
        ],
        "line_genders": [
            {"rel_start": 0.0, "rel_end": 0.5, "gender": "male", "text": "Male line"},
            {"rel_start": 0.5, "rel_end": 1.0, "gender": "female", "text": "Female line"},
        ],
        "tension_score": 0.7,
        "punchline_density": 0.4,
    }

    timeline = build_timeline(
        song_vector=[0.0] * 128,
        audio=audio,
        globe=globe,
        recent_used=[],
        song_semantics=lyrics_sem,
    )

    assert len(timeline) >= 2
    # First half should be male
    first_half_male = any(seg.mc_gender == "male" for seg in timeline if seg.start_sec < 4.0)
    assert first_half_male is True
    # Second half should be female
    second_half_female = any(seg.mc_gender == "female" for seg in timeline if seg.start_sec >= 4.0)
    assert second_half_female is True

