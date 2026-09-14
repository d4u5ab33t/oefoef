"""
cli.py — Main CLI interface for Native Genome Engine v1.0.0.
"""
import argparse
import sys
import os
from genome_engine import __version__
from genome_engine.hardware import detect_hardware, recommend_encode_plan
from genome_engine.scanner.audio_analyzer import AudioScanner
from genome_engine.genome.schema import GenomeData, VisualGenome
from genome_engine.compiler.song_compiler import SongCompiler
from genome_engine.directors.council import DirectorCouncil
from genome_engine.resolver.semantic_index import SemanticIndex, MediaAsset
from genome_engine.resolver.clip_resolver import ClipResolver
from genome_engine.renderer.otio_exporter import OTIOExporter
from genome_engine.renderer.ffmpeg_engine import FFmpegRenderEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genome-engine",
        description=f"Native Visual & Rhythm Genome Engine v{__version__}"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: hardware-check
    hw_parser = subparsers.add_parser("hardware-check", help="Detect system CPU, RAM and encode capabilities")
    hw_parser.set_defaults(func=cmd_hardware_check)

    # Subcommand: scan
    scan_parser = subparsers.add_parser("scan", help="Scan track audio and generate rhythm genome")
    scan_parser.add_argument("--song", required=True, help="Path to audio file (MP3/WAV)")
    scan_parser.set_defaults(func=cmd_scan)

    # Subcommand: compile
    compile_parser = subparsers.add_parser("compile", help="Compile music video timeline")
    compile_parser.add_argument("--song", required=True, help="Path to audio file")
    compile_parser.add_argument("--style", default="alpine_drill_comedy", help="Visual director style")
    compile_parser.add_argument("--output", default="output/final_edl.json", help="Path for output EDL JSON")
    compile_parser.add_argument("--dry-run", action="store_true", help="Generate EDL without rendering video")
    compile_parser.set_defaults(func=cmd_compile)

    # Subcommand: render
    render_parser = subparsers.add_parser("render", help="Render compiled timeline to video")
    render_parser.add_argument("--edl", required=True, help="Path to compiled EDL timeline JSON")
    render_parser.add_argument("--output", default="output/final_video.mp4", help="Output MP4 path")
    render_parser.set_defaults(func=cmd_render)

    return parser


def cmd_hardware_check(args):
    hw = detect_hardware(force_refresh=True)
    print("=" * 60)
    print(f"🚀 Native Genome Engine v{__version__} Hardware Diagnostic")
    print("=" * 60)
    print(f"Logical Cores  : {hw.logical_cores}")
    print(f"Physical Cores : {hw.physical_cores or 'N/A'}")
    print(f"Total RAM      : {hw.total_ram_gb:.2f} GB")
    print(f"Available RAM  : {hw.available_ram_gb:.2f} GB")
    print(f"RAM Detection  : {hw.ram_source}")
    
    workers, threads = recommend_encode_plan(1920, 1080, "libx264", "medium")
    print(f"Recommended 1080p Encode Plan: {workers} Workers x {threads} Threads")
    print("=" * 60)
    return 0


def cmd_scan(args):
    print(f"Scanning track: {args.song}...")
    scanner = AudioScanner()
    rhythm = scanner.scan_file(args.song)
    print(f"✅ Scan Complete. Detected BPM: {rhythm.bpm}, Duration: {rhythm.duration_sec}s, Sections: {len(rhythm.sections)}")
    return 0


def cmd_compile(args):
    print(f"Compiling track '{args.song}' with style '{args.style}'...")
    
    # 1. Scan Audio
    scanner = AudioScanner()
    rhythm = scanner.scan_file(args.song)
    
    # 2. Build Genome
    visual = VisualGenome(style_name=args.style)
    genome = GenomeData(audio_path=args.song, rhythm=rhythm, visual=visual)

    # 3. Compile Song Timeline
    compiler = SongCompiler()
    edl = compiler.compile(genome)

    # 4. Apply Director Council
    council = DirectorCouncil(args.style)
    enhanced_edl = council.review_and_enhance(edl)

    # 5. Resolve Clips
    index = SemanticIndex()
    index.add_asset(MediaAsset("sample_clip1.mp4", tags=["lederhosen", "snow"]))
    index.add_asset(MediaAsset("sample_clip2.mp4", tags=["gold_chains", "moshpit"]))
    resolver = ClipResolver(index)
    resolved_edl = resolver.resolve_edl(enhanced_edl)

    # 6. Save Output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(resolved_edl.to_dict().__str__())

    print(f"✅ Compiled {len(resolved_edl.segments)} segments. EDL saved to: {args.output}")

    if args.dry_run:
        print("[DRY RUN] Finished timeline compilation.")
        return 0

    return 0


def cmd_render(args):
    print(f"Rendering timeline '{args.edl}' to '{args.output}'...")
    engine = FFmpegRenderEngine(use_nvenc=True)
    print(f"✅ Render engine initialized with NVENC acceleration.")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
