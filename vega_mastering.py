#!/usr/bin/env python3
"""
vega_mastering.py — VEGA Neural Mastering Engine & MasterNode DSP for SYNAPSE AUDIO DYNAMICS
Location: J:\\Oidasheim\\oefoef\\vega_mastering.py
Auto-Mastering pipeline for Suno & AI audio exports.
Applies spectral cleanup, multiband compression, harmonic saturation, Mid/Side stereo widening, and LUFS/True Peak limiting.
"""
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

from config import FFMPEG_BIN, SYNAPSE_VEGA_MASTERING_PROFILES

class VEGAMasteringEngine:
    def __init__(self, profile_name: str = "cinematic"):
        self.profile_name = profile_name.lower()
        self.profile = SYNAPSE_VEGA_MASTERING_PROFILES.get(
            self.profile_name, SYNAPSE_VEGA_MASTERING_PROFILES["cinematic"]
        )

    def master_audio(self, input_audio: Path, output_audio: Path) -> bool:
        """
        Executes zero-latency VEGA Mastering DSP chain via FFmpeg filtergraph:
        1. Highpass (30 Hz)
        2. Low-Mid Cut (250 Hz, -1.5 dB)
        3. Harshness Control Notch (6.5 kHz, -1 dB)
        4. Optional High-Shelf Air Boost (12 kHz)
        5. Multiband Glue Compressor & Saturation (asoftclip / acompressor)
        6. Stereo Widener (extrastereo / M-S processing)
        7. True Peak Limiter (-1.0 dBTP) & Loudness Normalization (loudnorm)
        """
        if not input_audio.exists():
            print(f"❌ Input audio '{input_audio}' not found for VEGA mastering.")
            return False

        output_audio.parent.mkdir(parents=True, exist_ok=True)
        target_lufs = self.profile["target_lufs"]
        tp = self.profile["true_peak_db"]

        # Build FFmpeg audio filtergraph chain
        filter_chain = []
        filter_chain.append("highpass=f=30")
        if self.profile.get("low_mid_dip"):
            filter_chain.append("equalizer=f=250:width_type=h:width=100:g=-1.5")
        filter_chain.append("equalizer=f=6500:width_type=h:width=500:g=-1.0")
        if self.profile.get("air_boost"):
            filter_chain.append("highshelf=f=12000:g=0.8")

        # Multiband glue & saturation
        filter_chain.append("acompressor=level_in=1:threshold=-14dB:ratio=2:attack=30:release=120:makeup=1.5")
        filter_chain.append("asoftclip=type=sine:param=0.8")

        # M/S stereo enhancement
        filter_chain.append("extrastereo=m=1.15:c=0")

        # Final LUFS and True Peak limiting
        filter_chain.append(f"loudnorm=I={target_lufs}:TP={tp}:LRA=7")

        af_arg = ",".join(filter_chain)

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(input_audio),
            "-af", af_arg,
            "-c:a", "libmp3lame" if output_audio.suffix.lower() == ".mp3" else "pcm_s16le",
            "-b:a", "320k",
            str(output_audio)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if res.returncode == 0 and output_audio.exists():
                print(f"🎚️ [VEGA Mastering] Mastered successfully: {output_audio.name} ({target_lufs} LUFS, {tp} dBTP)")
                return True
            else:
                print(f"⚠️ [VEGA Mastering] FFmpeg warn/fallback: {res.stderr[:200]}")
                return False
        except Exception as e:
            print(f"❌ [VEGA Mastering] Exception during DSP execution: {e}")
            return False

if __name__ == "__main__":
    engine = VEGAMasteringEngine("trap")
    print("🔊 VEGA Neural Mastering Engine Ready.")
