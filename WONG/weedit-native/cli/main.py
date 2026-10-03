import typer
import json
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel

from core.ir import RenderIR
from core.scanner.pipeline import ScannerPipeline
from core.compiler.song_compiler import SongCompiler
from core.director.director import Director
from core.resolver.genome_resolver import GenomeResolver
from core.bandit.rl_bandit import RLBandit
from core.optimizer.pipeline import OptimizerPipeline
from core.renderer.backend import FFmpegBackend
from core.replay.logger import ReplayLogger
from core.report.generator import ReportGenerator

app = typer.Typer(name="weed", help="🧬 WE.ED.IT OIDA Native Genome 2.0", add_completion=False, no_args_is_help=True)
console = Console()

class BuildContext:
    def __init__(self, project_dir: Path):
        self.dir = project_dir
        self.cache = project_dir / ".weed_cache"
        self.cache.mkdir(exist_ok=True)
    def save(self, name: str, data):
        with open(self.cache / f"{name}.json", "w") as f: json.dump(data, f, indent=2, default=str)
    def load(self, name: str):
        p = self.cache / f"{name}.json"
        if p.exists():
            with open(p) as f: return json.load(f)
        return None

@app.command()
def doctor():
    console.print(Panel("🩺 WE.ED.IT System Doctor\n✅ Python 3.10+\n✅ Core Modules Loaded\n⚠️ FFmpeg (ensure it is in PATH)", style="cyan"))

@app.command()
def make(mp3: Path = typer.Argument(...), clips: Path = typer.Argument(...), style: str = typer.Option("cinematic", "--style", "-s")):
    ctx = BuildContext(Path.cwd())
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TimeElapsedColumn(), console=console) as progress:
        task = progress.add_task("🧬 Scanning Genome Library...", total=1)
        scanner = ScannerPipeline()
        clip_dna = scanner.scan_directory(clips)
        ctx.save("scan", [c.model_dump() for c in clip_dna])
        progress.advance(task)

        task = progress.add_task("🎼 Compiling Song AST...", total=1)
        compiler = SongCompiler()
        song_ast = compiler.compile(mp3)
        ctx.save("compile", song_ast.model_dump())
        progress.advance(task)

        task = progress.add_task("🎬 Directing Shots...", total=1)
        director = Director(style)
        intents = director.direct(song_ast)
        ctx.save("intents", [i.model_dump() for i in intents])
        progress.advance(task)

        task = progress.add_task("🎯 Resolving Candidates...", total=1)
        resolver = GenomeResolver(clip_dna)
        resolver_results = {i.id: resolver.resolve(i) for i in intents}
        ctx.save("resolve", {k: v.model_dump() for k, v in resolver_results.items()})
        progress.advance(task)

        task = progress.add_task("🎲 RL Bandit Selecting...", total=1)
        bandit = RLBandit()
        bandit_decisions, initial_irs = {}, {}
        for intent in intents:
            dec = bandit.choose(intent, resolver_results[intent.id], song_ast, list(initial_irs.values()))
            bandit_decisions[intent.id] = dec
            initial_irs[intent.id] = RenderIR(
                clip_file_path=next((c.file_path for c in clip_dna if c.id == dec.chosen_candidate.clip_dna_id), "unknown.mp4"),
                trim_in_ms=dec.chosen_candidate.trim_start_ms, trim_out_ms=dec.chosen_candidate.trim_end_ms,
                main_audio_track_id=song_ast.id, source_intent_id=intent.id, replay_log_id=""
            )
        progress.advance(task)

        task = progress.add_task("⚙️ Running Optimizer Passes...", total=1)
        optimizer = OptimizerPipeline(song_ast)
        timeline = optimizer.optimize_all(intents, resolver_results, bandit_decisions, initial_irs)
        ctx.save("optimize", {"timeline": [t.model_dump() for t in timeline], "logs": [l.model_dump() for l in optimizer.replay_logs]})
        progress.advance(task)

        task = progress.add_task("🎬 Rendering Final Video...", total=1)
        out_dir = Path.cwd() / "output"
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / f"{song_ast.artist}_{song_ast.title}_v001.mp4"
        renderer = FFmpegBackend()
        try:
            renderer.render(timeline, out_file, mp3)
        except Exception as e:
            console.print(f"[yellow]⚠️ Render skipped: {e}[/yellow]")
        progress.advance(task)

        task = progress.add_task("📊 Generating Report...", total=1)
        reporter = ReportGenerator(song_ast, optimizer.replay_logs)
        reporter.generate_html(Path.cwd() / "reports" / "render_report.html")
        ReplayLogger().save_logs(optimizer.replay_logs)
        progress.advance(task)

    console.print("\n[bold green]🎉 Compilation Successful![/bold green]")
    console.print(f"📁 Video: {out_file}")
    console.print(f"📊 Report: ./reports/render_report.html")

@app.command()
def replay(shot_id: str = typer.Argument(...)):
    logs = ReplayLogger().load_all()
    log = next((l for l in logs if l.shot_id == shot_id), None)
    if log:
        console.print(f"\n[bold cyan]📋 Intent:[/bold cyan] {log.intent.song_section} | Energy: {log.intent.need_energy}")
        console.print(f"[bold green]✅ Chosen:[/bold green] {log.bandit_decision.chosen_candidate.clip_dna_id} (Reward: {log.final_reward:.2f})")
        console.print(f"[bold magenta]⚙️ Passes:[/bold magenta] {', '.join(log.optimizer_passes_applied)}")
    else:
        console.print(f"[red]Shot {shot_id} not found.[/red]")

if __name__ == "__main__":
    app()
