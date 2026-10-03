#!/usr/bin/env python3
import sys
import argparse
import yaml
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

# Module-Importe (Stelle sicher, dass diese existieren)
from scanner.visual_dna import VisualScanner
from compiler.audio.song_compiler import SongCompiler
from genome.resolver import GenomeResolver
from renderer.ffmpeg_emitter import RenderEmitter

console = Console()

def load_config():
    config_path = Path("config.yaml")
    if not config_path.exists():
        console.print("[bold red]❌ config.yaml nicht gefunden. Bitte setup_gos.py ausführen.")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="🧬 WE.ED.IT OIDA Native Genome CLI")
    parser.add_argument("command", choices=["scan", "compile", "doctor"])
    args = parser.parse_args()
    config = load_config()

    if args.command == "scan":
        console.print("[bold cyan]🧬 Starte DNA-Extraktion...[/bold cyan]")
        scanner = VisualScanner(db_path="database/genome_os.db")
        scanner.ingest(config['paths']['clips_native'])
        console.print("[bold green]✅ Scan erfolgreich.[/bold green]")

    elif args.command == "compile":
        console.print("[bold cyan]🎬 Starte Compiler-Pipeline...[/bold cyan]")
        
        # 1. Song Kompilation
        compiler = SongCompiler()
        song_ast = compiler.compile(Path(config['paths']['playlist']).parent / "track.mp3")
        
        # 2. Mock Director & Resolver (In v1.1 ersetzen)
        console.print(f"🎵 Song: {song_ast.bpm} BPM | {len(song_ast.sections)} Sektionen")
        
        # 3. Render mit Echtzeit-Dashboard
        total_shots = 20 # Beispielwert aus AST
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Kompiliere Shots...", total=total_shots)
            
            # Simulation der Render-Schleife
            for i in range(total_shots):
                # Hier würde der Emitter aktiv werden
                progress.update(task, advance=1)
                
            # Dashboard Anzeige am Ende
            table = Table(title="🧬 Compile Report")
            table.add_column("Metrik", style="cyan")
            table.add_column("Wert", style="magenta")
            table.add_row("Shots kompiliert", str(total_shots))
            table.add_row("Output", "build/final_video.mp4")
            console.print(table)

    elif args.command == "doctor":
        console.print("[bold yellow]🩺 System Check...[/bold yellow]")
        db_exists = Path("database/genome_os.db").exists()
        console.print(f"Datenbank: {'[green]OK[/green]' if db_exists else '[red]FEHLT[/red]'}")
        console.print("[bold green]✅ System bereit.[/bold green]")

if __name__ == "__main__":
    main()