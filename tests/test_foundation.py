"""
test_foundation.py — Tests for v0.1 Foundation & Installer components.
"""
import pytest
from genome_engine import __version__
from genome_engine.hardware import detect_hardware, recommend_encode_plan
from genome_engine.cli import build_parser, main


def test_package_version():
    assert __version__ == "0.1.0"


def test_hardware_detection():
    hw = detect_hardware()
    assert hw.logical_cores > 0
    assert hw.total_ram_gb > 0
    assert hw.available_ram_gb > 0
    assert hw.ram_source in ("psutil", "windows", "linux", "fallback")


def test_encode_plan():
    workers, threads = recommend_encode_plan(1920, 1080, "libx264", "medium")
    assert workers >= 1
    assert threads >= 1


def test_cli_parser():
    parser = build_parser()
    args = parser.parse_args(["hardware-check"])
    assert args.command == "hardware-check"


def test_cli_hardware_check_main():
    ret = main(["hardware-check"])
    assert ret == 0
