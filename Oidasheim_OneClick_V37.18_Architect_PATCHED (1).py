# -*- coding: utf-8 -*-
r"""
Oidasheim_OneClick_V37.17_Architect.py
1-Click: MP3 + Clips -> Epic Music Video (9:16 Vertical Master)

CHANGELOG V37.17:
  - NEU: Full-Duration-Sicherheitsnetz (schließt Rundungslücken am Songende)
  - NEU: ClipHistory - session-übergreifende Wiederholsperre (SQLite-Cooldown)
  - NEU: LibrarySync - gleicht clips.db mit Dateisystem ab
  - NEU: Gender-Timeline direkt aus [Male MC]/[Female MC]-Lyrics-Markern
  - NEU: Multi-Tempo-BPM-Timeline (Beat-Switch-Songs, z.B. 140->187->70->140)
  - NEU: Zonen-Rotation (first/mid/last Clip-Drittel, kreativ statt zufällig)
  - NEU: Akzent-/Near-Repeat-Erkennung (Onset-Analyse) -> Glitch/Jump/Morph/Speedramp
  - NEU: Freeze-Frame am Segmentende + echte xfade-Übergänge statt hartem concat
  - NEU: Hip-Hop/Oida-native Semantik-Lexikon + Source-Priority-Scoring
  - GEERBT (V37.16): SQL-Fix learned_lexicon, DataLayer self.conn Init
"""

import os, sys, subprocess, sqlite3, json, random, re, glob, math, shutil, functools, stat
from pathlib import Path
from collections import deque, Counter
from datetime import datetime
import numpy as np
import librosa
from bs4 import BeautifulSoup
from tinytag import TinyTag

# ── ULTRA-FRÜHER NumPy-Downgrade-Check ──
try:
    import numpy as _np
    from packaging import version
    if version.parse(_np.__version__) >= version.parse("2.5"):
        print("⚠️ NumPy > 2.5 erkannt. Downgrade auf 2.2.3...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--force-reinstall", "numpy==2.2.3"])
        print("✅ NumPy korrigiert. Bitte starte das Skript neu.")
        sys.exit(0)
except Exception: pass

try:
    from PIL import Image
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_OK = True
except Exception:
    _SEMANTIC_OK = False

_SEMANTIC_MODEL = None
if _SEMANTIC_OK:
    try:
        _SEMANTIC_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _SEMANTIC_OK = False

try:
    from rembg import remove, new_session
    _ROTO_OK = True
    _ROTO_SESS = new_session()
except Exception:
    _ROTO_OK = False

import oidasheim_config as CFG

# ═══════════════════════════════════════════════════════════════════
#  VERTICAL SETTINGS (9:16) & GLOBALS
# ═══════════════════════════════════════════════════════════════════
TARGET_W = 720
TARGET_H = 1280
TARGET_AR = TARGET_W / TARGET_H
AR_MISMATCH_TOLERANCE = getattr(CFG, "AR_MISMATCH_TOLERANCE", 0.15)
DEFAULT_CLIP_DB = getattr(CFG, "DEFAULT_CLIP_DB", "clips.db")
CLIP_ROOT = getattr(CFG, "CLIP_ROOT", r"J:\raw_vidz")  # NEU: für LibrarySync -> ggf. anpassen
REFERENCE_BPM = 140.0  # Clip-Bibliothek ist überwiegend auf dieses Tempo optimiert
FREEZE_S = 0.12        # ~3 Frames @ 24fps -> Hauptobjekt friert kurz ein

CULTURE_LEXICON_HIPHOP = getattr(CFG, "CULTURE_LEXICON_HIPHOP", {
    "gender_f": ["she", "her", "sie", "girl", "queen", "mädchen"],
    "gender_m": ["he", "him", "er", "boy", "king", "junge", "bruder", "oida"],
    "oida_native": ["oida", "digga", "bruder", "hood", "street-cred", "block"],
    "bavarian":    ["weißwurst", "königsplatz", "minga", "089", "u-bahn"],
    "sfx_marker":  ["sfx", "glitch", "collapse", "shake it", "break it"],
    "adlib":       ["yeah", "yup", "uh", "woo", "skrrt", "oida"],
})

VIBE_PROFILES = {
    "dark_cinematic": {"label": "🌑 Dark Cinematic", "eq": "eq=contrast=1.10:brightness=-0.04:saturation=0.85:gamma=0.95", "rotation_max": 0.8},
    "neon_energy": {"label": "💜 Neon Energy", "eq": "eq=contrast=1.14:brightness=0.02:saturation=1.35:gamma=1.05", "rotation_max": 1.5},
}

TRANSITION_MAP = {
    "glitch": ["pixelize", "hblur", "distance"],
    "jump":   ["hardcut"],
    "morph":  ["dissolve", "smoothleft", "smoothright"],
    "fade":   ["fade", "fadeblack"],
}

BANNER = r"""
██████╗ ██╗██████╗  █████╗ ██╗██████╗  █████╗ 
██╔══██╗██║██╔══██╗██╔══██╗██║██╔══██╗██╔══██╗
██║  ██║██║██████╔╝███████║██║██║  ██║███████║
██║  ██║██║██╔══██╗██╔══██║██║██║  ██║██╔══██║
██████╔╝██║██║  ██║██║  ██║██║██████╔╝██║  ██║
╚═════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝
  V37.17 SEMANTIC/TEMPO-TIMELINE | GENDER-AWARE | FULL DURATION
"""

# ═══════════════════════════════════════════════════════════════════
#  INTEGRITY & UTILS
# ═══════════════════════════════════════════════════════════════════

def is_clip_healthy(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return res.returncode == 0 and "," in res.stdout
    except Exception: return False

@functools.lru_cache(maxsize=4096)
def probe_duration(src: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", src], capture_output=True, text=True, timeout=10)
        return float(out.stdout.strip())
    except Exception: return 10.0

def needs_letterbox(width, height, tol=AR_MISMATCH_TOLERANCE):
    if not width or not height: return False
    return abs((width / height) - TARGET_AR) / TARGET_AR > tol

# ═══════════════════════════════════════════════════════════════════
#  NEU: LYRICS-/TAG-PARSER (Gender-Timeline, Multi-Tempo, SFX)
# ═══════════════════════════════════════════════════════════════════

SFX_MARKER_RE = re.compile(r'\(SFX:\s*([^)]+)\)', re.IGNORECASE)
SECTION_MARKER_RE = re.compile(r'\[([A-Z][A-Z0-9 :._\-]+)\]')
SECTION_TIME_RE = re.compile(r'\[([^|\]]+?)(?:\s*\|\s*(\d+:\d{2})\s*[–-]\s*(\d+:\d{2}))?(?:\s*\|\s*([^\]]+))?\]')
GENDER_TAG_RE = re.compile(r'(Male|Female)\s+(MC|Voice|Vocals)', re.IGNORECASE)
HALFTIME_BPM_RE = re.compile(r'(\d{2,3})\s*BPM', re.IGNORECASE)
MULTI_BPM_RE = re.compile(r'(\d{2,3})\s*BPM\s*(?:Start|Beat-Switch|Breakdown|Comeback|→)?', re.IGNORECASE)
SECTION_HEADER_TIME_RE = re.compile(r'\[(?:INTRO|VERSE|CHORUS|BRIDGE|OUTRO)[^\]]*?(\d+):(\d{2})[–-](\d+):(\d{2})[^\]]*\]', re.IGNORECASE)

def extract_sfx_cues(lyrics: str):
    return {"sfx_cues": SFX_MARKER_RE.findall(lyrics or ""), "sections": SECTION_MARKER_RE.findall(lyrics or "")}

def parse_gender_timeline(lyrics: str):
    """Baut eine Zeit->Gender-Zuordnung direkt aus Lyrics-Sektionsmarkern wie [Female MC | 0:37-0:58]."""
    timeline = []
    for match in SECTION_TIME_RE.finditer(lyrics or ""):
        header, t_start, t_end, _ = match.groups()
        gender_match = GENDER_TAG_RE.search(header)
        if not gender_match or not t_start or not t_end:
            continue
        gender = "f" if gender_match.group(1).lower() == "female" else "m"
        s = int(t_start.split(":")[0]) * 60 + int(t_start.split(":")[1])
        e = int(t_end.split(":")[0]) * 60 + int(t_end.split(":")[1])
        timeline.append((s, e, gender))
    return timeline

def gender_at(timeline, t_s: float) -> str:
    for start, end, gender in timeline:
        if start <= t_s < end:
            return gender
    return "neutral"

def resolve_effective_bpm(bpm_tag: float, text_blob: str) -> float:
    """Half-Time-Trap-Fix: wenn Text eine ~doppelte BPM nennt, diese bevorzugen."""
    if not text_blob or not bpm_tag:
        return bpm_tag
    match = HALFTIME_BPM_RE.search(text_blob)
    if not match:
        return bpm_tag
    text_bpm = float(match.group(1))
    if abs(text_bpm - bpm_tag * 2) < 5:
        return text_bpm
    return bpm_tag

def parse_tempo_timeline(text_blob: str, lyrics: str, fallback_bpm: float):
    """Multi-Tempo-Songs (Beat-Switches) -> Liste von (start_s, end_s, bpm)."""
    bpm_values = [float(x) for x in MULTI_BPM_RE.findall(text_blob or "")]
    if len(bpm_values) <= 1:
        return [(0.0, float("inf"), fallback_bpm)]
    sections = SECTION_HEADER_TIME_RE.findall(lyrics or "")
    timeline = []
    for i, (m1, s1, m2, s2) in enumerate(sections):
        start_s = int(m1) * 60 + int(s1)
        end_s = int(m2) * 60 + int(s2)
        bpm = bpm_values[min(i, len(bpm_values) - 1)]
        timeline.append((start_s, end_s, bpm))
    return timeline or [(0.0, float("inf"), fallback_bpm)]

def bpm_at(timeline, t_s: float, fallback: float) -> float:
    for start, end, bpm in timeline:
        if start <= t_s < end:
            return bpm
    return fallback

def classify_accent(onset_times, window_start_s, window_end_s):
    """'none' / 'hit' / 'burst' / 'near_repeat' (gleichmäßige schnelle Wiederholungen: PANG-PANG-PANG)."""
    hits = [t for t in onset_times if window_start_s <= t < window_end_s]
    if not hits:
        return "none", 0, 0.0
    if len(hits) >= 2:
        gaps = np.diff(sorted(hits))
        gap_std = float(np.std(gaps)) if len(gaps) > 1 else 0.0
        gap_mean = float(np.mean(gaps))
        is_near_repeat = gap_std < (gap_mean * 0.35) and gap_mean < 0.35
    else:
        gap_mean, is_near_repeat = 0.0, False
    if is_near_repeat and len(hits) >= 3:
        return "near_repeat", len(hits), gap_mean
    if len(hits) >= 3:
        return "burst", len(hits), 0.0
    return "hit", len(hits), 0.0

def _source_prio(path_str: str) -> int:
    p = path_str.lower()
    if "favs" in p: return 0
    if "[beatsync]" in p: return 1
    if "oidamo" in p: return 2
    return 3

def _guess_clip_gender(path: str) -> str:
    p = path.lower()
    if any(k in p for k in ["female", "frau", "girl", "queen"]): return "f"
    if any(k in p for k in ["male", "mann", "boy", "king"]): return "m"
    return "neutral"

_HIPHOP_CATEGORY_VECS = {}

def _get_category_vecs():
    global _HIPHOP_CATEGORY_VECS
    if not _HIPHOP_CATEGORY_VECS and _SEMANTIC_OK:
        for cat, words in CULTURE_LEXICON_HIPHOP.items():
            _HIPHOP_CATEGORY_VECS[cat] = _SEMANTIC_MODEL.encode(" ".join(words), normalize_embeddings=True)
    return _HIPHOP_CATEGORY_VECS

# ═══════════════════════════════════════════════════════════════════
#  DIRECTOR CLASSES
# ═══════════════════════════════════════════════════════════════════

class LexiconLearner:
    def __init__(self, db_conn):
        self.conn = db_conn
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.extended_lexicon = CULTURE_LEXICON_HIPHOP

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_lexicon (
                term TEXT PRIMARY KEY, category TEXT, frequency INTEGER,
                first_seen TEXT, last_seen TEXT
            )""")
        self.conn.commit()

    def learn_from_lyrics(self, lyrics):
        if not lyrics: return
        now = datetime.now().isoformat()
        words = re.findall(r'\b[a-zA-ZäöüÄÖÜß]{4,}\b', lyrics.lower())
        for w in set(words):
            if w.capitalize() in lyrics:
                self.conn.execute("""
                    INSERT OR REPLACE INTO learned_lexicon (term, category, frequency, first_seen, last_seen)
                    VALUES (?, ?, COALESCE((SELECT frequency FROM learned_lexicon WHERE term=?),0)+1,
                            COALESCE((SELECT first_seen FROM learned_lexicon WHERE term=?),?), ?)
                """, (w, "names", w, w, now, now))
        self.conn.commit()


class ClipHistory:
    """Persistente, session-übergreifende Wiederholsperre (SQLite-Cooldown)."""
    def __init__(self, db_conn, cooldown_hours=48):
        self.conn = db_conn
        self.cooldown_s = cooldown_hours * 3600
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_usage_log (
                path TEXT PRIMARY KEY, last_used_ts REAL
            )""")
        self.conn.commit()

    def is_blocked(self, path: str) -> bool:
        row = self.conn.execute("SELECT last_used_ts FROM clip_usage_log WHERE path=?", (path,)).fetchone()
        if not row: return False
        return (datetime.now().timestamp() - row["last_used_ts"]) < self.cooldown_s

    def mark_used(self, path: str):
        now = datetime.now().timestamp()
        self.conn.execute("INSERT OR REPLACE INTO clip_usage_log (path, last_used_ts) VALUES (?, ?)", (path, now))
        self.conn.commit()


class LibrarySync:
    """Gleicht clips.db mit dem tatsächlichen Dateisystem ab (neue/verwaiste Clips)."""
    def __init__(self, db_conn, clip_root):
        self.conn = db_conn
        self.conn.row_factory = sqlite3.Row
        self.clip_root = Path(clip_root)

    def sync(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clips (
                path TEXT PRIMARY KEY,
                width INTEGER,
                height INTEGER
            )""")
        cols={r[1] for r in self.conn.execute("PRAGMA table_info(clips)").fetchall()}
        migrations=[
            ("motion_score","ALTER TABLE clips ADD COLUMN motion_score REAL DEFAULT 0.0"),
            ("duration_sec","ALTER TABLE clips ADD COLUMN duration_sec REAL DEFAULT 10.0"),
            ("gender","ALTER TABLE clips ADD COLUMN gender TEXT DEFAULT 'neutral'"),
            ("source_prio","ALTER TABLE clips ADD COLUMN source_prio INTEGER DEFAULT 3"),
        ]
        for c,sql in migrations:
            if c not in cols:
                self.conn.execute(sql)
        self.conn.commit()
        if not self.clip_root.exists():
            print(f"⚠️ Clip-Root nicht gefunden: {self.clip_root} — LibrarySync übersprungen.")
            return
        known = {r["path"] for r in self.conn.execute("SELECT path FROM clips")}
        on_disk = {str(p) for p in self.clip_root.rglob("*.mp4")}

        for p in on_disk - known:
            if not is_clip_healthy(p): continue
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", p]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            try:
                w, h = map(int, res.stdout.strip().split(","))
            except Exception:
                w, h = 1920, 1080
            self.conn.execute(
                "INSERT OR IGNORE INTO clips (path, width, height, motion_score, duration_sec, gender, source_prio) VALUES (?,?,?,?,?,?,?)",
                (p, w, h, 0.0, probe_duration(p), _guess_clip_gender(p), _source_prio(p))
            )
            print(f"➕ Neuer Clip erkannt: {Path(p).name}")

        for p in known - on_disk:
            self.conn.execute("DELETE FROM clips WHERE path=?", (p,))
            print(f"➖ Entfernt (Datei fehlt): {Path(p).name}")

        self.conn.commit()


class OidasheimAnalyzer:
    def analyze(self, path):
        y, sr = librosa.load(path, sr=22050)
        rms = librosa.feature.rms(y=y)[0]
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, backtrack=True)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        return {
            "bpm": float(np.atleast_1d(tempo)[0]) or 120.0,
            "duration_ms": int(len(y)/sr*1000),
            "energy_map": (rms / (np.max(rms)+1e-9)).tolist(),
            "onset_times": onset_times.tolist(),
        }


class VirtualCamera:
    def get_motion_params(self, energy, dur, vibe, bpm):
        frames = max(1, int(dur * 24))
        beat_p = 60.0 / bpm
        sway = (TARGET_W * 0.02) * (0.5 + energy)
        sway_expr = f"{sway:.2f}*sin(2*PI*(on/24/{beat_p:.4f}))"
        rot_expr = f"{math.radians(vibe['rotation_max'] * (0.5+energy)):.4f}*sin(2*PI*n/{frames*2})"
        return {"z": f"1.0+(0.05*on/{frames})", "x": f"iw/2-(iw/zoom/2)+{sway_expr}", "y": "ih/2-(ih/zoom/2)", "rotation": rot_expr}


class ZoneRotator:
    """Kreative Rotation über die Clip-Drittel (first/mid/last)."""
    PATTERNS = [["mid", "first", "last"], ["last", "mid", "first"], ["first", "last", "mid"], ["mid", "last", "first"]]

    def __init__(self):
        self._pattern = random.choice(self.PATTERNS)
        self._idx = 0

    def next_zone(self, energy: float) -> str:
        if energy > 0.75:
            return "mid"  # Meiste Bewegung bei 140bpm-optimierten Clips
        zone = self._pattern[self._idx % len(self._pattern)]
        self._idx += 1
        return zone

# ═══════════════════════════════════════════════════════════════════
#  LAYER 2: OidaIDA (VERTICAL PRIO PICKING)
# ═══════════════════════════════════════════════════════════════════

class OidaIDA:
    def __init__(self, pool, db_conn):
        self.pool = pool
        self.conn = db_conn
        self.analyzer = OidasheimAnalyzer()
        self.cam = VirtualCamera()
        self.lexicon = LexiconLearner(db_conn)
        self.history = ClipHistory(db_conn, cooldown_hours=48)
        self.zone_rotator = ZoneRotator()
        self._lyrics_vec = None
        self._category_weights = {}

    def create_regiebuch(self, job):
        data = self.analyzer.analyze(job["mp3"])
        self.lexicon.learn_from_lyrics(job["lyrics"])

        base_bpm = resolve_effective_bpm(job.get("bpm_tag") or data["bpm"], job.get("genre_tag", ""))
        tempo_timeline = parse_tempo_timeline(job.get("genre_tag", ""), job["lyrics"], base_bpm)
        gender_timeline = parse_gender_timeline(job["lyrics"])

        if _SEMANTIC_OK and job.get("lyrics"):
            self._lyrics_vec = _SEMANTIC_MODEL.encode(job["lyrics"], normalize_embeddings=True)
            cats = _get_category_vecs()
            self._category_weights = {c: float(np.dot(self._lyrics_vec, v)) for c, v in cats.items()} if cats else {}
        else:
            self._lyrics_vec = None
            self._category_weights = {}

        vibe = VIBE_PROFILES["neon_energy"] if base_bpm > 130 else VIBE_PROFILES["dark_cinematic"]
        edl = {"meta": {"title": job["mp3"].stem, "mp3": str(job["mp3"]), "bpm": base_bpm, "vibe": vibe}, "steps": []}
        curr_ms, total_ms = 0, data["duration_ms"]
        recent = deque(maxlen=80)
        onset_times = data["onset_times"]

        while curr_ms < total_ms:
            idx = min(int(curr_ms/total_ms*len(data["energy_map"])), len(data["energy_map"])-1)
            energy = data["energy_map"][idx]
            t_s = curr_ms / 1000.0
            current_bpm = bpm_at(tempo_timeline, t_s, base_bpm)
            tempo_ratio = REFERENCE_BPM / max(current_bpm, 60.0)
            seg_gender = gender_at(gender_timeline, t_s) if gender_timeline else "neutral"

            beat_s = 60.0 / current_bpm
            accent_type, accent_count, gap_mean = classify_accent(onset_times, t_s, t_s + beat_s)

            if curr_ms < 4000:
                bars = 0.5
            elif accent_type == "near_repeat":
                bars = max(1.0, accent_count * (gap_mean / beat_s)) if beat_s > 0 else 1.0
            elif accent_type == "burst":
                bars = 0.25
            elif accent_type == "hit" or energy > 0.85:
                bars = 0.5
            else:
                bars = 4 * tempo_ratio

            dur_ms = int(60000 / current_bpm * bars)
            if curr_ms + dur_ms > total_ms: dur_ms = total_ms - curr_ms
            if dur_ms <= 0: break

            clip = self._pick_vertical_part(dur_ms/1000, energy, recent, seg_gender)
            transition = self._pick_transition(accent_type)

            edl["steps"].append({
                "duration_ms": dur_ms, "clip_path": clip["path"],
                "seek_start": clip["best_seek"], "energy": energy,
                "zone": clip.get("zone", "n/a"), "accent": accent_type,
                "transition": transition, "bpm_used": current_bpm,
                "is_roto": energy > 0.83 and _ROTO_OK,
                "cam": self.cam.get_motion_params(energy, dur_ms/1000, vibe, current_bpm)
            })
            curr_ms += dur_ms

        # NEU: Full-Duration-Sicherheitsnetz gegen Rundungslücken
        covered_ms = sum(s["duration_ms"] for s in edl["steps"])
        if covered_ms < total_ms - 50:
            gap_ms = total_ms - covered_ms
            last_clip = self._pick_vertical_part(gap_ms / 1000, 0.5, recent, "neutral")
            edl["steps"].append({
                "duration_ms": gap_ms, "clip_path": last_clip["path"],
                "seek_start": last_clip["best_seek"], "energy": 0.5,
                "zone": last_clip.get("zone", "n/a"), "accent": "none",
                "transition": "fade", "bpm_used": base_bpm,
                "is_roto": False,
                "cam": self.cam.get_motion_params(0.5, gap_ms/1000, vibe, base_bpm)
            })
        return edl

    def _pick_transition(self, accent_type):
        if accent_type == "near_repeat":
            return "speedramp"
        if accent_type == "burst":
            return random.choice(["glitch", "jump"])
        if accent_type == "hit":
            return random.choice(["glitch", "morph", "jump"])
        return random.choice(["fade", "morph"])

    def _pick_vertical_part(self, needed_s, energy, recent, seg_gender="neutral"):
        pool_slice = [c for c in self.pool if c["path"] not in recent and not self.history.is_blocked(c["path"])]

        if seg_gender in ("f", "m"):
            gender_filtered = [c for c in pool_slice if c.get("gender") in (seg_gender, "neutral")]
            if gender_filtered:
                pool_slice = gender_filtered

        if not pool_slice:
            pool_slice = self.pool

        candidates = random.sample(pool_slice, min(len(pool_slice), 40))
        dominant_cat = max(self._category_weights, key=self._category_weights.get) if self._category_weights else None

        scored = []
        for c in candidates:
            if not is_clip_healthy(c["path"]): continue
            c_ar = c.get("width", 1920) / c.get("height", 1080)
            ar_score = 1.0 - min(1.0, abs(c_ar - TARGET_AR))
            source_bonus = {0: 15, 1: 8, 2: 0, 3: -5}.get(c.get("source_prio", 3), -5)
            cat_bonus = 10 if dominant_cat and dominant_cat in str(c.get("path", "")).lower() else 0
            score = (ar_score * 40) + (c.get("motion_score", 0) * 30 * energy) + source_bonus + cat_bonus
            scored.append((score, c))

        if not scored:
            best_clip = random.choice(self.pool)
        else:
            scored.sort(key=lambda x: x[0], reverse=True)
            best_clip = scored[0][1]

        self.history.mark_used(best_clip["path"])
        t_s = best_clip.get("duration_sec") or probe_duration(best_clip["path"])

        third = t_s / 3.0
        zone_bounds = {
            "first": (0.05, max(0.05, third - needed_s)),
            "mid":   (third, max(third, 2 * third - needed_s)),
            "last":  (2 * third, max(2 * third, t_s - needed_s - 0.2)),
        }
        zone_name = self.zone_rotator.next_zone(energy)
        lo, hi = zone_bounds[zone_name]
        if hi <= lo:
            lo, hi = 0.05, max(0.05, t_s - needed_s - 0.2)
        best_seek = round(random.uniform(lo, hi), 3)

        recent.append(best_clip["path"])
        return {**best_clip, "best_seek": best_seek, "zone": zone_name}

# ═══════════════════════════════════════════════════════════════════
#  LAYER 3: dere (VERTICAL RENDERER)
# ═══════════════════════════════════════════════════════════════════

class DereRenderer:
    def __init__(self, app_root):
        self.temp = app_root / "tmp"
        self.temp.mkdir(parents=True, exist_ok=True)

    def execute(self, edl, out_folder):
        title = edl["meta"]["title"]
        vibe = edl["meta"]["vibe"]
        chunks = [edl["steps"][i:i + 30] for i in range(0, len(edl["steps"]), 30)]
        chunk_files = []

        for c_idx, chunk in enumerate(chunks):
            chunk_out = self.temp / f"ch_{c_idx}.mp4"
            inputs, mask_inputs, fc, seg_labels = [], [], [], []

            for i, s in enumerate(chunk):
                inputs.append(f"-i \"{s['clip_path']}\"")
                sc = f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase:flags=lanczos,crop={TARGET_W}:{TARGET_H}"
                rot = f"rotate={s['cam']['rotation']}:c=black"
                dur = s["duration_ms"] / 1000
                freeze = f"tpad=stop_mode=clone:stop_duration={FREEZE_S}"

                if s["is_roto"]:
                    mask = self._generate_mask(s["clip_path"], s["seek_start"])
                    mask_inputs.append(f"-i \"{mask}\"")
                    m_idx = len(chunk) + len(mask_inputs) - 1
                    fc.append(f"[{i}:v]trim=start={s['seek_start']}:duration={dur},setpts=PTS-STARTPTS,{sc},{rot},{freeze},split=2[v_a][v_b];"
                              f"[{m_idx}:v]scale={TARGET_W}:{TARGET_H}[msk{i}];"
                              f"[v_a][msk{i}]alphamerge,fade=out:st={dur*0.8}:d=0.2[fg{i}];"
                              f"[v_b]boxblur=15,fade=out:st={dur*0.4}:d=0.4[bg{i}];"
                              f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2[v{i}]")
                elif s.get("transition") == "speedramp":
                    ramp_expr = f"setpts=(1-0.55*(T/{dur}))*PTS"
                    zp = f"zoompan=z='{s['cam']['z']}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={TARGET_W}x{TARGET_H}:fps=24"
                    fc.append(f"[{i}:v]trim=start={s['seek_start']}:duration={dur*1.3},{ramp_expr},setpts=PTS-STARTPTS,{sc},{zp},{rot},format=yuv420p,{vibe['eq']}[v{i}]")
                else:
                    zp = f"zoompan=z='{s['cam']['z']}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={TARGET_W}x{TARGET_H}:fps=24"
                    fc.append(f"[{i}:v]trim=start={s['seek_start']}:duration={dur},setpts=PTS-STARTPTS,{sc},{zp},{rot},format=yuv420p,{vibe['eq']},{freeze}[v{i}]")

                seg_labels.append(f"v{i}")

            fc_script = ";".join([f for f in fc if f.strip()])

            cum_offset, prev_label = 0.0, seg_labels[0]
            for i in range(1, len(chunk)):
                s = chunk[i]
                cum_offset += chunk[i-1]["duration_ms"] / 1000 + FREEZE_S
                transition = s.get("transition", "fade")
                out_label = f"x{i}"

                if transition == "jump":
                    fc_script += f";[{prev_label}][{seg_labels[i]}]concat=n=2:v=1:a=0[{out_label}]"
                else:
                    variant = random.choice(TRANSITION_MAP.get(transition, TRANSITION_MAP["fade"]))
                    xfd = 0.12 if transition == "glitch" else (0.25 if transition == "morph" else 0.18)
                    off = max(0.0, cum_offset - xfd)
                    fc_script += f";[{prev_label}][{seg_labels[i]}]xfade=transition={variant}:duration={xfd}:offset={off:.3f}[{out_label}]"
                prev_label = out_label

            fc_script += f";[{prev_label}]null[outv]"

            f_path = self.temp / f"s_{c_idx}.fc"
            with open(f_path, "w", encoding="utf-8") as f: f.write(fc_script)

            cmd = f"ffmpeg -y -hide_banner -loglevel error {' '.join(inputs)} {' '.join(mask_inputs)} -filter_complex_script \"{f_path.absolute().as_posix()}\" -map \"[outv]\" -c:v libx264 -preset ultrafast -crf 14 \"{chunk_out.absolute().as_posix()}\""
            res = subprocess.run(cmd, shell=True)
            if res.returncode == 0: chunk_files.append(chunk_out)

        self._final_merge(chunk_files, edl["meta"]["mp3"], out_folder / f"{title} [BeatSync-V37.17-VERTICAL].mp4")

    def _generate_mask(self, path, ss):
        m_path = self.temp / f"m_{Path(path).stem}_{int(ss)}.png"
        if not m_path.exists():
            tmp = self.temp / "f.png"
            subprocess.run(f"ffmpeg -y -ss {ss} -i \"{path}\" -frames:v 1 \"{tmp}\"", shell=True, capture_output=True)
            if _ROTO_OK:
                mask = remove(Image.open(tmp), session=_ROTO_SESS, only_mask=True)
                mask.save(m_path)
            else:
                subprocess.run(f"ffmpeg -y -f lavfi -i color=c=black:s={TARGET_W}x{TARGET_H} -frames:v 1 \"{m_path}\"", shell=True)
        return m_path

    def _final_merge(self, chunk_files, mp3, out):
        l_txt = self.temp / "list.txt"
        with open(l_txt, "w") as f:
            for cf in chunk_files: f.write(f"file '{cf.resolve().as_posix()}'\n")
        cmd = f"ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i \"{l_txt.absolute().as_posix()}\" -i \"{mp3}\" -map 0:v -map 1:a -c:v libx264 -preset slow -crf 17 -c:a aac -b:a 320k -shortest \"{out.absolute().as_posix()}\""
        subprocess.run(cmd, shell=True)
        if out.exists(): print(f"✅ FINISHED: {out.name}")

# ═══════════════════════════════════════════════════════════════════
#  DATA LAYER & ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════

class DataLayer:
    def __init__(self, db_path, root):
        self.root = Path(root)
        self.db_path = db_path
        self.mp3_index = {p.name.lower(): p for p in self.root.rglob("*.mp3")}
        self.conn = None

    def fetch(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        clips = [dict(r) for r in self.conn.execute("SELECT * FROM clips").fetchall() if Path(r["path"]).exists()]
        jobs = []
        for h in self.root.rglob("*.html"):
            with open(h, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f, "html.parser")
            for row in soup.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 16: continue
                name = cols[15].text.replace('\xa0', ' ').strip().lower()
                found = self.mp3_index.get(name) or self.mp3_index.get(Path(name).name.lower())
                if found:
                    prio = 0 if "favs" in str(found).lower() else 1
                    bpm_tag_txt = cols[5].text.strip()
                    jobs.append({
                        "mp3": found, "lyrics": cols[13].text, "folder": found.parent, "prio": prio,
                        "bpm_tag": float(bpm_tag_txt) if bpm_tag_txt else None,
                        "key_tag": cols[11].text.strip(),
                        "genre_tag": cols[12].text.strip(),  # KORRIGIERT: Comment-Feld (Genre-Spalte meist leer)
                        "rating_tag": cols[14].text.strip(),
                    })
        return clips, sorted(jobs, key=lambda x: x["prio"]), self.conn

if __name__ == "__main__":
    print(BANNER)
    app_root = Path(__file__).resolve().parent
    dl = DataLayer(DEFAULT_CLIP_DB, r"J:\Oidasheim\Musik")

    conn_boot = sqlite3.connect(DEFAULT_CLIP_DB)
    LibrarySync(conn_boot, CLIP_ROOT).sync()
    conn_boot.close()

    pool, jobs, db_conn = dl.fetch()

    director = OidaIDA(pool, db_conn)
    renderer = DereRenderer(app_root)

    for job in jobs:
        print(f"🚀 Oida! Processing: {job['mp3'].name}")
        try:
            regiebuch = director.create_regiebuch(job)
            renderer.execute(regiebuch, job["folder"])
            shutil.rmtree(renderer.temp, ignore_errors=True)
            renderer.temp.mkdir(exist_ok=True)
        except Exception as e: print(f"❌ Fehler: {e}")