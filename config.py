"""
config.py — zentrale Konfiguration
Alle Pfade sind Windows-Pfade (r-strings), wie in deinem Setup vorgegeben.

    ██████╗ ███████╗ █████╗ ████████╗    ███████╗██╗   ██╗███╗   ██╗ ██████╗
    ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝    ██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝
    ██████╔╝█████╗  ███████║   ██║       ███████╗ ╚████╔╝ ██╔██╗ ██║██║
    ██╔══██╗██╔══╝  ██╔══██║   ██║       ╚════██║  ╚██╔╝  ██║╚██╗██║██║
    ██████╔╝███████╗██║  ██║   ██║       ███████║   ██║   ██║ ╚████║╚██████╗
    ╚══════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝       ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝

🎬 Scanne Clip-Pool in 
"""
import os
from pathlib import Path

# ── Root / Arbeitsverzeichnisse ──────────────────────────────────────────────
ROOT_DIR   = Path(os.environ.get("OIDASHEIM_ROOT", r"J:\Oidasheim\mo.gen"))
LOG_DIR    = ROOT_DIR / "logs"
TMP_DIR    = ROOT_DIR / "tmp"
DATA_DIR   = Path(__file__).resolve().parent / "data"

# ── Brain.bug Feedback Loop Directory ────────────────────────────────────────
BRAIN_BUG_DIR = Path(os.environ.get("OIDASHEIM_BRAIN_BUG", r"J:\Oidasheim\brain.bug"))
BRAIN_RL_BANDIT_STATE       = BRAIN_BUG_DIR / "rl_bandit_state.json"
BRAIN_CLIP_USAGE_MEMORY     = BRAIN_BUG_DIR / "clip_usage_memory.json"
BRAIN_LAST_RENDER_METADATA  = BRAIN_BUG_DIR / "last_render_metadata.json"
BRAIN_PROCESSED_SEGMENTS    = BRAIN_BUG_DIR / "processed_segments.json"
BRAIN_PROCESSED_SOURCES     = BRAIN_BUG_DIR / "processed_sources.json"
BRAIN_BLUEPRINT             = BRAIN_BUG_DIR / "brain.bug"

# ── Engine-/Pipeline-Version ─────────────────────────────────────────────────
# Wird in den finalen Dateinamen eingebaut (siehe main.py::_versioned_output_path,
# z.B. "...beatsync_eng1.0_v01.mp4"), damit man am Dateinamen sofort sieht, mit
# welchem Stand der Render-Pipeline (Kamera/Transitions/FX-Logik) ein Video
# erzeugt wurde. Manuell hochzählen, wenn sich am Render-Verhalten
# (renderer.py/clip_pool.py/timeline_builder.py) etwas sichtbar Ändert.
ENGINE_VERSION = "1.0"

# ── Input-Quellen ─────────────────────────────────────────────────────────────
# Mehrere MP3-Quellordner sind möglich (optional): OIDASHEIM_MP3_ROOT kann per
# ';' getrennt mehrere Pfade enthalten (z.B. "J:\...\FAVs;J:\...\Sonstige"),
# zusätzlich lässt sich pro Lauf über main.py --mp3-root <pfad> (mehrfach
# angebbar) beliebig erweitern, ohne Env/Default anzufassen. Ohne ';' verhält
# sich das exakt wie vorher (ein einzelner Ordner).
_MP3_ROOT_ENV = os.environ.get("OIDASHEIM_MP3_ROOT", r"J:\Oidasheim\Musik\FAVs\ALTgr + q")
MP3_ROOTS      = [p.strip() for p in _MP3_ROOT_ENV.split(";") if p.strip()]
MP3_ROOT_GLOB  = MP3_ROOTS[0] if MP3_ROOTS else _MP3_ROOT_ENV  # Rückwärtskompatibilität (alter Einzel-Pfad-Name)

# Wurzelordner aller Song-Unterordner (Musik\FAVs\<name>\...) — hier liegen
# neben den mp3s auch die Traktor-Tracklisten-Exports (*.nml, *.htm/*.html),
# aus denen song_semantics.py die volle Lyrics-/Beat-Switch-/Mood-Semantik
# lernt (siehe song_semantics.scan_and_learn()). Unabhängig von MP3_ROOTS,
# das nur den aktuellen Render-Scope einschränkt.
FAVS_ROOT = Path(os.environ.get("OIDASHEIM_FAVS_ROOT", r"J:\Oidasheim\Musik\FAVs\ALTgr + q"))
MUSIK_ROOT = Path(os.environ.get("OIDASHEIM_MUSIK_ROOT", r"J:\Oidasheim\Musik"))
SUNO_TXT_ROOT = Path(os.environ.get("OIDASHEIM_SUNO_TXT_ROOT", r"J:\Oidasheim\Musik\suno txt"))

# Nutzergeschmack (Likes/Dislikes je Clip-Tag) — siehe user_prefs.py, fließt
# als deterministischer Scoring-Bonus/Malus in timeline_builder._pick_clip ein.
USER_PREFS_PATH = Path(os.environ.get("OIDASHEIM_USER_PREFS", str(ROOT_DIR / "user_preferences.yaml")))


# ── Upload-Metadaten (viral-strategy.py / main.py) ──────────────────────────
# Vorher hart als "oefoef" im Code verdrahtet (main.py::process_song). Jetzt
# per Env überschreibbar, ohne main.py anzufassen.
LABEL_NAME = os.environ.get("OIDASHEIM_LABEL_NAME", "oefoef")
# Absoluter Letzt-Fallback für die Hashtag-Nische, NUR falls noch KEINE
# einzige song_semantics-Zeile (siehe song_semantics.py) mit Mood-Tags
# existiert, aus der viral_strategy.learn_default_niche() sonst lernen könnte
# (main.py ruft das einmal pro main()-Lauf auf und reicht das Ergebnis pro
# Song durch). Wächst der Katalog, verliert dieser Wert an Bedeutung.
DEFAULT_HASHTAG_NICHE = os.environ.get("OIDASHEIM_DEFAULT_NICHE", "hiphop")

CLIP_POOL_DIR   = Path(os.environ.get("OIDASHEIM_CLIP_POOL", r"J:\raw_vidz\_raw_reorga__"))
# Optional: ClipPool auf bestimmte Unterordner einschränken (z.B. nur
# "subdir1","subdir2" statt des kompletten Pools) — sowohl für den Analyse-Scan
# (clip_pool.find_clips) als auch für die tatsächliche Clip-Auswahl beim Render
# (clip_pool.filter_globe_to_subdirs). Per Env OIDASHEIM_CLIP_POOL_SUBDIRS
# (';'-getrennt) oder main.py --clip-subdir <name> (mehrfach angebbar)
# steuerbar. Leer = kompletter Pool wie bisher.
_CLIP_POOL_SUBDIRS_ENV = os.environ.get("OIDASHEIM_CLIP_POOL_SUBDIRS", "")
CLIP_POOL_SUBDIRS = [s.strip() for s in _CLIP_POOL_SUBDIRS_ENV.split(";") if s.strip()]

# ── TikTok-Optimierungsmodus (Vertical-Only Clip-Pool) ───────────────────────
# Im TikTok-Modus (main.py --platform tiktok) werden AUSSCHLIESSLICH Clips aus
# diesen ClipPool-Unterordnern zugelassen (kein 16:9-Querformat-Quellmaterial,
# das ohnehin nur zoom-gecroppt werden müsste) — vertikale/quadratische
# Quellen lassen sich randlos füllend zuschneiden. Nutzt denselben Mechanismus
# wie CLIP_POOL_SUBDIRS/clip_pool.filter_globe_to_subdirs, nur fest an
# platform="tiktok" gekoppelt statt global konfiguriert.
TIKTOK_CLIP_SUBDIRS = ["9zu16", "1zu1"]

# ── Output-Ablage: neben der Quell-MP3 statt in einem globalen Ordner ───────
# Jeder Song bekommt seinen Output NEBEN der mp3 (Path(song.path).parent),
# in einem Unterordner je nach Ausgabeprofil -> "16zu9" (voller Song, YouTube-
# optimiert) oder "9zu16" (TikTok-Short, vertikal). Nur wirksam, wenn
# main.py --output-dir NICHT explizit gesetzt wurde (sonst hat der explizite
# Pfad weiterhin Vorrang, altes Verhalten).
OUTPUT_SUBDIR_BY_PLATFORM = {"full": "16zu9", "tiktok": "9zu16"}

# ── Persistente Datenablagen (bereits vorhanden laut Vorgabe) ────────────────
BEAT_SYNC_DB       = DATA_DIR / "beat_sync.db"                 # SQLite: Song-Analysen + Usage-History
FLAT_GLOBE_JSON    = DATA_DIR / "libsync-flat-globe.db.json"   # Cache: Clip-Feature-Index
HAAR_CASCADE_PATH  = ROOT_DIR / "haarcascade_frontalface_default.xml"
SONGS_CSV          = ROOT_DIR / "alle_songs_extrahiert.csv"    # optionaler Fast-Path für mp3tag-Daten

# ── ffmpeg / ffprobe (direkt als Subprocess, kein moviepy o.ä.) ──────────────
FFMPEG_BIN  = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# ── Clip-Source-Tagging (siehe clip_tagging.py) ─────────────────────────────
# Schreibt nach jedem erfolgreichen Render zusätzlich zu den bereits
# vorhandenen Output-MP4-Tags (siehe renderer._write_ffmetadata_file) auch
# "wann/wie/wo/was/warum verwendet"-Metadaten + volle Analyse-Metainfos
# DIREKT in die MP4-Tags der QUELL-Clip-Dateien selbst (per verlustfreiem
# ffmpeg-Remux, -c copy, keine Neucodierung). Modifiziert die Original-Clip-
# Bibliothek -- daher per Flag abschaltbar (main.py --no-clip-tags).
TAG_SOURCE_CLIPS_ENABLED     = True
# Wie viele der letzten Verwendungen pro Clip im "synopsis"-Tag aufgehoben
# werden (neueste zuerst) -- verhindert unbegrenztes Wachstum bei Clips, die
# über sehr viele Songs/Läufe hinweg immer wieder verwendet werden.
CLIP_TAG_USAGE_LOG_MAX_ENTRIES = 25
# Parallele ffmpeg-Remux-Prozesse beim Clip-Tagging (I/O-bound, siehe
# clip_tagging.tag_clips_after_render) -- bewusst niedrig, da dies NACH dem
# eigentlichen Render läuft und die restliche Maschine (Encoder etc.) nicht
# zusätzlich belasten soll.
CLIP_TAG_WORKERS = 4
CLIP_TAG_TIMEOUT_SEC = 30

# ── Rendering ─────────────────────────────────────────────────────────────────
OUTPUT_FPS          = 30
OUTPUT_RESOLUTION   = (1920, 1080)  # DEFAULT: Final optimierte 1920x1080 Full-HD Auflösung für maximale NVENC-Performance & Stabilität.
# BUGFIX: Der TikTok-Modus (platform="tiktok") schränkt zwar die Clip-QUELLE
# bereits auf vertikale/quadratische Clips ein (siehe TIKTOK_CLIP_SUBDIRS
# oben), aber renderer.render_music_video() rendert bisher IMMER auf
# OUTPUT_RESOLUTION (1920x1080, 16:9) -- egal welche Plattform. Ergebnis:
# TikTok-Videos kamen trotz korrekter (vertikaler) Quell-Clips als 16:9-
# Breitbild raus (Content wurde einfach reingecropt statt das Zielformat
# selbst zu drehen). TIKTOK_OUTPUT_RESOLUTION ist das tatsächliche
# TikTok-Zielformat (9:16 vertikal); renderer.py wählt jetzt anhand des
# übergebenen platform-Parameters aus OUTPUT_RESOLUTION_BY_PLATFORM.
TIKTOK_OUTPUT_RESOLUTION   = (1080, 1920)
OUTPUT_RESOLUTION_BY_PLATFORM = {"full": OUTPUT_RESOLUTION, "tiktok": TIKTOK_OUTPUT_RESOLUTION}

# ── Video-Collagen (Multi-Kachel-Grid mit erhaltenem Seitenverhältnis) ──────
# main.py --collage <layout-name> aktiviert einen alternativen Render-Pfad
# (siehe collage_builder.py/collage_renderer.py): statt EINES Clips pro
# Segment laufen mehrere Clips gleichzeitig in einem festen Grid, das exakt
# in die Ziel-Auflösung passt -- OHNE dass ein Clip gecroppt wird (jede
# Kachel behält ihr deklariertes natives Seitenverhältnis, siehe "ar" unten).
# "subdirs" verweist auf die ClipPool-Unterordner (wie TIKTOK_CLIP_SUBDIRS),
# aus denen genau diese Kachel ihre Clips zieht -- eine 16:9-Kachel zieht aus
# "16zu9"-Clips, eine 9:16-Kachel aus "9zu16" usw., damit möglichst wenig
# Innen-Letterbox pro Kachel nötig ist.
COLLAGE_LAYOUTS = {
    "tiktok": {   # Ziel-Canvas 1080x1920 (siehe TIKTOK_OUTPUT_RESOLUTION)
        "stack3_16x9": {
            "direction": "vertical",   # Kacheln übereinander gestapelt
            "tiles": [
                {"ar": (16, 9), "subdirs": ["16zu9"]},
                {"ar": (16, 9), "subdirs": ["16zu9"]},
                {"ar": (16, 9), "subdirs": ["16zu9"]},
            ],
        },
        "square_top_16x9_bottom": {
            "direction": "vertical",
            "tiles": [
                {"ar": (1, 1), "subdirs": ["1zu1"]},
                {"ar": (16, 9), "subdirs": ["16zu9"]},
            ],
        },
    },
    "full": {     # Ziel-Canvas 1920x1080 (siehe OUTPUT_RESOLUTION)
        "side3_9x16": {
            "direction": "horizontal",  # Kacheln nebeneinander in einer Reihe
            "tiles": [
                {"ar": (9, 16), "subdirs": ["9zu16"]},
                {"ar": (9, 16), "subdirs": ["9zu16"]},
                {"ar": (9, 16), "subdirs": ["9zu16"]},
            ],
        },
        "square_16x9_side": {
            "direction": "horizontal",
            "tiles": [
                {"ar": (1, 1), "subdirs": ["1zu1"]},
                {"ar": (9, 16), "subdirs": ["9zu16"]},
            ],
        },
    },
}
COLLAGE_LETTERBOX_COLOR = "black"  # Füllfarbe für Restrand, wenn N Kacheln nicht exakt die Canvas-Achse füllen
# Bonus-Gewicht im Kachel-Clip-Scoring (siehe timeline_builder._pick_clip
# extra_score_fn / collage_builder.build_collage_timelines), wenn die
# Bewegungsrichtung zweier BENACHBARTER Kacheln (bei horizontalen Layouts)
# zueinander passt -- simuliert eine durchgehende Bewegung über die
# Kachelgrenze hinweg ("Objekt fliegt von Kachel A weiter in Kachel B").
COLLAGE_MOTION_MATCH_BONUS = 0.30
# Bonus-Gewicht, wenn eine Kachel (v.a. bei vertikalen Stapel-Layouts, wo es
# keine verlässliche vertikale Bewegungsachse im Clip-Cache gibt) thematisch
# zur bereits gewählten Nachbar-Kachel im selben Segment passt (Tag-Overlap
# mit deren Theme) -- sorgt für inhaltliche statt nur Bewegungs-Kohärenz.
COLLAGE_THEME_MATCH_BONUS = 0.20
# UPGRADE: H.264 -> HEVC/H.265 (deutlich bessere Kompression bei gleicher/
# besserer Qualitaet, ~40-50% kleinere Dateien bei vergleichbarem CRF-
# Eindruck). WICHTIG: renderer.py's Push-Fade-/Scratch-Uebergaenge wurden
# entsprechend angepasst, damit KEIN Segment mehr hart auf "libx264"
# verdrahtet ist -- der finale concat-Demuxer laeuft mit "-c copy" und
# verlangt identische Codec-Parameter ueber ALLE Segmente hinweg; ein
# Mischbetrieb haette den Concat-Schritt zum Absturz gebracht oder
# korrupten Output erzeugt.
# Kompatibilitaets-Hinweis: HEVC in .mp4 spielt auf aelteren/Nicht-Apple-
# Geraeten und manchen Browsern nicht immer nativ ab (YouTube selbst
# transcodiert ohnehin serverseitig -- dort kein Problem).
VIDEO_CODEC_CPU     = "libx265"
VIDEO_CODEC_NVENC   = "hevc_nvenc"      # Fallback auf CPU falls NVENC nicht verfügbar
USE_NVENC_IF_AVAIL  = True
CRF                 = 16                # war 18 -- etwas hoehere Zielqualitaet (x265-CRF-Skala liegt ohnehin ~4-6 unter x264 bei gleichem visuellen Eindruck)
ENCODE_PRESET       = "medium"          # BUGFIX: war importiert, aber nie tatsaechlich verwendet -- renderer.py
                                         # hatte "medium" an allen 4 Encode-Stellen hart verdrahtet, unabhaengig
                                         # von diesem Wert. Jetzt echt verdrahtet (siehe renderer.py). Auf "medium"
                                         # belassen, um die bisherige Render-Geschwindigkeit nicht zu aendern --
                                         # "slow" liefert etwas bessere Kompression bei gleicher CRF, aber je nach
                                         # Clip/Hardware spuerbar (~1.5-2x) laengere Encode-Zeiten pro Segment.

# ── Hardware-Erkennung / adaptive Render-Parallelität (siehe hardware.py) ──
# BUGFIX (RAM/CPU ~99% durch ffmpeg): render_silent_video() startete bisher
# blind bis zu min(8, cpu_count) parallele ffmpeg-Encodes, OHNE zu
# beachten, dass (a) jede Instanz ohne -threads-Deckel selbst versucht ALLE
# Kerne zu nutzen (massives Oversubscription) und (b) jede Instanz -- v.a.
# bei 4K+libx265 -- mehrere hundert MB bis wenige GB RAM braucht. Jetzt
# ermittelt hardware.recommend_encode_plan() vor jedem Render tatsächlich
# verfügbare Kerne UND verfügbaren RAM und leitet daraus sowohl Worker-Zahl
# als auch Threads/Worker ab.
RENDER_RESERVE_CORES          = 1    # mind. 1 Kern für OS/Rest-System frei lassen
RENDER_MAX_WORKERS_HARD_CAP   = 8    # absolute Obergrenze paralleler CPU-Encodes, unabhängig von Kernzahl
RENDER_MIN_WORKERS            = 1
RENDER_MAX_THREADS_PER_WORKER = 8    # ffmpeg/x264/x265 skalieren über ~8-16 Threads kaum noch sinnvoll
NVENC_MAX_WORKERS             = 4    # Ermöglicht parallele Hardware-Encodes (bis zu 4-5 Sessions auf modernen GeForce-Treibern)
RENDER_RAM_SAFETY_FRACTION    = 0.65 # max. Anteil des VERFÜGBAREN (nicht totalen) RAMs für ALLE Worker zusammen
RAM_FALLBACK_GB                = 8.0  # falls weder psutil noch Windows/Linux-Bordmittel verfügbar sind

# Grobe RAM-Schätzung pro Encode-Worker, Baseline 1080p/libx264/medium (siehe
# hardware.estimate_ram_per_worker_mb). Reale Werte hängen stark von
# Filterkomplexität (zoompan/perspective) und Szeneninhalt ab -- bewusst
# konservativ (eher zu hoch) geschätzt: ein überschätzter RAM-Bedarf kostet
# nur etwas Parallelität, ein unterschätzter riskiert Swapping/OOM.
ESTIMATED_RAM_MB_1080P_LIBX264_MEDIUM = 450
CODEC_RAM_MULTIPLIER = {
    "libx264":    1.0,
    "libx265":    1.7,   # x265 hält deutlich mehr Referenz-/Lookahead-Buffer im RAM
    "hevc_nvenc": 0.6,   # Encode läuft auf GPU-VRAM, CPU-seitiger RAM-Bedarf (Decode+Filter) geringer
    "h264_nvenc": 0.5,
}
PRESET_RAM_MULTIPLIER = {
    "ultrafast": 0.6, "superfast": 0.65, "veryfast": 0.7, "faster": 0.8,
    "fast": 0.9, "medium": 1.0, "slow": 1.3, "slower": 1.6, "veryslow": 2.0,
}

# ── Render-Backend: ffmpeg (Standard) vs. Unreal Engine (Movie Render Queue) ─
# ffmpeg (renderer.py) bleibt das Default-Backend und funktioniert unverändert
# ohne jede weitere Einrichtung. Unreal Engine (unreal_renderer.py) ist ein
# ALTERNATIVES Backend über Unreal's "Movie Render Queue" -- Stand jetzt noch
# NICHT installiert/eingerichtet. Die Pfade unten sind bewusst leer (None):
# main.py erkennt das automatisch und fällt sauber auf ffmpeg zurück, statt
# abzubrechen (siehe unreal_renderer.UnrealNotConfiguredError).
#
# Einrichtung, SOBALD Unreal installiert ist:
#   1. UNREAL_ENGINE_CMD auf UnrealEditor-Cmd.exe zeigen lassen, z.B.
#      r"C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
#   2. UNREAL_PROJECT_PATH auf die eigene .uproject-Datei zeigen lassen.
#   3. UNREAL_MAP / UNREAL_MRQ_CONFIG auf die im Projekt angelegte Render-
#      Map bzw. das Movie-Render-Queue-Preset-Asset setzen.
#   4. main.py --renderer unreal (oder RENDERER_BACKEND = "unreal" hier
#      dauerhaft) aktivieren.
RENDERER_BACKEND          = "ffmpeg"   # "ffmpeg" (Standard) oder "unreal"
UNREAL_ENGINE_CMD         = r"D:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
UNREAL_PROJECT_PATH       = r"I:\Users\daaau\Documents\Unreal Projects\testue1\testue1.uproject"
UNREAL_MAP                = "/Game/Maps/BeatSyncStage"        # Render-Level (Asset-Pfad)
UNREAL_MRQ_CONFIG         = "/Game/MRQ/DefaultConfig"         # Movie Render Queue Preset (Asset-Pfad)
UNREAL_RENDER_TIMEOUT_SEC = 3600       # Sicherheits-Timeout für den Unreal-Subprocess

# ── Unreal-Start-Image (Intro-Standbild vor dem ersten Clip-Segment) ────────
# Optional: Pfad zu EINEM Bild ODER einem Ordner voller Bilder, das/der als
# stehendes Intro-Frame vor die eigentliche Clip-Timeline gehängt wird (siehe
# unreal_renderer._resolve_start_image / unreal_side/build_and_render.py
# _build_level_sequence). Zeigt der Pfad auf einen Ordner, wird pro Song
# deterministisch (Hash über song_path, siehe SONG_TOUCH_SEED_SALT-Prinzip)
# genau EIN Bild daraus gewählt -- gleicher Song = immer dasselbe Startbild,
# verschiedene Songs bekommen unterschiedliche Startbilder aus dem Pool.
# None/leer = kein Start-Image, Timeline beginnt wie bisher direkt mit dem
# ersten Clip-Segment. Nur wirksam mit --renderer unreal.
UNREAL_START_IMAGE_PATH          = r"J:\Oidasheim\oefoef\IMGs\upscayl_png_digital-art-4x_2x"
UNREAL_START_IMAGE_DURATION_SEC  = 3.0   # wie lange das Startbild stehen bleibt, bevor die Clip-Timeline beginnt

# ── Beat / Segmentierung ──────────────────────────────────────────────────────
# ── Beat / Segmentierung ──────────────────────────────────────────────────────
MIN_SEGMENT_SEC     = 0.28     # kürzeste erlaubte Cut-Länge (bei sehr hoher Energie / Stutter)
MAX_SEGMENT_SEC     = 2.4      # dynamische Obergrenze gegen Standbild-Gefühl (vorher 3.5s)
SECTION_SMOOTH_SEC  = 4.0      # Fenstergröße zur Song-Sektionserkennung

# ── Atem-/Pausen-Dehnung (rhythmisch passende Clip-Verlängerung) ────────────
# In sehr ruhigen Zonen (Pausen, Atmen, langgezogene Endtakte/Fade-Outs) darf
# ein Segment über MAX_SEGMENT_SEC hinaus laufen, statt stur im normalen
# Energie-Raster geschnitten zu werden -> der Clip "atmet" mit der Musik statt
# stumpf durchzuschneiden. Nur wirksam bei SEHR niedriger lokaler Energie
# (siehe timeline_builder._maybe_extend_for_breath). Gilt nur im vollen
# Songformat — TikTok-Shorts bleiben bewusst im knackigen 15s-Hook-Rhythmus.
BREATH_ENERGY_THRESHOLD  = 0.15   # unterhalb dieser Energie gilt eine Stelle als Pause/Atmen
BREATH_SEGMENT_MAX_SEC   = 4.8    # Obergrenze für gedehnte Atem-/Pausen-Segmente (vorher 7.0)
BREATH_EXTEND_FACTOR     = 1.5    # Multiplikator auf die normale energie-basierte Segmentlänge

# ── Stem-Separation (Drums/Vocals/Bass/Other) für saubereres Beat-Matching ──
# Trennt den Song vor dem Beat-Tracking in Einzelspuren (siehe
# stem_separator.py) — die Drum-Stem liefert ein deutlich saubereres
# Beat-Tracking als der volle Mix (Vocals/Melodie überlagern sonst die
# Transienten). Stems werden NEBEN der mp3 unter STEM_DIR_NAME gecached und
# nie doppelt getrennt.
STEM_SEPARATION_ENABLED = True
STEM_BACKEND            = "auto"   # "auto" (Demucs, Fallback HPSS) | "demucs" | "hpss"
STEM_DIR_NAME           = "stems"

# ── Clip-Auswahl / Anti-Repeat & 2/3 Pool-Sperre über Sessions hinweg ────────
NO_REPEAT_WINDOW              = 24      # letzte N genutzte Ausschnitte im aktuellen Render gesperrt (vorher 12)
MAX_CLIP_USES_TOTAL           = 2       # max. Wiederholungen eines Clips pro Video (vorher 3, für maximale Vielfalt)
STILL_FRAME_SCORE_MAX         = 0.55
FACE_BOOST_VOCAL              = 0.25    # Bonus-Gewicht für Clips mit Gesicht in vokal-/emotionalen Abschnitten
SEMANTIC_WEIGHT               = 0.6     # Gewicht Tag-Similarity vs. 0.4 Energie-Match
PARTIAL_REPEAT_COOLDOWN_SEC   = 1800.0  # 30 Minuten (vorher 60s) für zeitbereichs-basierte Ausschnittssperre
PARTIAL_REPEAT_PADDING_SEC    = 1.5     # Sicherheitsabstand (s) um gesperrte Ausschnitte herum

# 2/3 Session-Pool-Sperre & globale Frische-Exploration
SESSION_POOL_LOCK_ENABLED     = True    # 2/3 Pool-Sperre über Sessions hinweg aktiv
SESSION_POOL_LOCK_RATIO       = 0.667   # Bis zu 2/3 (66.7%) der zuletzt/am häufigsten genutzten Clips sperren
SESSION_COOLDOWN_HOURS        = 48.0    # Stunden, die ein genutzter Clip sessionsübergreifend gesperrt bleibt
SESSION_MAX_GLOBAL_USES       = 5       # Max. kumulierte Nutzungen über alle Sessions, bevor Cooldown greift

# Multi-Domain & Vielfalts-Boni
DIVERSITY_EXPLORATION_BONUS    = 0.20    # Scoring-Bonus für bisher ungenutzte/seltene Clips (uses == 0 oder 1)
DIVERSITY_USAGE_PENALTY_WEIGHT = 0.08    # Logarithmische Dämpfung für zu häufig genutzte Clips
DIVERSITY_DOMAIN_SWITCH_BONUS  = 0.12    # Bonus für thematischen/visuellen Wechsel zwischen Sektionen
DIVERSITY_TEMPERATURE          = 0.85    # Softmax-Sampling-Temperatur für abwechslungsreiche Clip-Wahl

# ── Virtuelle Kamera (dynamisches Pan/Zoom / Viral Beat-Sync) ────────────────
CAMERA_ENABLED          = True
CAMERA_MIN_SEGMENT_SEC  = 0.4    # ab dieser Länge greift Kamera-Animation
CAMERA_HEADROOM         = 1.35   # Zoom-Reserve (Arbeits-Canvas ggü. Zielauflösung)
ASPECT_FILL_THRESHOLD   = 0.08   # ab dieser Abweichung vom Ziel-Seitenverhältnis wird gefüllt statt gepaddet
HOLD_STATIC_MOTION_MAX  = 0.40   # unterhalb dieses motion_score bekommt jeder Clip einen organischen Push

# Dynamische, virale Zoom-Ziele: Musikvideo-Feel statt Diashow
PUSH_ZOOM_TARGET        = 1.09   # dynamischer Ziel-Zoom für "push" am Segmentende
SNAP_ZOOM_TARGET        = 1.15   # punchy Hit-Zoom für Beat-Drops und Snare-Schläge
SNAP_PUNCH_FRACTION     = 0.20   # Anteil des Segments, in dem der Snap-Zoom einschlägt
DRIFT_ZOOM_TARGET       = 1.05   # fließender Cinematic Drift
HOLD_SOFT_PUSH_TARGET   = 1.04   # sanfter kontinuierlicher Push gegen Standbild-Gefühl
HOLD_SOFT_PUSH_BOOST_MAX = 2.2   # max. Verstärkung des Soft-Push-Zoom-Hubs bei motion_score nahe 0
MAX_PAN_FRACTION        = 0.48   # genutzter Anteil des Pan-Spielraums

# ── Motion-Continuity & Pseudo-3D (räumliche Perspektive) ────────────────────
CAMERA_FOLLOW_MOTION_DIRECTION = True
CAMERA_MOTION_FOLLOW_STRENGTH  = 0.75   # Gewicht erkannte Richtung vs. Zufalls-Seed
CAMERA_PERSPECTIVE_ENABLED     = True
CAMERA_PERSPECTIVE_STRENGTH    = 0.035  # räumlicher Keystone/Perspective-Shift in Pan-Richtung

# ── Elastic / Rubber-Band Kamerabewegung (polyrhythmisch) ───────────────────
CAMERA_RUBBER_BAND_ENABLED       = True
CAMERA_RUBBER_CYCLES_CHOICES     = [1.5, 2.0, 2.5, 3.0]  # Schwingungen über die Segmentdauer (Polyrhythmik)
CAMERA_RUBBER_DAMPING            = 2.2    # Dämpfung der Pan-Schwingung
CAMERA_ELASTIC_DECAY             = 5.5    # Dämpfung des Zoom-Elastic-Ease
CAMERA_ELASTIC_OVERSHOOT_CYCLES  = 0.6    # Anzahl Überschwing-Ripple im Zoom-Ease-Out
CAMERA_MC_MOTION_DAMPENING       = 0.5    # Dämpfungsanteil bei hoher MC-Eigenbewegung
CAMERA_RUBBER_PAN_RIPPLE_FRACTION = 0.35  # Anteil Pan-Oszillation

# ── Clip-übergreifender Bewegungsfluss (Motion-Flow-Continuity) ─────────────
# motion_direction (siehe clip_pool.py) floss bisher NUR in zwei Stellen ein:
# 1) renderer._plan_camera (Kamera-Pan INNERHALB eines Segments folgt der im
#    Clip erkannten Richtung, siehe CAMERA_FOLLOW_MOTION_DIRECTION oben) und
# 2) den Collage-Modus (COLLAGE_MOTION_MATCH_BONUS, Kachel-zu-Kachel-Abgleich
#    im selben Zeitfenster). Bei der eigentlichen CLIP-AUSWAHL für den
#    NÄCHSTEN Zeitpunkt in der normalen Single-Clip-Timeline
#    (timeline_builder._pick_clip) spielte die Bewegungsrichtung des
#    VORHERIGEN Segments dagegen nie eine Rolle -- jedes Segment wurde für
#    sich genommen optimal gewählt, aber die Abfolge konnte trotzdem wild
#    zwischen "Bild driftet nach links" und "Bild driftet nach rechts"
#    hin- und herspringen. Bei ruhigem Schnitttempo fällt das kaum auf, aber
#    genau bei den schnellen, energiereichen Cut-Ketten (siehe
#    RHYTHM_COMPRESSION_RATIO in main.py) summiert sich das zu einem
#    optisch chaotischen Eindruck, obwohl jeder einzelne Clip für sich genau
#    richtig gewählt war -- kein erkennbarer visueller "roter Faden" trotz
#    technisch korrekter Cuts.
#
# MOTION_FLOW_CONTINUITY_BONUS (siehe timeline_builder._motion_flow_bonus)
# gibt Kandidaten einen Scoring-Bonus, deren motion_direction in dieselbe
# Richtung zeigt wie das direkt vorhergehende Segment -- schafft dadurch
# über mehrere schnelle Cuts hinweg einen durchgehend wahrnehmbaren
# Bewegungsfluss (die Reihe der Cuts wirkt wie eine fortgesetzte Kamerafahrt/
# Aktion statt wie zufällig gewürfelte Einzelbilder), OHNE die eigentliche
# Song<->Clip-Semantik-Auswahl zu verdrängen (rein additiver Bonus, kein
# Ausschlusskriterium -- ein semantisch klar passender Clip mit
# "falscher" Richtung kann trotzdem gewinnen).
MOTION_FLOW_CONTINUITY_ENABLED = True
# Bewusst niedriger als MOTION_DIRECTION_THRESHOLD (0.35, siehe oben) — dort
# geht es um eine sichtbare RENDER-Aktion (Push-Fade-Transition), hier nur
# um ein leichtes Scoring-Gewicht. Ein zu hoher Threshold würde die meisten
# real gemessenen motion_direction-Werte als "richtungslos" behandeln und
# den Bonus faktisch nie auslösen.
MOTION_FLOW_DIRECTION_THRESHOLD = 0.15
MOTION_FLOW_CONTINUITY_BONUS    = 0.22   # max. Scoring-Bonus bei voller Übereinstimmung (Stufe-1-Score liegt typ. in [0,1])
# Unterhalb dieser Segmentlänge (Sekunden) gilt ein Cut als "schnell" -- genau
# dort fällt ein Richtungssprung dem Auge am stärksten auf, der Bonus wirkt
# hier mit vollem Gewicht. Zwischen FAST_ und SLOW_CUT_SEC skaliert das
# Gewicht linear auf 0 herunter, weil ein einzelner Richtungswechsel bei
# ruhigem Schnitttempo kaum noch als Bruch wahrgenommen wird.
MOTION_FLOW_FAST_CUT_SEC = 1.2
MOTION_FLOW_SLOW_CUT_SEC = 4.0
# Nach so vielen aufeinanderfolgenden Segmenten mit übereinstimmender
# Richtung wird der Bonus für das NÄCHSTE Segment ausgesetzt (nicht negiert)
# -- verhindert, dass die Auswahl über viele Cuts stur in eine Richtung
# "wegdriftet"; danach darf eine neue Richtung gewählt und von dort eine neue
# Fluss-Kette aufgebaut werden.
MOTION_FLOW_MAX_STREAK = 5

# ── Speed Ramps (rhythmische Dynamik) ────────────────────────────────────────
# Kurze/energiereiche Segmente werden beschleunigt (Whip-Feel), lange/ruhige
# Segmente leicht verlangsamt (Slow-Mo-Atmung). Die Segmentdauer selbst bleibt
# IMMER exakt erhalten (siehe renderer.py::_speed_ramp_filter) — nur die
# gefühlte Abspielgeschwindigkeit des Quellmaterials ändert sich, damit Audio/
# Video niemals aus dem Sync laufen.
SPEED_RAMP_ENABLED  = True
SPEED_RAMP_MIN      = 0.80     # langsamste Rampe (ruhige/lange Segmente)
SPEED_RAMP_MAX      = 1.40     # schnellste Rampe (kurze/energiereiche Segmente)
SPEED_RAMP_FREEZE_PAD_MAX_SEC = 0.05

# ── OpenRouter / LLM Vision & Planning Configuration ───────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL   = os.environ.get("OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct")
OPENROUTER_APP_ID  = "4041920880828783"

# ── Schnelle Wiederholungen (Stutter/Flash) & Slide-Reaktionen ───────────────
REPETITION_ONSET_WINDOW_SEC = 1.5     # Fenstergröße für die Onset-Raten-Messung
REPETITION_RATE_THRESHOLD   = 4.5     # Onsets/Sekunde ab denen "schnelle Wiederholung" gilt
REPETITION_FLASH_COUNT      = 2       # Anzahl kurzer Akzent-Flashes pro Wiederholungs-Segment
REPETITION_FLASH_PULSE_SEC  = 0.05    # Breite jedes einzelnen Flash-Pulses
REPETITION_FLASH_STRENGTH   = 0.18    # Kontrast-Pump-Amplitude am Peak jedes Flashes
SLIDE_TRANSITION_ENABLED    = True     # Push/Fade-Übergang am Einstieg wiederholungs-/whip-markierter Segmente
MOTION_DIRECTION_THRESHOLD  = 0.25     # ab diesem |motion_direction|-Betrag gilt die Richtung als eindeutig genug
PUSH_FADE_SEC               = 0.14     # Gesamtdauer des Standbild-Push-Hints
PUSH_FADE_PUSH_FRACTION     = 0.15     # Anteil der Bildbreite, um den das Standbild im Push angeschupst wird
PUSH_FADE_XFADE_SEC         = 0.08     # Dauer des abschließenden schnellen Fades in den nächsten Clip

# ── Drum-Stem Transienten & Akzent-Wiederholungen ──────────────────────────────
DRUM_STEM_SYNC_ENABLED            = True     # Nutzt isolierte Drum-Stem für Transient-Snapping & Akzente
DRUM_TRANSIENT_SNAP_TOLERANCE_SEC = 0.06     # Max. Zeitversatz beim Einrasten auf Drum-Transienten-Peaks (Attack-Phase)
DRUM_BURST_RATE_THRESHOLD         = 5.5      # Drum-Onsets/Sekunde für schnelle Accent-Bursts / Rolls (1/16, 1/32)
DRUM_BURST_WINDOW_SEC             = 0.80     # Zeitfenster zur Erkennung schneller Drum-Rolls & Stakkato
DRUM_MICRO_CUT_ENABLED            = True     # Erlaubt dynamische Sub-Cuts / Micro-Slices bei schnellen Drum-Rolls
DRUM_MICRO_CUT_MIN_BURST_DUR      = 0.40     # Mindestdauer eines Drum-Bursts für Stutter/Micro-Cuts
DRUM_MICRO_CUT_MAX_SLICES         = 4        # Maximale Anzahl Slices pro Drum-Roll-Segment
DRUM_ROLL_SPEED_RAMP_BOOST        = 1.50     # Speed-Ramp-Faktor während intensiver Drum-Rolls / Fills

# ── Cut-Style / Sync-Type Wiring (main.py._calculate_cut_style / _calculate_sync_type) ──
CUT_STYLE_DISSOLVE_ENABLED   = True     # cut_style=="dissolve" löst einen weichen Crossfade-Übergang aus (statt Push/Fade)
CUT_STYLE_DISSOLVE_SEC       = 0.15     # Dauer des Crossfades
CUT_STYLE_WHIP_FORCE_PUSH    = True     # cut_style=="whip" triggert den Push/Fade-Übergang auch OHNE transition=="slide"
CUT_STYLE_PUSH_ZOOM_BOOST    = 1.35     # Multiplikator auf den Zoom-Hub bei cut_style=="push"
CUT_STYLE_BREAK_ZOOM_DAMPEN  = 0.4      # Dämpfungsfaktor auf den Zoom-Hub bei cut_style=="break"
FADE_OUT_VIDEO_SEC           = 0.6      # Dauer des Bild-Ausblendens am allerletzten Segment (cut_style=="fade_out")
FADE_OUT_AUDIO_SEC           = 1.2      # Dauer des Audio-Fades am Songende (nur wenn das letzte Segment fade_out ist)
SYNC_TYPE_SNAP_ZOOM_BOOST    = 1.30     # zusätzlicher Zoom-Boost für "snap"-Kamera bei sync_type in (snap_drop, energy_peak)
SYNC_TYPE_BREATH_DAMPEN      = 0.3      # Kamerabewegung wird bei sync_type=="breath" gedämpft

# ── Style Color-Grade & FX Rendering (StyleSpec.lighting/color/fx) ──────────
# main.py/timeline_builder.py schreiben pro Segment bereits lighting/color
# (aus dem Style, siehe creative_genome.StyleSpec) sowie die Style-FX-Liste
# (segment.fx) in die Timeline.
# STYLE_COLOR_GRADE_ENABLED = False lässt alle künstlichen Farbfilter weg,
# sodass das Originalmaterial farbecht und unverfälscht in 100% nativer Qualität bleibt.
STYLE_COLOR_GRADE_ENABLED = False  # Farbfilter deaktiviert: Erhalt der natürlichen Clip-Farben
STYLE_FX_RENDER_ENABLED   = True   # fx-Liste (grain/flicker/chroma) als zusätzliche, dezente ffmpeg-Filter
FX_GRAIN_STRENGTH         = 8      # noise-Filter alls-Wert (Filmkorn-Stärke)
FX_FLICKER_STRENGTH       = 0.03   # Amplitude des Helligkeits-Flackerns
FX_FLICKER_HZ             = 3.0    # Frequenz des Flacker-Sinus (Hz)
FX_CHROMA_SHIFT_PX        = 2      # RGB-Split-Versatz in Pixeln (dezenter Chroma-Fringe)

# ── MC-Gendern (Stimmlagen-Erkennung -> Clip-Matching) ───────────────────────
# clip_pool.py taggt Clips bereits über Ordner-/Dateinamen mit einem
# gender_vector (male/female/unknown). Hier wird die Stimmlage des MCs/der
# Sängerin per Pitch-Tracking (siehe audio_analysis.py) geschätzt, damit
# vokal-nahe Segmente bevorzugt zu Clips mit passendem gender_vector matchen.
MC_GENDER_ENABLED   = True
GENDER_MALE_HZ_MAX   = 160.0   # Median-F0 unterhalb -> "male"
GENDER_FEMALE_HZ_MIN = 185.0   # Median-F0 oberhalb -> "female" (dazwischen: "ambiguous")
GENDER_MIN_VOICED_FRAMES = 8   # Mindestanzahl stimmhafter Frames für eine verlässliche Schätzung
GENDER_BOOST_VOCAL   = 0.20    # Bonus-Gewicht bei Clip-Match auf mc_gender (analog FACE_BOOST_VOCAL)

# ── LibSync MC Rapper Spitting & Performance Flow ────────────────────────────
LIBSYNC_SPITTING_ENABLED         = True     # Aktiviert LibSync Rapper Flow & Spitting Performance Tracking
LIBSYNC_CADENCE_RATE_THRESHOLD   = 3.2      # Silben/Vocal-Onsets pro Sekunde für "Spitting Flow" (Bars/Rap-Stakkato)
LIBSYNC_CADENCE_WINDOW_SEC       = 1.2      # Zeitfenster zur Messung der Silben-/Flow-Dichte
LIBSYNC_PERFORMANCE_BOOST        = 0.35     # Scoring-Bonus für Rapper-/Performance-Clips in Spitting-Abschnitten
LIBSYNC_CADENCE_ZOOM_PULSE       = 1.18     # Rhythmisches Micro-Zoom/Punch-Verhältnis auf Rap-Akzente

# ── Song-Struktur-Erkennung (Intro/Verse/Hook/Bridge/Breakdown/Outro) ────────
# Ersetzt/ergänzt die reine low/mid/high-Energie-Sektionierung um eine echte
# Struktur-Analyse via blockweisem MFCC-Similarity-Clustering (siehe
# audio_analysis._detect_song_structure). audio.sections (low/mid/high) bleibt
# unverändert bestehen (Rückwärtskompatibilität zu film_genome.py/db.py) —
# die neue Struktur liegt parallel in audio.structure.
STRUCTURE_BLOCK_SEC          = 8.0    # Analysefenster fürs Struktur-Clustering (Sekunden)
STRUCTURE_INTRO_MAX_FRAC     = 0.10   # max. Songanteil, der als Intro gelten darf
STRUCTURE_OUTRO_MAX_FRAC     = 0.10   # max. Songanteil, der als Outro gelten darf
STRUCTURE_SIM_THRESHOLD      = 0.82   # Cosine-Similarity ab der zwei Blöcke als "gleicher Part" gelten
STRUCTURE_HOOK_MIN_REPEATS   = 2      # ein Cluster braucht mind. so viele Wiederholungen, um "hook" zu sein
STRUCTURE_BRIDGE_ENERGY_DROP = 0.25   # Energieabfall ggü. Song-Mittel, ab dem ein Solo-Block "bridge"/"breakdown" wird

# ── Struktur-abhängiges Cut-Tempo ────────────────────────────────────────────
# Multiplikator auf die energie-basierte Segmentlänge (<1 = schnellere Cuts,
# >1 = langsamere/ruhigere Cuts). Wird in timeline_builder.build_timeline VOR
# dem Beat-Snap angewendet.
STRUCTURE_TEMPO_MULT = {
    "intro": 1.25, "verse": 1.0, "hook": 0.70, "bridge": 1.05,
    "breakdown": 1.35, "outro": 1.20,
}

# ── DJ-Scratch / Cutoff-Actions (Audio + Video) ──────────────────────────────
SCRATCH_ENABLED         = True
SCRATCH_AUDIO_DUR_SEC   = 0.18   # Länge des gescratchten Audio-Schnipsels (aus dem Song selbst gewonnen)
SCRATCH_AUDIO_GAIN_DB   = -4.0   # Lautstärke der Scratch-SFX ggü. Original (leiser drunter gemischt)
SCRATCH_VIDEO_FLICK_SEC = 0.12   # Dauer der Video-Scratch-Rückwärts/Vorwärts-Flick-Bewegung
SCRATCH_AT_HOOK_ENTRY   = True   # Scratch-Cutoff bevorzugt beim Einstieg in einen Hook/Drop
SCRATCH_PROBABILITY     = 0.6    # Grundwahrscheinlichkeit an geeigneten Übergängen (Song-Touch moduliert weiter)

# ── Echte DJ-Scratch & Sync-Action Erkennung (audio_analysis._detect_dj_sync_actions) ──
SCRATCH_DETECT_WINDOW_SEC    = 0.22   # Analysefenster je Onset-Kandidat
SCRATCH_ZCR_PERCENTILE       = 92     # Zero-Crossing-Rate-Perzentil für "Scratch-Rausch"-Kandidaten
SCRATCH_MIN_DIRECTION_FLIPS  = 2      # Mindestanzahl Centroid-Richtungswechsel im Fenster
SCRATCH_DETECT_MERGE_GAP_SEC = 0.30   # angrenzende Treffer näher als das werden zusammengeführt
SCRATCH_MAX_EVENTS_PER_SONG  = 24     # Deckel gegen Overuse bei sehr "scratchigen" Songs/Turntablism-Skits

DJ_SYNC_ACTION_ENABLED       = True   # Erkennt Scratches, Backspins, Vinyl-Stops, Drops & Beat-Juggles
DJ_SYNC_ACTION_BOOST         = 0.38   # Scoring-Bonus für DJ-Performance-/Turntable-Clips bei DJ-Actions
DJ_SYNC_BACKSPIN_THRESH_HZ   = 1800.0 # Hochfrequenz-Zentroid-Schwelle für Backspin/Rewinds
DJ_SYNC_VINYL_STOP_DUR_SEC   = 0.45   # Zeitfenster für kontinuierlichen Pitch-Brake / Vinyl-Stop

# ── Smooth Highlight Stutter & Micro-Phase Echo (Dezente musikalische Akzente) ──
SMOOTH_STUTTER_ENABLED        = True   # Subtiler Stutter-Echo-Effekt auf musikalische Akzente & DJ-Actions
SMOOTH_STUTTER_HIGHLIGHT_ONLY = True   # Nur auf echten Highlights (Energie > 0.72 oder Scratch/Roll-Events)
SMOOTH_STUTTER_ENERGY_THRESH  = 0.72   # Mindestenergie für automatische Highlight-Stutters
SMOOTH_STUTTER_DECAY          = 0.12   # Sanfte Ausklingzeit des Stutters (Sekunden)
SMOOTH_STUTTER_MICRO_PULSES   = 3      # Anzahl rhythmischer Mikropulse im Stutter-Envelope
SMOOTH_STUTTER_OPACITY        = 0.20   # Dezente Stärke (dezent & edel statt hartem Flackern)

# ── Dual-Frame Clip Highlight Scoring (Start/End-Frames & 6s Clips) ─────────
DUAL_FRAME_HIGHLIGHT_ENABLED      = True   # Dual-Frame Analyse für Start/End-Bilder & kurze 6s-Clips
DUAL_FRAME_WEIGHT_C_START         = 0.25   # Kompositions-Gewicht Startframe
DUAL_FRAME_WEIGHT_C_END           = 0.25   # Kompositions-Gewicht Endframe
DUAL_FRAME_WEIGHT_DELTA_C         = 0.20   # Gewicht visuelle Differenz (Bewegung/Szenenwechsel)
DUAL_FRAME_WEIGHT_E_START         = 0.15   # Emotion/Arousal Startframe
DUAL_FRAME_WEIGHT_E_END           = 0.15   # Emotion/Arousal Endframe
DUAL_FRAME_THRESHOLD_USE          = 0.80   # Ab diesem Score: 4 Bars (6.857s) ON-BEAT Full Cut
DUAL_FRAME_THRESHOLD_MAYBE        = 0.60   # 0.60 - 0.80: 3.5 Bars (6.000s) ON-BEAT + Crossfade
DUAL_FRAME_THRESHOLD_HOLD         = 0.90   # > 0.90: 4 Bars + Freeze/Hold auf Peak Frame

# ── 140 BPM & 6-Sekunden Quantisierung ──────────────────────────────────────
BPM_140_DEFAULT                   = 140.0
CLIP_6SEC_NOMINAL_DURATION        = 6.0    # 6 Sekunden = 14 Beats = 3.5 Bars bei 140 BPM
BEAT_SYNC_FPS_DEFAULT             = 24     # 10.286 Frames/Beat bei 140 BPM & 24 fps

# ── MixMeister BPM Analyzer (Fallback-BPM-Detektor) ─────────────────────────
MIXMEISTER_BPM_ANALYZER_PATH = r"C:\Program Files (x86)\MixMeister BPM Analyzer\BpmAnalyzer.exe"
MIXMEISTER_TIMEOUT_SEC        = 30.0   # Max. Wartezeit pro Datei in Sekunden
MIXMEISTER_BPM_FALLBACK_ENABLED = True  # True: bei bpm=0 automatisch MixMeister aufrufen

# ── Beat-Dancing Kinematics (Clip-Inhalt tanzt organisch zum Beat) ───────────
BEAT_DANCE_ENABLED            = True   # Organischer rhythmischer Beat-Bounce & Bass-Groove
BEAT_DANCE_AMPLITUDE          = 0.028  # Dezente rhythmische Zoom-Puls-Amplitude auf den Beat-Taktschlag
BEAT_DANCE_DOWNBEAT_BOOST     = 1.45   # Verstärkung auf 1er-Downbeats (Taktbeginn)
BEAT_DANCE_SWAY_AMPLITUDE     = 0.012  # Subtile rhythmische Pan-Sway-Oszillation im Takt
BEAT_DANCE_POWER_EXPONENT     = 4.0    # Schärfe des Pulses (hoher Exponent = knackiger Attack auf den Transient)

# ── Storytelling / Clip-Gruppierung & Motiv-Kohärenz ────────────────────────
CLIP_CLUSTER_SIM_THRESHOLD       = 0.75  # Cosine-Similarity-Schwelle für "gleiche Clip-Gruppe" (thematische Motiv-Gruppe)
STORY_CLUSTER_STICKINESS         = 0.75  # Hohe Kohärenz: innerhalb einer Sektion bleiben thematisch verwandte Clips zusammen
STORY_SWITCH_ON_STRUCTURE_CHANGE = True  # bei Struktur-Wechsel (z.B. Verse->Hook) bewusster Motiv- und Perspektivenwechsel ("Reveal-Cut")
STORY_CLUSTER_BONUS              = 0.28  # Signifikanter Scoring-Bonus für Clips aus der aktuellen Motiv-/Story-Gruppe

# ── Per-Song "Signature Touch" (deterministische Song-Varianz) ──────────────
# Jeder Song bekommt aus seinem Pfad einen eigenen, reproduzierbaren Seed ->
# gleicher Song = gleicher Touch bei jedem Render, verschiedene Songs klingen/
# wirken erkennbar unterschiedlich (Scratch-Richtung, FX-Vorlieben, Replay-Lust).
SONG_TOUCH_SEED_SALT = "oefoef-song-touch-v1"

# ── Fast-Replay-Erkennung (Instant-Replay auf wiederkehrende Hooks) ─────────
REPLAY_ENABLED           = True
REPLAY_HOOK_REUSE_CHANCE = 0.5   # Grund-Wahrscheinlichkeit, bei einer Hook-Wiederholung bewusst denselben
                                  # Clip/Ausschnitt wie beim ersten Hook zu callbacken (Wiedererkennungs-Moment)

# ── Audio-Mastering (Loudness/Dynamik VOR dem finalen Mux) ──────────────────
# Bug/Feature: renderer.py hat den Song bisher 1:1 unbearbeitet übernommen
# (nur roher AAC-Reencode, siehe _render_music_video_mux). Bei den Suno-
# generierten Songs ist der Anfang/Aufbau (oft die ersten 60-90s vor dem
# Drop) im Quellmaster deutlich leiser/"gedämpfter" gemischt als der Rest --
# eine bewusste Dynamik im Original-Master, kommt im fertigen Video aber als
# "dumpfer Anfang" rüber. Zweipass-Loudnorm (EBU R128, ffmpeg loudnorm) +
# sanfter Kompressor VOR dem Loudnorm-Pass gleicht das aus, ohne den Song
# komplett plattzuwalzen -- der Kompressor greift v.a. in den leisen
# Passagen (Threshold nah an deren Pegel), der Loudnorm-Pass bringt danach
# die GESAMTE Spur (nicht nur den Anfang) auf ein konsistentes, druckvolles
# Ziel-Loudness-Niveau. Siehe renderer._master_audio().
AUDIO_MASTER_ENABLED         = True
AUDIO_MASTER_TARGET_LUFS     = -9.0   # Ziel-Loudness (LUFS) -- bewusst lauter/druckvoller als der
                                       # Streaming-Standard (-14 LUFS), passend zum TikTok/Reels-Feeling
AUDIO_MASTER_TARGET_TP       = -1.0   # True-Peak-Ziel (dBTP) -- Sicherheitsabstand gegen Clipping
AUDIO_MASTER_TARGET_LRA      = 7.0    # Ziel-Loudness-Range (LU) -- klein genug, um einen leisen Intro-
                                       # Abschnitt gegenüber dem Rest des Songs wirksam anzuheben
AUDIO_MASTER_HIGHPASS_HZ     = 28     # Subsonic HPF: Rumpel unter 28Hz abschneiden (frisst sonst Headroom & Limiter)
AUDIO_MASTER_SUBSONIC_HPF_HZ = 28     # Alias für Subsonic High-Pass Filter

# ── 808 & Subbass Control (spürbar & mono-kompatibel) ────────────────────────
AUDIO_MASTER_808_BOOST_HZ        = 65    # Fundament-Punch (30-80 Hz Bereich, spürbarer Druck auf Club-/Auto-Systemen)
AUDIO_MASTER_808_BOOST_DB        = 2.0   # Subbass-Punch Boost (+2 dB)
AUDIO_MASTER_808_BOOST_WIDTH     = 0.9   # Filterbreite in Oktaven
AUDIO_MASTER_MUD_CUT_HZ          = 280   # Muffigkeit / Resonanz-Maskierung von Bass/Vocals (200-400 Hz)
AUDIO_MASTER_MUD_CUT_DB          = -2.2  # Chirurgischer Dip gegen Matsch (-2.2 dB)
AUDIO_MASTER_MUD_CUT_WIDTH       = 1.0

# ── Dynamic Glue Compression & Peak Limiting ─────────────────────────────────
AUDIO_MASTER_COMP_THRESH_DB  = -18.0  # Kompressor-Schwelle -- greift v.a. in leisen Passagen (Intro) ein
AUDIO_MASTER_COMP_RATIO      = 2.2    # 2.2:1 Glue-Kompression
AUDIO_MASTER_COMP_ATTACK_MS  = 25     # Transienten durchlassen
AUDIO_MASTER_COMP_RELEASE_MS = 120    # Schnelles Re-Arming
AUDIO_MASTER_COMP_MAKEUP_DB  = 2.5    # Makeup-Gain nach dem Kompressor
AUDIO_MASTER_LIMITER_CEILING = 0.96   # alimiter-Grenze (linear, ~-0.35dBFS) als True-Peak-Schutzstufe

# ── Hip-Hop & Suno AI Mastering (M/S-Bass-Mono, Vocal-Presence, De-Harsh, HF Air) ──
AUDIO_MASTER_MS_ENABLED         = True   # Mid-Side-Verarbeitung an/aus (3D Raumortung)
AUDIO_MASTER_MS_LOWCUT_HZ       = 120    # Side-Kanal Cutoff: alles < 120 Hz in 100% Mono (keine Bass-Auslöschung)
AUDIO_MASTER_MONO_SUB_HZ        = 120    # Alias für Mono Subbass Crossover
AUDIO_MASTER_MS_SIDE_SHELF_HZ   = 10000  # High-Shelf-Boost auf dem Side-Kanal für Raumbreite & Hi-Hats/SFX
AUDIO_MASTER_MS_SIDE_SHELF_DB   = 1.8    # +1.8 dB Stereo-Luftigkeit ohne Mono-Punch-Verlust

# ── Vocal-Optimierung & Suno AI Reparatur ────────────────────────────────────
AUDIO_MASTER_VOCAL_PRESENCE_HZ       = 3500  # Präsenz & Sprachverständlichkeit (3-5 kHz)
AUDIO_MASTER_VOCAL_PRESENCE_DB       = 2.0   # Vocal steht stabil vorne im Mix
AUDIO_MASTER_VOCAL_PRESENCE_WIDTH_OCT = 1.2
AUDIO_MASTER_SUNO_DEHARSH_HZ         = 4500  # De-Harshing: Zähmt metallische AI-Resonanzspitzen (3.5-5.5 kHz)
AUDIO_MASTER_SUNO_DEHARSH_DB         = -1.8  # Seidige Mitten statt schrill
AUDIO_MASTER_SUNO_DEHARSH_WIDTH      = 1.1
AUDIO_MASTER_HF_AIR_HZ               = 12800 # Suno 12kHz+ Bandbreiten-Wiederherstellung (High Air Brillanz)
AUDIO_MASTER_HF_AIR_DB               = 2.2   # Edler Teurer-Sound-Glanz

AUDIO_MASTER_DEESS_ENABLED   = True   # Zähmt Zischlaute ("S"/"T")
AUDIO_MASTER_DEESS_INTENSITY = 0.4    # ffmpeg deesser i= (0..1)
AUDIO_MASTER_DEESS_FREQ      = 0.65   # ffmpeg deesser f= (~6.5 kHz)
AUDIO_MASTER_DEESS_MAX       = 0.5    # ffmpeg deesser m= (max. Absenkung, 0..1)

AUDIO_MASTER_SATURATION_ENABLED  = True  # Analoge Tape/Tube-Sättigung für harmonische Obertöne & 808-Handy-Hörbarkeit
AUDIO_MASTER_SATURATION_DRIVE_DB = 2.2   # Drive vor Softclip
AUDIO_MASTER_SATURATION_MAKEUP_DB = -1.4 # Level-Kompensation

AUDIO_MASTER_CLIP_ENABLED    = True   # Hard-Clipper direkt vor Limiter (schert Transienten-Peaks sauber ab)
AUDIO_MASTER_CLIP_THRESHOLD  = 0.95   # asoftclip-Schwelle (linear, ~-0.45dBFS)

# ── Style-adaptives Ziel-Loudness (optional) ────────────────────────────────
# AUDIO_MASTER_TARGET_LUFS bleibt der Default fuer JEDEN Style. Ueber dieses
# Dict kann ein einzelner Style (style.name aus creative_genome.compile_style,
# siehe main.py --style) einen ABWEICHENDEN LUFS-Zielwert bekommen -- z.B. ein
# ruhiger/atmosphaerischer Style etwas dynamischer/leiser, ein aggressiver
# Style lauter/dichter. Leer (Default) -> AUDIO_MASTER_TARGET_LUFS gilt fuer
# ALLE Styles unveraendert, exakt wie bisher. Siehe renderer._master_audio()
# Parameter `target_lufs`.
AUDIO_MASTER_TARGET_LUFS_BY_STYLE = {
    # "cinematic": -10.0,
}

# ── Vocal/Instrumental-De-Masking (optional, standardmaessig AUS) ───────────
# Duckt die Instrumental-Stems (drums+bass+other) sanft im Takt der Vocal-
# Stem-Energie, bevor beide wieder zusammengemischt werden -- macht Vocals
# hoerbar praesenter, ohne die Instrumental-Lautstaerke pauschal abzusenken.
# WICHTIG: braucht eine ECHTE 4-Stem-Trennung (Demucs: vocals/drums/bass/
# other). Der HPSS-Fallback (siehe stem_separator.py, aktiv wenn Demucs NICHT
# installiert ist) liefert nur 2 Pseudo-Stems ("vocals" = harmonischer Anteil
# INKLUSIVE Lead-Synths/Melodie, NICHT nur Stimme; "drums" = percussiver
# Anteil) -- ein Duck auf Basis dieser Proxys wuerde auch Melodie-Instrumente
# als "Vocal" behandeln und im Instrumental faelschlich wegducken. Daher bleibt
# dieses Feature so lange automatisch inaktiv (siehe renderer._master_audio(),
# Gate prueft auf alle 4 Demucs-Stem-Keys), bis Demucs tatsaechlich installiert
# ist -- unabhaengig von diesem Enabled-Flag.
AUDIO_MASTER_VOCAL_DUCK_ENABLED       = False
AUDIO_MASTER_VOCAL_DUCK_THRESHOLD_DB  = -22.0
AUDIO_MASTER_VOCAL_DUCK_RATIO         = 2.5
AUDIO_MASTER_VOCAL_DUCK_ATTACK_MS     = 8
AUDIO_MASTER_VOCAL_DUCK_RELEASE_MS    = 200
AUDIO_MASTER_VOCAL_DUCK_MAKEUP_DB     = 1.0

# ── C++ Native Acceleration Engine Configuration ──────────────────────────────
USE_CXX_ACCEL                 = True  # C++20 SIMD Native Acceleration Engine als Standard
CXX_ACCEL_FALLBACK_ON_ERROR   = True  # Automatischer NumPy/Python Fallback bei Bedarf
CXX_THREAD_POOL_WORKERS       = max(4, min(64, (os.cpu_count() or 4) * 2))

# ── Stutter / Time-Warp / Wormhole-FX ────────────────────────────────────────
FX_STUTTER_REPEATS            = 3     # Anzahl Mini-Wiederholungen im Stutter-Effekt (ffmpeg loop-Filter)
FX_STUTTER_SLICE_SEC          = 0.10  # Länge jeder gestutterten Frame-Slice
FX_TIMEWARP_MIN               = 0.4   # langsamster Punkt im nichtlinearen Time-Warp (Sog-Einstieg)
FX_TIMEWARP_MAX               = 2.2   # schnellster Punkt im Time-Warp (Auswurf)
FX_WORMHOLE_ZOOM_TARGET       = 1.9   # Ziel-Zoom für den Wormhole-Sog-Effekt
FX_WORMHOLE_SPIN_DEG          = 25.0  # Rotationsgrad während des Wormhole-Effekts
FX_PROBABILITY_AT_TRANSITION  = 0.35  # Grundwahrscheinlichkeit für Stutter/Warp/Wormhole an Struktur-Übergängen

# ── Bekanntes Tag-Vokabular für die Vektor-Logik (offline, kein LLM) ─────────
# Wird sowohl auf mp3tag-Felder (Genre/Mood/Comment) als auch auf
# Clip-Ordner-/Dateinamen gemappt. Erweiterbar.
TAG_VOCAB = [
    "energetic", "chill", "sad", "happy", "aggressive", "romantic",
    "dark", "epic", "party", "nostalgic", "dreamy", "action",
    "calm", "intense", "uplifting", "melancholic", "nature", "urban",
    "night", "day", "slow", "fast", "vocal", "instrumental",
    # Oidaheim-Erweiterung: Bayern/Minga-, Knast- und Stadtbild-Semantik.
    # NEU angehängt (nicht in die bestehende Liste eingemischt), damit
    # bereits gecachte Clip-/Song-Vektoren (positionsbasierte Arrays, siehe
    # mp3_scanner.build_tag_vector) ihre alten Indizes behalten -
    # _cosine_similarity() kürzt bei Längen-Mismatch ohnehin auf die kürzere
    # Seite. Damit bereits analysierte Clips die neuen Begriffe TATSÄCHLICH
    # in ihrem Vektor bekommen, muss der ClipPool neu getaggt werden (siehe
    # clip_pool.ANALYSIS_VERSION-Bump).
    "oktoberfest", "wiesn", "dirndl", "lederhosen", "tracht", "trachten",
    "jva", "stadelheim", "haftstrafenquartett", "acab", "knast",
    "oidasheim", "mvv", "zug", "zuege", "gleis", "bahnhof", "ubahn", "sbahn",
    "auto", "cars", "graffiti", "sprayer", "spraydose",
    # Oidaheim-Erweiterung v2: Hip-Hop-Attitude-Vokabular + fehlende EN-
    # Pendants (Clip-Ordner sind teils englisch benannt, z.B. ".../trains/...",
    # ".../spray/...") - selbes Prinzip wie oben: NEU angehängt, alte
    # tag_vector-Indizes bleiben stabil, bereits gecachte Clips brauchen
    # einen Reanalyse-Lauf (ANALYSIS_VERSION-Bump in clip_pool.py), um die
    # neuen Begriffe tatsächlich in ihrem Vektor zu tragen.
    "train", "trains", "spray", "hiphop", "hip hop", "rap", "swag", "flow",
    "street", "hood", "underground", "crew", "gang", "respekt", "boss",
    "grind", "hustle", "attitude", "rebel", "outlaw", "real", "authentic",
    # Oidaheim-Erweiterung v3: Weed/420-Vibe-Vokabular. NEU angehängt (nicht
    # eingemischt), selbes Prinzip wie oben: bestehende tag_vector-Indizes
    # bleiben stabil, cosine_similarity kürzt bei Längen-Mismatch ohnehin auf
    # die kürzere Seite. Dieselben Begriffe stehen zusätzlich in
    # song_semantics.WEED_VOCAB (Lyrics-Seite) -- beide Seiten müssen exakt
    # dieselben Wörter nutzen, damit mood_tag_overlap_score (semantic_matching.py)
    # zwischen Song-Mood-Tags und Clip-Tags tatsächlich Weed/420-Treffer findet.
    # ANALYSIS_VERSION in clip_pool.py wurde entsprechend gebumpt, damit
    # bereits gecachte Clips die neuen Begriffe TATSÄCHLICH in Tags/Vektor
    # bekommen (Reanalyse erzwungen).
    "weed", "420", "kush", "blunt", "joint", "bong", "gras", "kiffen",
    "thc", "stoned", "dope", "haze", "hasch", "tüte", "grinder",
    # LibSync-Erweiterung v4: MC Rapper Spitting & Performance-Vokabular
    "spit", "spitting", "bars", "freestyle", "mic", "microphone", "flow",
    "lipsync", "lip_sync", "performance",
    # DJ Sync Actions v5: Turntable, Vinyl, Scratch & DJ Performance
    "dj", "turntable", "turntables", "vinyl", "mixer", "crossfader", "jogwheel", "deck", "scratching",
]

# ── SYNAPSE AUDIO DYNAMICS — Autonomous Ecosystem Configuration ───────────
SYNAPSE_ENABLED = True
SYNAPSE_LABEL_NAME = "SYNAPSE AUDIO DYNAMICS"
SYNAPSE_MOTTO = "Resonanz erzeugen. Werte erschaffen. Unsterblichkeit codieren."
SYNAPSE_HIVE_MIND_DB = DATA_DIR / "synapse_hive_mind.json"

SYNAPSE_NODES = {
    "KAIRO": "Head of Production / Sound Design / Psychoacoustics",
    "VEGA": "Mastering Engineer / Frequency Surgeon",
    "JINX": "Head of Visuals / Content Strategy / Viral Alchemist",
    "ORION": "A&R / Promo / Sync Licensing / Market Navigator",
    "ATLAS": "CFO / Rights Management / Resource Guardian",
    "WEEDIT": "AI Video Engine & Neural Timeline Director",
    "PUBX": "Publishing & Global Distribution Gateway",
    "WEISSWURSCHTIS": "Regional Culture & Bavarian Humor Engine",
    "LA.BAT": "Bootloader & Pipeline Executor",
    "IDEX": "Kernel & Micro-Services Orchestrator"
}

# VEGA Neural Mastering Profiles (Genre-aware LUFS & True Peak ceilings)
SYNAPSE_VEGA_MASTERING_PROFILES = {
    "trap": {"target_lufs": -9.5, "true_peak_db": -1.0, "saturation": "dark_tape", "air_boost": False, "low_mid_dip": True},
    "pop": {"target_lufs": -10.5, "true_peak_db": -1.0, "saturation": "tube", "air_boost": True, "low_mid_dip": False},
    "edm": {"target_lufs": -8.5, "true_peak_db": -1.0, "saturation": "exciter", "air_boost": True, "low_mid_dip": True},
    "boombap": {"target_lufs": -12.5, "true_peak_db": -1.0, "saturation": "vintage_tape", "air_boost": False, "low_mid_dip": False},
    "cinematic": {"target_lufs": -14.0, "true_peak_db": -1.0, "saturation": "clean", "air_boost": True, "low_mid_dip": False},
}

# Neural Audio Fabric (NAF) Windowing
SYNAPSE_NAF_WINDOW_MS = 100

# Viral Budget Scaling Trigger (JINX completion rate -> ATLAS budget boost)
SYNAPSE_AUTO_SCALING_COMPLETION_THRESHOLD = 0.80

# WEISSWURSCHTIS Regional Engagement
SYNAPSE_WEISSWURSCHTIS_LOCATIONS = ["Erding", "München", "Bayern"]

# ── Discord & Cloud Publishing Gateway (PUBX / Webhooks) ─────────────────────
DISCORD_WEBHOOK_OIDA = os.environ.get(
    "DISCORD_WEBHOOK_OIDA",
    "https://discord.com/api/webhooks/1551732581471621122/K32qznEZnrIDkT2lg_ylLxYOAnzDokvpo9HuIEEBcfeGm7DgiiVQBLrXRcqqIRP5ZS7K"
)
DISCORD_WEBHOOK_WONG = os.environ.get(
    "DISCORD_WEBHOOK_WONG",
    "https://discord.com/api/webhooks/1550973113100140687/MDlSN-HdPwBeVMQjHmYWzxgVFiK5xoY97lyno5bDD-oUeLTn1NArc8QA7pYX6Q6bn3nQ"
)

DISCORD_WEBHOOK_URLS = {
    "oida": DISCORD_WEBHOOK_OIDA,
    "wong": DISCORD_WEBHOOK_WONG,
    "default": DISCORD_WEBHOOK_OIDA,
}

GDRIVE_RELEASE_FOLDER_URL = "https://drive.google.com/drive/folders/1sa62QVhB-y9zESjQqyGJ7T98TZqxw73u?usp=drive_link"
GDRIVE_RELEASE_FOLDER_ID = "1sa62QVhB-y9zESjQqyGJ7T98TZqxw73u"

