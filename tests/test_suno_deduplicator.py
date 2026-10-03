import pytest
from pathlib import Path

from suno_deduplicator import (
    compute_fast_hash,
    compute_full_md5,
    select_keeper,
    find_duplicates,
    move_duplicates_to_destination,
)


def test_select_keeper(tmp_path: Path):
    f_clean = tmp_path / "Oida_Track.mp3"
    f_dup1 = tmp_path / "Oida_Track (1).mp3"
    f_dup2 = tmp_path / "Oida_Track (2).mp3"

    f_clean.write_bytes(b"sample audio data 12345678")
    f_dup1.write_bytes(b"sample audio data 12345678")
    f_dup2.write_bytes(b"sample audio data 12345678")

    keeper = select_keeper([f_dup2, f_clean, f_dup1])
    assert keeper == f_clean


def test_find_and_move_duplicates(tmp_path: Path):
    suno_dir = tmp_path / "Suno Downloads"
    suno_dir.mkdir()

    sub1 = suno_dir / "Sub1"
    sub1.mkdir()

    orig_mp3 = sub1 / "Song.mp3"
    dupe_mp3 = sub1 / "Song (1).mp3"
    orig_img = sub1 / "Cover.jfif"
    dupe_img = sub1 / "Cover (1).jfif"

    audio_bytes = b"MPEG_AUDIO_TEST_PAYLOAD" * 100
    img_bytes = b"JFIF_IMAGE_TEST_PAYLOAD" * 50

    orig_mp3.write_bytes(audio_bytes)
    dupe_mp3.write_bytes(audio_bytes)
    orig_img.write_bytes(img_bytes)
    dupe_img.write_bytes(img_bytes)

    dupes, stats = find_duplicates([suno_dir], workers=4, log=lambda _: None)
    assert len(dupes) == 2
    dupe_paths = [d[0] for d in dupes]
    assert dupe_mp3 in dupe_paths
    assert dupe_img in dupe_paths

    dest_dir = tmp_path / "doppelt"
    move_stats = move_duplicates_to_destination(
        dupes_to_move=dupes,
        dest_root=dest_dir,
        source_root=tmp_path,
        log=lambda _: None,
    )

    assert move_stats["moved"] == 2
    assert not dupe_mp3.exists()
    assert not dupe_img.exists()
    assert orig_mp3.exists()
    assert orig_img.exists()
    assert (dest_dir / "Suno Downloads" / "Sub1" / "Song (1).mp3").exists()
    assert (dest_dir / "Suno Downloads" / "Sub1" / "Cover (1).jfif").exists()
