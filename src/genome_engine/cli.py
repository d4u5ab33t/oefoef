"""
cli.py — Main CLI interface for Native Genome Engine v1.0.0.
"""
import argparse
import sys
import os
import json
from pathlib import Path
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
from genome_engine.compiler.timeline import EditDecisionList
from genome_engine.learning.synapse_loop import AestheticGenomeLearner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genome-engine",
        description=f"Native Visual & Rhythm Genome Music Video Engine v{__version__}"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: hardware-check
    hw_parser = subparsers.add_parser("hardware-check", help="Detect system CPU, RAM, and hardware encode capabilities")
    hw_parser.set_defaults(func=cmd_hardware_check)

    # Subcommand: scan
    scan_parser = subparsers.add_parser("scan", help="Scan track audio and generate rhythm genome")
    scan_parser.add_argument("--song", "-s", required=True, help="Path to audio file (MP3/WAV)")
    scan_parser.add_argument("--output", "-o", default="", help="Optional output JSON path for RhythmGenome")
    scan_parser.set_defaults(func=cmd_scan)

    # Subcommand: compile
    compile_parser = subparsers.add_parser("compile", help="Compile music video timeline EDL")
    compile_parser.add_argument("--song", "-s", required=True, help="Path to audio file")
    compile_parser.add_argument("--style", default="alpine_drill_comedy", help="Visual director style preset")
    compile_parser.add_argument("--clip-dir", "-c", default="", help="Directory containing media clips to index")
    compile_parser.add_argument("--output", "-o", default="output/timeline_edl.json", help="Path for output EDL JSON")
    compile_parser.add_argument("--otio", default="", help="Optional path to export OpenTimelineIO file")
    compile_parser.add_argument("--dry-run", action="store_true", help="Generate EDL without executing video render")
    compile_parser.add_argument("--render", action="store_true", help="Execute FFmpeg rendering after compilation")
    compile_parser.add_argument("--render-out", default="output/final_video.mp4", help="Output MP4 file path")
    compile_parser.set_defaults(func=cmd_compile)

    # Subcommand: render
    render_parser = subparsers.add_parser("render", help="Render compiled timeline EDL to MP4 video")
    render_parser.add_argument("--edl", required=True, help="Path to compiled EDL timeline JSON")
    render_parser.add_argument("--output", "-o", default="output/final_video.mp4", help="Output MP4 path")
    render_parser.add_argument("--cpu", action="store_true", help="Force CPU libx264 encoding instead of GPU NVENC")
    render_parser.add_argument("--dry-run", action="store_true", help="Generate concat script without encoding")
    render_parser.set_defaults(func=cmd_render)

    # Subcommand: export-otio
    otio_parser = subparsers.add_parser("export-otio", help="Export an EDL JSON to OpenTimelineIO format")
    otio_parser.add_argument("--edl", required=True, help="Path to compiled EDL timeline JSON")
    otio_parser.add_argument("--output", "-o", required=True, help="Path to write .otio JSON file")
    otio_parser.set_defaults(func=cmd_export_otio)

    # Subcommand: learn
    learn_parser = subparsers.add_parser("learn", help="Analyze reference video and auto-adapt VisualGenome")
    learn_parser.add_argument("--reference", "-r", required=True, help="Path to reference video file")
    learn_parser.add_argument("--style", default="alpine_drill_comedy", help="Base style to adapt")
    learn_parser.add_argument("--output", "-o", default="", help="Optional output JSON for adapted VisualGenome")
    learn_parser.set_defaults(func=cmd_learn)

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
    print(f"✅ Scan Complete. Detected BPM: {rhythm.bpm}, Duration: {rhythm.duration_sec}s, Sections: {len(rhythm.sections)}, Drops: {len(rhythm.drop_timestamps)}")
    
    if args.output:
        visual = VisualGenome()
        genome = GenomeData(audio_path=args.song, rhythm=rhythm, visual=visual)
        genome.save_json(args.output)
        print(f"📁 GenomeData saved to: {args.output}")

    return 0


def cmd_compile(args):
    print(f"Compiling track '{args.song}' with style '{args.style}'...")
    
    # 1. Scan Audio -> Rhythm Genome
    scanner = AudioScanner()
    rhythm = scanner.scan_file(args.song)
    
    # 2. Build Visual Genome & GenomeData
    visual = VisualGenome(style_name=args.style)
    genome = GenomeData(audio_path=args.song, rhythm=rhythm, visual=visual)

    # 3. Compile Song Timeline
    compiler = SongCompiler()
    edl = compiler.compile(genome)

    # 4. Apply Director Council Enhancements
    council = DirectorCouncil(args.style)
    enhanced_edl = council.review_and_enhance(edl)

    # 5. Resolve Media Clips
    index = SemanticIndex()
    if args.clip_dir and os.path.exists(args.clip_dir):
        count = index.scan_directory(args.clip_dir)
        print(f"Indexed {count} media clips from {args.clip_dir}")
    else:
        # Default mock / sample clips
        index.add_asset(MediaAsset("sample_clip_mountains.mp4", tags=["snow", "zugspitze", "landscape"]))
        index.add_asset(MediaAsset("sample_clip_drill.mp4", tags=["lederhosen", "gold_chains", "moshpit"]))
        index.add_asset(MediaAsset("sample_clip_bass.mp4", tags=["drop_energy", "high_energy"]))

    resolver = ClipResolver(index)
    resolved_edl = resolver.resolve_edl(enhanced_edl)

    # 6. Save EDL JSON
    resolved_edl.save_json(args.output)
    print(f"✅ Compiled {len(resolved_edl.segments)} segments. EDL saved to: {args.output}")

    # Optional OTIO export
    if args.otio:
        otio_content = OTIOExporter.export_otio(resolved_edl)
        os.makedirs(os.path.dirname(os.path.abspath(args.otio)) or ".", exist_ok=True)
        with open(args.otio, "w", encoding="utf-8") as f:
            f.write(otio_content)
        print(f"🎬 OpenTimelineIO exported to: {args.otio}")

    # Optional Render
    if args.render:
        engine = FFmpegRenderEngine(use_nvenc=True)
        engine.render(resolved_edl, args.render_out, dry_run=args.dry_run)

    return 0


def cmd_render(args):
    print(f"Loading timeline EDL from '{args.edl}'...")
    if not os.path.exists(args.edl):
        print(f"[ERROR] EDL file not found: {args.edl}")
        return 1

    edl = EditDecisionList.load_json(args.edl)
    engine = FFmpegRenderEngine(use_nvenc=not args.cpu)
    success = engine.render(edl, args.output, dry_run=args.dry_run)
    return 0 if success else 1


def cmd_export_otio(args):
    if not os.path.exists(args.edl):
        print(f"[ERROR] EDL file not found: {args.edl}")
        return 1
    edl = EditDecisionList.load_json(args.edl)
    otio_str = OTIOExporter.export_otio(edl)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(otio_str)
    print(f"✅ OpenTimelineIO successfully exported to: {args.output}")
    return 0


def cmd_learn(args):
    learner = AestheticGenomeLearner()
    profile = learner.analyze_reference(args.reference)
    base_visual = VisualGenome(style_name=args.style)
    adapted = learner.adapt_visual_genome(base_visual, profile)
    print("=" * 60)
    print("🧠 Synapse Neural Learning Results")
    print("=" * 60)
    print(f"Reference Video        : {args.reference}")
    print(f"Detected Cuts/Min      : {profile.detected_cuts_per_min}")
    print(f"Dominant Color Palette : {profile.dominant_colors}")
    print(f"Motion Intensity       : {profile.motion_intensity}")
    print(f"Adapted Cuts Target    : {adapted.target_cuts_per_min}")
    print("=" * 60)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(adapted.__dict__, f, indent=2)
        print(f"📁 Adapted VisualGenome saved to: {args.output}")

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
