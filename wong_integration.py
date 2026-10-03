"""wong_integration.py — Optionale Anbindung an WONG (WE.ED.IT OIDA Native
Genome), ein eigenständiges Schwester-Projekt (1:1 nach WONG/ kopiert;
Original: I:\\Oidasheim\\WE.ED.IT OIDA Native Genome (WONG)).

Ausgelagert aus main.py (Refactor: main.py war auf > 1150 Zeilen angewachsen).
main.py braucht von hier nur zwei Funktionen:

- init_wong_state(full_globe, log): baut Resolver/Bandit-Zustand EINMAL pro
  main.py-Lauf (nicht pro Song) auf, siehe main()/--wong-resolver.
- wong_resolve_segment(segment, idx, sync_type, wong_state): fragt WONGs
  GenomeResolver+RLBandit pro Timeline-Segment ab, rein informativ als
  Vergleichssignal im EDL (siehe main.py::_build_render_script) -- ändert
  NIE segment.clip_path bzw. den tatsächlich gerenderten Clip.

Bei jedem Fehler (Modul fehlt, DB-Aufbau schlägt fehl, ...) wird
--wong-resolver sauber deaktiviert (None/geloggt), statt den ganzen
main.py-Lauf abzubrechen.
"""
import sys
from pathlib import Path

# WONG verwendet dieselben generischen Ordner-/Paketnamen wie oefoef selbst
# (core/, styles/, models/, genome/) -- ein dauerhafter sys.path-Eintrag
# würde irgendwo im Stack beim ersten "import core" o.ä. silently das
# falsche Paket laden. Stattdessen: gezielter Datei-Import pro Modul (gleiche
# Technik wie main.py bei viral-strategy.py wegen des Bindestrichs im
# Unterordner "weedit-native"), ohne dauerhaften Seiteneffekt auf sys.path.
import importlib.util as _importlib_util

WONG_DIR = Path(__file__).resolve().parent / "WONG"

def load_wong_module(module_name: str, relative_path: str):
    """Lädt ein einzelnes Modul aus dem kopierten WONG-Repo direkt per
    Dateipfad -- kein sys.path-Eintrag, keine Namenskollision mit oefoef-
    eigenen Paketen/Ordnern.

    relative_path ist relativ zu WONG_DIR, z.B.:
        wong_models   = load_wong_module("wong_core_models", "core/models.py")
        wong_resolver = load_wong_module("wong_resolver", "genome/resolver/__init__.py")
        weed_ir       = load_wong_module("wong_weedit_ir", "weedit-native/core/ir.py")

    Wirft FileNotFoundError, falls WONG_DIR/relative_path fehlt (z.B. WONG/
    noch nicht kopiert), oder den ursprünglichen ImportError des Zielmoduls,
    falls dessen eigene Abhängigkeiten fehlen -- WONG hat ein eigenes
    requirements.txt/.venv (siehe WONG/weedit-native/requirements.txt),
    dessen Pakete ggf. separat in oefoefs .venv312 nachinstalliert werden
    müssen, bevor ein geladenes WONG-Modul tatsächlich lauffähig ist.
    """
    target = WONG_DIR / relative_path
    if not target.is_file():
        raise FileNotFoundError(f"WONG-Modul nicht gefunden: {target}")
    spec = _importlib_util.spec_from_file_location(module_name, target)
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# --- WONG-Resolver/-Bandit tatsächlich nutzen (opt-in, siehe --wong-resolver) ---
# Anders als load_wong_module() oben: core/resolver/genome_resolver.py und
# core/bandit/rl_bandit.py referenzieren sich gegenseitig per
# "from core.ir import ..." -- das braucht ein echtes, importierbares "core"-
# Package, kein reiner Datei-Pfad-Import ist hier möglich. Deshalb wird
# WONG/weedit-native NUR für die Dauer dieses einen Imports in sys.path
# gehängt und danach sofort wieder entfernt; die geladenen Module bleiben in
# sys.modules gecacht, ein zweiter Aufruf fasst sys.path also nicht nochmal
# an. oefoef selbst hat kein eigenes Top-Level-"core"-Modul -> keine
# Namenskollision zu erwarten.
def _load_wong_native_core():
    if "core.resolver.genome_resolver" in sys.modules:
        return (sys.modules["core.ir"], sys.modules["core.resolver.genome_resolver"],
                sys.modules["core.bandit.rl_bandit"])
    weedit_native_dir = str(WONG_DIR / "weedit-native")
    if not (WONG_DIR / "weedit-native" / "core" / "ir.py").is_file():
        raise FileNotFoundError(f"WONG/weedit-native nicht gefunden unter {WONG_DIR}.")
    sys.path.insert(0, weedit_native_dir)
    try:
        import core.ir as wong_ir
        import core.resolver.genome_resolver as wong_resolver_mod
        import core.bandit.rl_bandit as wong_bandit_mod
    finally:
        sys.path.remove(weedit_native_dir)
    return wong_ir, wong_resolver_mod, wong_bandit_mod

def _sync_wong_genome_db(full_globe: dict, db_path: Path) -> None:
    """Spiegelt oefoefs eigenen Clip-Pool (full_globe, siehe clip_pool.py) in
    WONGs sqlite-Schema (Tabelle "clips", siehe
    WONG/weedit-native/core/scanner/pipeline.py::_init_db), damit
    GenomeResolver.resolve() ohne WONGs eigenen Scanner auskommt. Feld-Mapping:
    oefoef "entropy"/"motion_score" -> motion_entropy, "camera_movement" ->
    camera_motion, "tags" -> genes, "duration" (Sekunden) -> duration_ms."""
    import sqlite3, json as _json
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY, file_path TEXT UNIQUE, motion_entropy REAL,
            camera_motion TEXT, genes TEXT, duration_ms INTEGER
        )""")
        rows = [
            (clip_path, clip_path,
             max(0.0, min(1.0, meta.get("entropy", meta.get("motion_score", 0.5)) or 0.5)),
             meta.get("camera_movement", "static"),
             _json.dumps(meta.get("tags") or []),
             int((meta.get("duration") or 5.0) * 1000))
            for clip_path, meta in full_globe.items() if isinstance(meta, dict)
        ]
        conn.executemany("INSERT OR REPLACE INTO clips VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()

def init_wong_state(full_globe: dict, log) -> dict | None:
    """Baut den WONG-Resolver/-Bandit-Zustand für einen kompletten main.py-Lauf
    (einmal, nicht pro Song) -- bei irgendeinem Fehler wird --wong-resolver
    sauber deaktiviert (None zurückgegeben, geloggt), statt den ganzen Lauf
    abzubrechen; gleiches Fallback-Prinzip wie beim Unreal-Renderer in main.py."""
    try:
        wong_ir, wong_resolver_mod, wong_bandit_mod = _load_wong_native_core()
    except Exception as e:
        log(f"[main] WONG nicht verfügbar (Import fehlgeschlagen: {e}) -> --wong-resolver wird ignoriert.")
        return None
    db_path = WONG_DIR / "weedit-native" / ".weed_cache" / "oefoef_genome.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _sync_wong_genome_db(full_globe, db_path)
    except Exception as e:
        log(f"[main] WONG-Genome-DB-Aufbau fehlgeschlagen ({e}) -> --wong-resolver wird ignoriert.")
        return None
    resolver = wong_resolver_mod.GenomeResolver([], db_path=db_path)
    bandit = wong_bandit_mod.RLBandit()
    song_ast = wong_ir.SongAST(title="oefoef", artist="oefoef", total_duration_ms=0,
                                sections=[], global_energy_curve=[], global_emotion_curve=[])
    log(f"[main] WONG-Resolver aktiv: {len(full_globe)} Clips nach {db_path.name} gespiegelt.")
    return {"ir": wong_ir, "resolver": resolver, "bandit": bandit, "song_ast": song_ast}

def wong_resolve_segment(segment, idx: int, sync_type: str, wong_state: dict | None) -> dict | None:
    """Fragt WONGs GenomeResolver+RLBandit, welchen Clip SIE für dieses
    Segment gewählt hätten -- rein informativ (Vergleichssignal im EDL, siehe
    main.py::_build_render_script), ändert NIE segment.clip_path bzw. den
    tatsächlich gerenderten Clip."""
    if not wong_state:
        return None
    wong_ir = wong_state["ir"]
    try:
        intent = wong_ir.ShotIntent(
            song_section=segment.section_label or "mid",
            phrase_id=f"seg_{idx:04d}",
            start_ms=int(segment.start_sec * 1000),
            end_ms=int(segment.end_sec * 1000),
            need_energy=max(0.0, min(1.0, segment.target_energy)),
            need_emotion=[str(getattr(segment, "theme", None) or "neutral")],
            need_color=[],
            need_camera=wong_ir.CameraIntent(
                movement="handheld" if segment.target_energy > 0.6 else "static",
                framing="medium", persistence_id=f"seg_{idx:04d}",
            ),
            need_rhythm=sync_type,
        )
        result = wong_state["resolver"].resolve(intent, top_k=25)
        if not result.candidates:
            return None
        decision = wong_state["bandit"].choose(intent, result, wong_state["song_ast"], [])
        return {
            "wong_pick": decision.chosen_candidate.clip_dna_id,
            "wong_reward_prediction": round(decision.reward_prediction, 4),
            "wong_reason": decision.decision_reason,
            "wong_agrees_with_oefoef": decision.chosen_candidate.clip_dna_id == segment.clip_path,
        }
    except Exception as e:
        return {"wong_error": str(e)}
