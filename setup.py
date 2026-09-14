#!/usr/bin/env python3
"""
setup.py — OIDASHEIM BEAT SYNC VIDEO EDITOR
Modern Python packaging configuration
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, encoding="utf-8") as f:
        requirements = [
            line.strip() for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]

setup(
    name="oidasheim-beatsync",
    version="1.0.0",
    description="ART DIRECTOR BEAT SYNC VIDEO EDITOR — 1-Click: MP3 + Clips -> Epic Music Videos",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Oidasheim",
    author_email="dev@oidasheim.de",
    url="https://github.com/oidasheim/beatsync",
    license="MIT",
    
    python_requires=">=3.10",
    packages=find_packages(include=["oidasheim*"]),
    include_package_data=True,
    
    install_requires=requirements,
    
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "gpu": [
            "torch[cuda118]>=2.0.0",  # CUDA 11.8 support
        ],
    },
    
    entry_points={
        "console_scripts": [
            "beatsync=main:main",
            "beatsync-builder=analysis.songrid_builder:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Sound/Audio",
    ],
    
    keywords=[
        "video", "music", "beat-sync", "clip-pool", "ffmpeg", 
        "ai", "editing", "automation", "semantic", "rhythm"
    ],
)
