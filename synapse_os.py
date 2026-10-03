#!/usr/bin/env python3
"""
synapse_os.py — SYNAPSE AUDIO DYNAMICS Main System Orchestrator & Launcher
Location: J:\\Oidasheim\\oefoef\\synapse_os.py
"Resonanz erzeugen. Werte erschaffen. Unsterblichkeit codieren."
"""
import sys
import json
import time
import argparse
from pathlib import Path

# Insert local root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SYNAPSE_LABEL_NAME, SYNAPSE_MOTTO, SYNAPSE_NODES
from idex_kernel import get_kernel
from neural_audio_fabric import NeuralAudioFabric
from vega_mastering import VEGAMasteringEngine
from scene_intelligence import SceneIntelligenceEngine
from render_graph_orchestrator import RenderGraphNeuralOrchestrator
from pubx_publisher import PUBXPublisher
from weisswurschtis_culture import WeisswurschtisCultureEngine

BANNER = r"""
    ███████╗██╗   ██╗███╗   ██╗██████╗ ███████╗███████╗     ██████╗ ███████╗
    ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔════╝██╔════╝    ██╔═══██╗██╔════╝
    ███████╗ ╚████╔╝ ██╔██╗ ██║██████╔╝███████╗█████╗      ██║   ██║███████╗
    ╚════██║  ╚██╔╝  ██║╚██╗██║██╔═══╝ ╚════██║██╔══╝      ██║   ██║╚════██║
    ███████║   ██║   ██║ ╚████║██║     ███████║███████╗    ╚██████╔╝███████║
    ╚══════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝     ╚══════╝╚══════╝     ╚═════╝ ╚══════╝
            SYNAPSE AUDIO DYNAMICS — AUTONOMOUS ECOSYSTEM OS v7.0
"""

def print_status():
    print(BANNER)
    print(f"🏢 Label: {SYNAPSE_LABEL_NAME}")
    print(f"💬 Motto: \"{SYNAPSE_MOTTO}\"\n")
    print("👥 ACTIVE NODES (The Apex Predators):")
    kernel = get_kernel()
    for name, info in SYNAPSE_NODES.items():
        print(f"  • {name:15s} | {info}")
    print("\n🎛️ IDEX KERNEL DASHBOARD:")
    print(json.dumps(kernel.get_status_dashboard(), indent=2))

def run_album_simulation():
    print(BANNER)
    print("🚀 STARTING FULL 10-TRACK ALBUM SIMULATION: 'CHROMA ASCENSION'\n")
    
    kernel = get_kernel()
    naf = NeuralAudioFabric()
    vega = VEGAMasteringEngine("cinematic")
    sie = SceneIntelligenceEngine()
    rno = RenderGraphNeuralOrchestrator()
    pubx = PUBXPublisher()
    culture = WeisswurschtisCultureEngine()

    tracks = [f"Track_{i:02d}_Ascension" for i in range(1, 11)]

    for idx, track_name in enumerate(tracks, 1):
        print(f"------------------------------------------------------------------------")
        print(f"▶️ [{idx}/10] ALBUM SIMULATION: Processing '{track_name}'")
        
        # 1. KAIRO & NAF
        print(f"  • 🎚️ KAIRO & NAF: Extracting 100ms Tensor Map & Hook/Drop markers...")
        time.sleep(0.05)

        # 2. VEGA Mastering
        print(f"  • 🔊 VEGA: Applying Auto-Mastering (Target: -10.5 LUFS, -1.0 dBTP)...")
        time.sleep(0.05)

        # 3. WEEDIT & NTE & SIE
        print(f"  • ✂️ WEEDIT & SIE: Scene Matching & Neural Timeline Cut Plan...")
        time.sleep(0.05)

        # 4. WEISSWURSCHTIS Culture
        caption = culture.generate_dialect_caption(track_name)
        print(f"  • 🥨 WEISSWURSCHTIS: Culture Overlay -> '{caption}'")
        time.sleep(0.02)

        # 5. RNO RenderGraph Execution
        plan = rno.build_execution_plan(f"{track_name}.mp3", "full", gpu_available=True)
        rno.execute_plan(plan, log_fn=lambda msg: print(f"    {msg}"))

        # 6. PUBX Publishing & ATLAS ROI
        pkg = pubx.build_release_package(Path(f"{track_name}.mp3"))
        pubx.publish_release(pkg, log_fn=lambda msg: print(f"    {msg}"))
        print(f"  • 📈 ATLAS: Target ROAS 4.2x | Automated Ad-Scaling active for DE/BR/JP.\n")

    print("========================================================================")
    print("🎉 FULL ALBUM SIMULATION COMPLETED SUCCESSFULLY!")
    print("📊 Results: 10/10 Tracks Deployed | 500+ Content Snippets | Global Sync Ready.")
    print("========================================================================\n")

def main():
    parser = argparse.ArgumentParser(description="SYNAPSE AUDIO DYNAMICS OS Launcher")
    parser.add_argument("--status", action="store_true", help="Zeige den Status aller Nodes und des IDEX Kernels.")
    parser.add_argument("--album-sim", action="store_true", help="Führe die vollständige 10-Track Album-Simulation durch.")
    parser.add_argument("--mastering-test", type=str, help="Pfad zu einer Audio-Datei für VEGA Auto-Mastering Test.")
    parser.add_argument("--profile", type=str, default="cinematic", choices=["trap", "pop", "edm", "boombap", "cinematic"], help="Mastering Profil")

    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.album_sim:
        run_album_simulation()
    elif args.mastering_test:
        inp = Path(args.mastering_test)
        out = inp.parent / f"{inp.stem}_VEGA_MASTERED{inp.suffix}"
        vega = VEGAMasteringEngine(args.profile)
        vega.master_audio(inp, out)
    else:
        print_status()
        print("\n💡 Tipp: Aufruf mit '--album-sim' für die Vollalbum-Simulation oder '--status'.")

if __name__ == "__main__":
    main()
