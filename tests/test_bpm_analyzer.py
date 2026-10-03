"""
tests/test_bpm_analyzer.py — Unit-Tests für das MixMeister BPM Analyzer Modul

Testet:
  1. _parse_bpm_output() — alle bekannten Ausgabeformate
  2. detect_bpm() mit nicht-existierender Datei → 0.0
  3. detect_bpm() mit nicht-existierendem Binary → 0.0
  4. detect_bpm_batch() — leere Liste, gemischte Ergebnisse
  5. is_available() — prüft ob Binary vorhanden
  6. BPM-Plausibilitäts-Check (20–400 BPM Range)
"""
import pytest
from unittest.mock import patch, MagicMock
import subprocess

import bpm_analyzer
from bpm_analyzer import _parse_bpm_output, detect_bpm, detect_bpm_batch, is_available


# ── _parse_bpm_output ─────────────────────────────────────────────────────────

class TestParseBpmOutput:
    def test_empty_string(self):
        assert _parse_bpm_output("") == 0.0

    def test_none_equivalent(self):
        assert _parse_bpm_output("   \n\n  ") == 0.0

    def test_bpm_colon_format(self):
        assert _parse_bpm_output("BPM: 140.00") == pytest.approx(140.0, abs=0.01)

    def test_bpm_colon_lowercase(self):
        assert _parse_bpm_output("bpm: 128.5") == pytest.approx(128.5, abs=0.01)

    def test_tempo_colon_format(self):
        assert _parse_bpm_output("Tempo: 174.0") == pytest.approx(174.0, abs=0.01)

    def test_raw_number_only(self):
        assert _parse_bpm_output("140.00") == pytest.approx(140.0, abs=0.01)

    def test_number_followed_by_bpm(self):
        assert _parse_bpm_output("132.00 BPM") == pytest.approx(132.0, abs=0.01)

    def test_integer_bpm(self):
        assert _parse_bpm_output("BPM: 96") == pytest.approx(96.0, abs=0.01)

    def test_bpm_in_multiline_output(self):
        txt = "MixMeister BPM Analyzer v1.0\nAnalyzing file...\nBPM: 140.00\nDone."
        assert _parse_bpm_output(txt) == pytest.approx(140.0, abs=0.01)

    def test_out_of_range_low_rejected(self):
        # 15 BPM ist nicht plausibel
        assert _parse_bpm_output("BPM: 15.0") == 0.0

    def test_out_of_range_high_rejected(self):
        # 500 BPM ist nicht plausibel
        assert _parse_bpm_output("BPM: 500.0") == 0.0

    def test_noise_output_returns_zero(self):
        assert _parse_bpm_output("Error: File not found\nInvalid format") == 0.0

    def test_140bpm_typical_mixmeister_output(self):
        """Simulierter typischer MixMeister-Output für 140 BPM Track."""
        output = "C:\\track.mp3\r\n140.00\r\n"
        assert _parse_bpm_output(output) == pytest.approx(140.0, abs=0.01)

    def test_decimal_precision_preserved(self):
        assert _parse_bpm_output("BPM: 137.82") == pytest.approx(137.82, abs=0.01)


# ── detect_bpm ───────────────────────────────────────────────────────────────

class TestDetectBpm:
    def test_nonexistent_file_returns_zero(self):
        result = detect_bpm("/nonexistent/track.mp3")
        assert result == 0.0

    def test_nonexistent_binary_returns_zero(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        with patch.object(bpm_analyzer, "_ANALYZER_PATH") as mock_path:
            mock_path.is_file.return_value = False
            result = detect_bpm(str(wav))
        assert result == 0.0

    def test_timeout_returns_zero(self, tmp_path):
        """Timeout → 0.0, kein Crash."""
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        with patch("bpm_analyzer._ANALYZER_PATH") as mock_analyzer:
            mock_analyzer.is_file.return_value = True
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="bpm", timeout=1)):
                result = detect_bpm(str(wav), timeout=0.001)
        assert result == 0.0

    def test_successful_bpm_detection_mocked(self, tmp_path):
        """Vollständiger Pfad: subprocess gibt '140.00' zurück → 140.0."""
        wav = tmp_path / "track.mp3"
        wav.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.stdout = "BPM: 140.00\n"
        mock_result.stderr = ""

        with patch("bpm_analyzer._ANALYZER_PATH") as mock_path, \
             patch("subprocess.run", return_value=mock_result):
            mock_path.is_file.return_value = True
            # Datei muss auch wirklich existieren
            result = detect_bpm(str(wav), timeout=5.0)
        assert result == pytest.approx(140.0, abs=0.01)

    def test_subprocess_exception_returns_zero(self, tmp_path):
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"\x00" * 100)
        with patch("bpm_analyzer._ANALYZER_PATH") as mock_path, \
             patch("subprocess.run", side_effect=OSError("Permission denied")):
            mock_path.is_file.return_value = True
            result = detect_bpm(str(wav))
        assert result == 0.0


# ── detect_bpm_batch ──────────────────────────────────────────────────────────

class TestDetectBpmBatch:
    def test_empty_list(self):
        assert detect_bpm_batch([]) == {}

    def test_all_nonexistent_files(self):
        paths = ["/fake/a.mp3", "/fake/b.mp3"]
        result = detect_bpm_batch(paths)
        assert set(result.keys()) == {str(p) for p in paths}
        assert all(v == 0.0 for v in result.values())

    def test_returns_dict_with_all_paths(self, tmp_path):
        f1 = tmp_path / "a.mp3"
        f2 = tmp_path / "b.mp3"
        f1.write_bytes(b"\x00")
        f2.write_bytes(b"\x00")

        with patch("bpm_analyzer.detect_bpm", return_value=128.0):
            result = detect_bpm_batch([str(f1), str(f2)])

        assert str(f1) in result
        assert str(f2) in result
        assert result[str(f1)] == pytest.approx(128.0, abs=0.01)

    def test_mixed_results(self, tmp_path):
        f1 = tmp_path / "good.mp3"
        f2 = tmp_path / "bad.mp3"
        f1.write_bytes(b"\x00")
        f2.write_bytes(b"\x00")

        def mock_detect(path, timeout=None):
            return 140.0 if "good" in str(path) else 0.0

        with patch("bpm_analyzer.detect_bpm", side_effect=mock_detect):
            result = detect_bpm_batch([str(f1), str(f2)])

        assert result[str(f1)] == pytest.approx(140.0, abs=0.01)
        assert result[str(f2)] == 0.0


# ── is_available ──────────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_returns_bool(self):
        result = is_available()
        assert isinstance(result, bool)

    def test_true_when_binary_exists(self):
        with patch("bpm_analyzer._ANALYZER_PATH") as mock_path:
            mock_path.is_file.return_value = True
            assert is_available() is True

    def test_false_when_binary_missing(self):
        with patch("bpm_analyzer._ANALYZER_PATH") as mock_path:
            mock_path.is_file.return_value = False
            assert is_available() is False
