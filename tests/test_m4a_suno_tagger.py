import pytest
from pathlib import Path
from mutagen.mp4 import MP4, MP4Cover

from m4a_suno_tagger import (
    parse_suno_txt,
    scan_suno_downloads_folder,
    build_suno_index,
    find_suno_metadata,
    check_la_bat_trigger,
    apply_tags_to_m4a,
    is_song_untagged,
    SunoMetadata,
)


def test_parse_suno_txt(tmp_path: Path):
    txt_file = tmp_path / "aqas-Ruthless_Love_v3.5-48130fa8.m4a.txt"
    txt_file.write_text(r"""Metadata for: aqas-Ruthless_Love_v3.5-48130fa8.m4a
Title: Ruthless Love
Artist: Oidasheim Crew
Track ID: 48130fa8-1111-2222-3333-444444444444

--- Lyrics ---
[Verse]
Oida, wir brennen die Straßen down.

--- Raw API Response ---
{"title": "Ruthless Love", "display_name": "Oidasheim Crew", "metadata": {"gpt_description_prompt": "Bavarian Trap Phonk", "tags": "trap, phonk, bavaria", "duration": 130.5}}
""", encoding="utf-8")

    meta = parse_suno_txt(txt_file)
    assert meta is not None
    assert meta.title == "Ruthless Love"
    assert meta.artist == "Oidasheim Crew"
    assert meta.track_id == "48130fa8-1111-2222-3333-444444444444"
    assert "Oida" in meta.lyrics
    assert meta.prompt_description == "Bavarian Trap Phonk"
    assert meta.tags_string == "trap, phonk, bavaria"


def test_la_bat_trigger_detection():
    # 1. la.bat in filename
    p1 = Path("j:/Oidasheim/Musik/m4a/la.bat_track_01.m4a")
    assert check_la_bat_trigger(p1, None, None) is True

    # 2. la.bat in Suno title
    p2 = Path("j:/Oidasheim/Musik/m4a/track_02.m4a")
    meta2 = SunoMetadata(source_txt="foo.txt", title="la.bat Oida Anthem")
    assert check_la_bat_trigger(p2, meta2, None) is True

    # 3. la.bat in Suno lyrics
    meta3 = SunoMetadata(source_txt="foo.txt", title="Anthem", lyrics="Wir starten mit la.bat in den Tag")
    assert check_la_bat_trigger(p2, meta3, None) is True

    # 4. Standard track without la.bat
    meta4 = SunoMetadata(source_txt="foo.txt", title="Normal Track", lyrics="Reine Musik ohne Marker")
    assert check_la_bat_trigger(p2, meta4, None) is False


def test_apply_tags_with_la_bat_prefix_and_album(tmp_path: Path):
    m4a_file = tmp_path / "sample_la_bat_track.m4a"
    
    meta = SunoMetadata(
        source_txt=str(tmp_path / "sample.txt"),
        title="Bavarian Beats",
        artist="DJ Oida",
        lyrics="[Verse]\nLa.bat ballert durch die Boxen.",
        prompt_description="Phonk 089",
        tags_string="phonk, bass",
        track_id="12345678-aaaa-bbbb-cccc-dddddddddddd",
        cover_path=str(tmp_path / "cover.jfif"),
    )

    is_la = check_la_bat_trigger(m4a_file, meta, None)
    assert is_la is True

    clean_title = meta.title.strip()
    if is_la and not clean_title.lower().startswith("la.bat"):
        clean_title = f"la.bat - {clean_title}"
    album = "la.bat" if is_la else "Suno AI"

    assert clean_title == "la.bat - Bavarian Beats"
    assert album == "la.bat"


def test_multi_source_suno_indexing(tmp_path: Path):
    txt_dir = tmp_path / "suno txt"
    txt_dir.mkdir()
    txt_file = txt_dir / "track-87654321.m4a.txt"
    txt_file.write_text("""Title: Multi Source Track
Artist: MCP Oida
Track ID: 87654321-0000-0000-0000-000000000000
--- Lyrics ---
[Chorus]
Cross Source Tagging!
""", encoding="utf-8")

    dl_dir = tmp_path / "Suno Downloads"
    dl_dir.mkdir()
    sub = dl_dir / "Multi Source Track"
    sub.mkdir()
    cover_file = sub / "cover.jfif"
    cover_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb")

    index = build_suno_index([txt_dir, dl_dir], log=lambda _: None)
    assert "87654321" in index["by_short_id"]
    meta = index["by_short_id"]["87654321"]
    assert meta.title == "Multi Source Track"
    assert "Cross Source" in meta.lyrics
