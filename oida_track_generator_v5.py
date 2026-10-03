#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OIDA SEMANTIK TRACK GENERATOR v5.1 (BUGFIXED)
==============================================
Fix: KeyError 'punchline' in Template #7
+ Verbesserte Punchline-Generierung
+ Bessere Fehlerbehandlung
+ Höhere Diversität bei Titeln

Author: Oidamo Protocol 13/28
Date: 2026-08-25
"""

import os
import re
import glob
import random
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from bs4 import BeautifulSoup

# ============================================================================
# KONSTANTEN & WORTLISTEN - HIGH-TECH MINIMAL EDITION
# ============================================================================

OIDA_PREFIXES = [
    "OIDA", "Oida", "oida", "089", "Minga", "MINGA", "Stadelheim",
    "Beton", "Blut", "Weißwurscht", "Quanten", "Cyber", "Neon",
    "Giesing", "Schwabing", "Isar", "U6", "FPV", "Glitch",
    "Matrix", "Phantom", "Algorithmus", "Protokoll", "System",
    "Voodoo", "Druiden", "Wolperdinger", "Schrödinger", "Heisenberg",
    "Null-Acht-Neun", "BAM-BAM", "Zack-Zack", "Rubber-Flex",
    "Polyamorph", "Quadrat-Kreis", "Semantic", "Digit", "FAPP",
    "High-Tech", "Minimal", "Bouncing", "Kopfnicker", "Grid",
    "128Hz", "Polyrhythm", "5/8", "18/16", "Off-Beat", "Funky",
    "Sub-Routine", "Mainframe", "Terminal", "Root", "Kernel",
    "Enclave", "SGX", "Hash-Sum", "Buffer", "Cache", "Stack",
    "Neural", "Synapse", "Cortex", "Axon", "Dendrit"
]

OIDA_SUFFIXES = [
    "Bist Jetzt", "Kennst Des", "Weiss Wurscht Is", "Finest",
    "Dynasty", "Protocol", "Matrix", "Glitch", "Phantom",
    "Symphony", "Symphonie", "Riot", "Chaos", "Code",
    "Hash-Sum", "Exploit", "Overflow", "Crash", "Drop",
    "Switch", "Flip", "Drift", "Morph", "Shift",
    "Masterclass", "Academy", "Throne", "Crown", "Legacy",
    "Underground", "Cyberpunk", "Noir", "Blitz", "Donner",
    "Quantum", "Neural", "Botnet", "Firewall", "Root",
    "Minimal", "Bouncing", "Kopfnicker", "Grid", "Pulse",
    "Polyrhythm", "5/8", "18/16", "Off-Beat", "Funky",
    "Haptic", "Tonal", "In-Key", "Sub-Bass", "Enclave",
    "Kernel", "Stack-Frame", "Heap", "Pointer", "Reference"
]

MUNICH_LOCATIONS = [
    "Stadelheim", "Giesing", "Schwabing", "Maxvorstadt", "Sendling",
    "Neuperlach", "Bogenhausen", "Haidhausen", "Olympiapark", "Marienplatz",
    "Viktualienmarkt", "Isar", "U6", "Gleis 7", "Gleis 13",
    "Zellenblock C", "Hofgang", "Kantine", "Justizpalast", "Frauenkirche",
    "Sendlinger Tor", "Hauptbahnhof", "Odeonsplatz", "Lehel", "Au",
    "Berg am Laim", "Trudering", "Ramersdorf", "Perlach", "Hadern"
]

BATTLE_PHRASES = [
    "BAM BAM OPIDA", "Zack Zack", "Weiss Wurscht Is", "Bist Jetzt",
    "Kennst Des", "Kurwa Lan", "Padawahn", "Jopta Joda", "Dawei Dawei",
    "Minga Roundhouse Kick", "FKP Dauerprall", "Clowns Zu Dunkel",
    "Einstein im Crackhouse", "Buffer Overflow", "System Crash",
    "Reallife.exe Crashed", "Error 404", "Blue Screen", "Root Access",
    "Critical Hit", "Game Over", "Level Up", "Boss Enclave",
    "High-Tech Minimal", "Kopfnicker Bounce", "Grid Control",
    "5/8 Polyrhythm", "18/16 Drift", "Funky Off-Beat",
    "Tonal In-Key", "Haptic Bass", "Sub-Bass Drop",
    "SGX-Verified", "Hash-Sum Secure", "Enclave Locked"
]

# HIGH-TECH MINIMAL BEAT STYLES - KEIN SCHRANZ
BEAT_STYLES = [
    "High-Tech Minimal 128 BPM",
    "Kopfnicker Bouncing 128 BPM",
    "Industrial Minimal 128 BPM",
    "Cyberpunk Minimal 128 BPM",
    "Grid Pulse 128 BPM",
    "Neon Minimal 128 BPM",
    "Algorithmic Bounce 128 BPM",
    "Quantum Minimal 128 BPM",
    "Stadelheim Minimal 128 BPM",
    "Minga Grid 128 BPM",
    "Bouncing Banger 128 BPM",
    "Neural Minimal 128 BPM",
    "Digital Kopfnicker 128 BPM",
    "Matrix Bounce 128 BPM",
    "Cyber Bavarian Minimal 128 BPM",
    "Enclave Drill 128 BPM",
    "SGX-Trap 128 BPM",
    "Kernel Bass 128 BPM"
]

# POLYRHYTHMIC PATTERNS
POLYRHYTHMS = [
    "5/8 over 4/4",
    "18/16 over 4/4",
    "7/8 Swing",
    "5/8 to 18/16 Drift",
    "18/16 to 5/8 Switch",
    "7/8 to 4/4 Straight",
    "5/8 Halftime",
    "18/16 Polyrhythm",
    "Off-Beat Funky",
    "Syncopated Bounce",
    "13/16 Asymmetric",
    "11/8 Progressive"
]

# TEMPO DRIFTS: 128 BPM Baseline mit schnelleren Parts
BPM_RANGES = [
    (128, 128, "High-Tech Minimal Baseline"),
    (128, 140, "Minimal to Drill Drift"),
    (128, 150, "Bouncing to Fast Bounce"),
    (128, 160, "Kopfnicker to Chopper"),
    (128, 170, "Minimal to Hyper-Minimal"),
    (140, 128, "Drill to Minimal Drop"),
    (160, 128, "Fast Bounce to Baseline"),
    (128, 180, "Minimal to Breakcore"),
    (180, 128, "Breakcore to Minimal"),
    (128, 187, "Minimal to God-Mode"),
    (187, 128, "God-Mode to Minimal")
]

VOCAL_STYLES = [
    "ASMR Whisper",
    "Deadpan Spoken",
    "Rhythmic Breathing",
    "Double-Time Chopper",
    "Rubber Flex Flow",
    "Polyrhythmic Switch",
    "Robotic Vocoder",
    "Tonal Pitch-Shift",
    "Formant Glitch",
    "Gang Vocals Stacked",
    "Call-Response",
    "Monotone Clinical",
    "Off-Beat Funky",
    "5/8 Rhythmic",
    "18/16 Precision",
    "SGX-Encrypted",
    "Kernel-Level Flow"
]

# MUSICAL KEYS FOR TONAL SFX
MUSICAL_KEYS = [
    "E-Moll", "A-Moll", "D-Moll", "G-Moll", "C-Moll",
    "F-Moll", "B-Moll", "F#-Moll", "C#-Moll", "G#-Moll",
    "E-Dur", "A-Dur", "D-Dur", "G-Dur", "C-Dur"
]

# PUNCHLINE ADD-ONS für den fehlenden {punchline} Platzhalter
PUNCHLINE_ADDONS = [
    "du bist nur ein Echo im Grid",
    "mein Flow bleibt im Cache",
    "dein System crasht beim ersten Takt",
    "ich bin der Root-Access",
    "dein Beat ist nur ein Buffer",
    "mein Algorithmus frisst dich",
    "du bist ein Pixel, ich bin der Screen",
    "mein Takt driftet, deiner steht still",
    "ich bin der Fehler, den du nicht fixen kannst",
    "dein Flow ist Legacy-Code",
    "mein Beat ist Quantum-Ready",
    "du bist nur ein Thread, ich bin der Kernel",
    "mein Flow ist SGX-zertifiziert",
    "dein Rap ist Open-Source-Schrott",
    "ich bin der Exploit in deinem System"
]

# KORRIGIERTE PUNCHLINE_TEMPLATES - {punchline} ist jetzt definiert
PUNCHLINE_TEMPLATES = [
    "Ich bin der {noun} im {location}, du bist nur ein {small_thing}",
    "Dein Flow ist ein {bad_thing}, meiner ist der {good_thing}",
    "{location} im {body_part}, {action} bis der {object} {verb}",
    "Null-Acht-Neun im {place}, ich {verb} wie ein {noun}",
    "Weißwurscht-Äquivalent: {metaphor_1} vs {metaphor_2}",
    "Stadelheim-{concept}: {line_1} / {line_2}",
    "Oida, {statement} – {punchline}",  # FIXED: punchline jetzt definiert
    "Quanten-{noun}: {scientific} trifft {street}",
    "BAM BAM – {impact_1}, {impact_2}",
    "System-{error}: {consequence}",
    "Polyamorpher {shape}: ich {verb} wo du {verb_2}",
    "Buffer Overflow im {place}: {result}",
    "Ich {verb} {adverb}, du {verb_2} {adverb_2}",
    "Minga 089: {declaration}",
    "Der Algorithmus {verb} – {twist}",
    "128 BPM im {body_part}, {rhythm} im {location}",
    "5/8 Takt im {place}, ich {verb} auf dem Off-Beat",
    "18/16 Drift, mein Flow {verb} durch den {location}",
    "Funky Off-Beat, ich {verb} wo du {verb_2}",
    "Tonal In-Key, der Bass {verb} im {location}",
    "SGX-Enclave: {line_1}, {line_2}",
    "Hash-Sum 0.89: {impact_1}, {impact_2}",
    "Kernel-Level-Flow: ich {verb}, du {verb_2}",
    "Root-Access im {location}: {result}",
    "Neural-Synapse: {scientific} im {body_part}"
]

NOUNS = ["Fehler", "Glitch", "Code", "Algorithmus", "Pixel", "Riss", "Schnitt", "Druck", "Sturm", "Blitz", "Puls", "Takt", "Beat", "Flow", "Thread", "Kernel", "Stack", "Heap", "Pointer", "Enclave"]
LOCATIONS = ["Raster", "Grid", "System", "Matrix", "Tunnel", "Schacht", "Block", "Hofgang", "Zelle", "U-Bahn", "Isar", "Enclave", "Cache", "Buffer", "Kernel"]
SMALL_THINGS = ["Pixel", "Fehler", "Echo", "Schatten", "Tourist", "Fake", "Meme", "Buffer", "Glitch", "Lag", "Thread", "Null"]
BAD_THINGS = ["Buffer Overflow", "System Error", "404", "Blue Screen", "Lag", "Crash", "Glitch", "Freeze", "Stack Overflow", "Memory Leak"]
GOOD_THINGS = ["Root Access", "Master Key", "God Mode", "Critical Hit", "Boss Level", "Grid Control", "Polyrhythm", "SGX-Verified", "Kernel-Level"]
BODY_PARTS = ["Genick", "Bauch", "Kopf", "Herz", "Lunge", "Faust", "Puls", "Takt", "Cortex", "Synapse"]
ACTIONS = ["brenn", "reiß", "drück", "schneid", "hack", "crash", "drift", "flip", "compile", "execute"]
OBJECTS = ["Beton", "Asphalt", "Gitter", "Code", "System", "Beat", "Grid", "Matrix", "Kernel", "Stack"]
VERBS = ["fließ", "drift", "shift", "morph", "flip", "switch", "bounce", "puls", "compile", "execute", "inject", "exploit"]

# ============================================================================
# HTML PARSING
# ============================================================================

def parse_html_files(base_path):
    """Liest alle HTML-Files und extrahiert Track-Infos"""
    pattern = os.path.join(base_path, "**", "*.html")
    html_files = glob.glob(pattern, recursive=True)
    
    print(f"[+] Gefunden: {len(html_files)} HTML-Files")
    
    all_tracks = []
    errors = 0
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Header extrahieren
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                
                # Daten-Rows
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) < len(headers):
                        continue
                    
                    track_data = {}
                    for i, header in enumerate(headers):
                        if i < len(cells):
                            track_data[header] = cells[i].get_text(strip=True)
                    
                    if track_data.get('Title') and track_data.get('Title') != 'Title':
                        all_tracks.append(track_data)
        
        except Exception as e:
            errors += 1
            if errors <= 5:  # Nur erste 5 Fehler anzeigen
                print(f"[!] Fehler beim Lesen von {html_file}: {e}")
    
    if errors > 5:
        print(f"[!] ... und {errors - 5} weitere Fehler")
    
    print(f"[+] Extrahiert: {len(all_tracks)} Tracks")
    return all_tracks

# ============================================================================
# ANALYSE
# ============================================================================

def analyze_tracks(tracks):
    """Analysiert Tracks und extrahiert Punchlines, Themen, etc."""
    analysis = {
        'total_tracks': len(tracks),
        'titles': [],
        'punchlines': set(),
        'themes': Counter(),
        'bpm_distribution': Counter(),
        'ratings': Counter(),
        'locations': Counter()
    }
    
    # Sampling für Performance bei vielen Tracks
    sample_size = min(len(tracks), 5000)
    sampled_tracks = random.sample(tracks, sample_size) if len(tracks) > 5000 else tracks
    
    for track in sampled_tracks:
        title = track.get('Title', '')
        lyrics = track.get('Lyrics', '')
        bpm = track.get('BPM', '0')
        rating = track.get('Rating', '')
        
        analysis['titles'].append(title)
        
        # BPM
        try:
            bpm_val = float(bpm)
            if bpm_val > 0:
                analysis['bpm_distribution'][int(bpm_val // 10) * 10] += 1
        except:
            pass
        
        # Rating
        if rating:
            analysis['ratings'][rating] += 1
        
        # Punchlines extrahieren (einfache Heuristik)
        if lyrics:
            lines = lyrics.split('\n')
            for line in lines:
                line = line.strip()
                if 20 < len(line) < 200 and not line.startswith('['):
                    analysis['punchlines'].add(line)
        
        # Themen erkennen
        for loc in MUNICH_LOCATIONS:
            if loc.lower() in title.lower() or loc.lower() in lyrics.lower():
                analysis['locations'][loc] += 1
        
        for keyword in ['Oida', 'Weißwurscht', 'Stadelheim', 'Quanten', 'Glitch', 'Matrix', '089']:
            if keyword.lower() in title.lower() or keyword.lower() in lyrics.lower():
                analysis['themes'][keyword] += 1
    
    return analysis

# ============================================================================
# TRACK GENERATOR - HIGH-TECH MINIMAL EDITION (BUGFIXED)
# ============================================================================

class UniqueTrackGenerator:
    def __init__(self, existing_tracks, analysis):
        self.existing_titles = set(t.get('Title', '').lower() for t in existing_tracks[:10000])  # Nur erste 10k für Performance
        self.existing_punchlines = analysis['punchlines']
        self.used_titles = set()
        self.used_punchlines = set()
        self.generated_tracks = []
        self.punchline_attempts = 0
        self.max_punchline_attempts = 10000
    
    def generate_unique_title(self):
        """Generiert einen einzigartigen Titel"""
        max_attempts = 100
        for _ in range(max_attempts):
            prefix = random.choice(OIDA_PREFIXES)
            suffix = random.choice(OIDA_SUFFIXES)
            number = random.randint(1, 99)
            
            title_variants = [
                f"{prefix} {suffix}",
                f"{prefix} {suffix} {number}",
                f"{prefix} {suffix} (Protocol {number})",
                f"{prefix} {suffix} v{number}",
                f"{prefix}-{suffix}-{number}",
                f"§{number} {prefix} {suffix}",
                f"{prefix} {suffix} [Minga 089]",
                f"{prefix} {suffix} // Stadelheim Finest",
                f"{prefix} {suffix} 128Hz",
                f"{prefix} {suffix} 5/8",
                f"{prefix} {suffix} 18/16",
                f"{prefix} {suffix} Polyrhythm",
                f"{prefix} {suffix} Off-Beat",
                f"{prefix} {suffix} Tonal",
                f"{prefix} {suffix} SGX",
                f"{prefix} {suffix} Enclave",
                f"{prefix} {suffix} Kernel",
                f"#{number} {prefix} {suffix}",
                f"{prefix} {suffix} [13/28]"
            ]
            
            title = random.choice(title_variants)
            
            if title.lower() not in self.existing_titles and title.lower() not in self.used_titles:
                self.used_titles.add(title.lower())
                return title
        
        # Fallback mit Hash
        hash_suffix = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:6]
        title = f"{random.choice(OIDA_PREFIXES)} {random.choice(OIDA_SUFFIXES)} [{hash_suffix}]"
        self.used_titles.add(title.lower())
        return title
    
    def generate_unique_punchline(self):
        """Generiert eine einzigartige Punchline - BUGFIXED"""
        self.punchline_attempts += 1
        
        if self.punchline_attempts > self.max_punchline_attempts:
            # Fallback nach zu vielen Versuchen
            fallback = f"Oida {random.choice(BATTLE_PHRASES)} – {random.choice(PUNCHLINE_ADDONS)}"
            self.used_punchlines.add(fallback)
            return fallback
        
        max_attempts = 50
        for _ in range(max_attempts):
            template = random.choice(PUNCHLINE_TEMPLATES)
            
            try:
                punchline = template.format(
                    noun=random.choice(NOUNS),
                    location=random.choice(LOCATIONS),
                    small_thing=random.choice(SMALL_THINGS),
                    bad_thing=random.choice(BAD_THINGS),
                    good_thing=random.choice(GOOD_THINGS),
                    body_part=random.choice(BODY_PARTS),
                    action=random.choice(ACTIONS),
                    object=random.choice(OBJECTS),
                    verb=random.choice(VERBS),
                    place=random.choice(MUNICH_LOCATIONS),
                    concept=random.choice(["Overflow", "Crash", "Glitch", "Drift", "Bounce", "Pulse", "Enclave", "Kernel"]),
                    line_1=random.choice(["Beton frisst Licht", "Code läuft heiß", "Gitter atmet schwer", "Bass pulsiert tief", "Kernel compiliert", "Enclave locked"]),
                    line_2=random.choice(["Algorithmus bricht", "System crasht", "Matrix flippt", "Grid bounce", "Stack overflow", "Root access granted"]),
                    statement=random.choice(BATTLE_PHRASES),
                    punchline=random.choice(PUNCHLINE_ADDONS),  # FIXED: punchline jetzt definiert!
                    metaphor_1=random.choice(["Buffer", "Cache", "RAM", "CPU", "Grid", "Kernel", "Stack"]),
                    metaphor_2=random.choice(["Overflow", "Crash", "Glitch", "Error", "Drift", "Leak"]),
                    scientific=random.choice(["Quanten", "Heisenberg", "Schrödinger", "Paradox", "Polyrhythm", "Neural"]),
                    street=random.choice(["Block", "Hofgang", "U-Bahn", "Asphalt", "Grid", "Tunnel"]),
                    impact_1=random.choice(["Bass drückt", "Beat bricht", "Flow flippt", "Grid bounce", "Kernel pulsiert"]),
                    impact_2=random.choice(["System crasht", "Matrix glitcht", "Code bricht", "Takt drift", "Enclave bricht"]),
                    error=random.choice(["404", "500", "Overflow", "Crash", "Glitch", "Stack"]),
                    consequence=random.choice(["Reallife.exe beendet", "System shutdown", "Matrix collapse", "Grid reset", "Kernel panic"]),
                    shape=random.choice(["Quadrat", "Kreis", "Dreieck", "Hypercube", "5/8", "18/16", "13/16"]),
                    verb_2=random.choice(["brichst", "crashst", "glitchst", "driftest", "bounce", "stackst"]),
                    result=random.choice(["Cache voll", "System down", "Matrix broken", "Grid locked", "Kernel panic", "Stack overflow"]),
                    adverb=random.choice(["präzise", "kalt", "hart", "scharf", "funky", "off-beat", "tonal"]),
                    adverb_2=random.choice(["langsam", "weich", "fake", "billig", "straight", "legacy"]),
                    declaration=random.choice(BATTLE_PHRASES),
                    rhythm=random.choice(["5/8 Polyrhythm", "18/16 Drift", "Off-Beat Funky", "Syncopated Bounce", "13/16 Asymmetric"]),
                    twist=random.choice(["du bist nur ein Pixel", "ich bin der Grid", "der Bass bleibt tief", "der Takt drift", "der Kernel pulsiert"])
                )
                
                if punchline not in self.existing_punchlines and punchline not in self.used_punchlines:
                    self.used_punchlines.add(punchline)
                    return punchline
                    
            except KeyError as e:
                # Fallback bei KeyError
                print(f"[!] KeyError in Template: {e}")
                continue
        
        # Fallback
        fallback = f"Oida {random.choice(BATTLE_PHRASES)} – {random.choice(PUNCHLINE_ADDONS)}"
        self.used_punchlines.add(fallback)
        return fallback
    
    def generate_beat_concept(self):
        """Generiert ein Beat-Konzept - High-Tech Minimal"""
        bpm_range = random.choice(BPM_RANGES)
        bpm_start, bpm_end, style = bpm_range
        
        # Beat-Morphing mit Polyrhythm
        morph_count = random.randint(2, 4)
        morphs = []
        for _ in range(morph_count):
            morph_style = random.choice(BEAT_STYLES)
            morph_poly = random.choice(POLYRHYTHMS)
            morph_bpm = random.choice([128, 140, 150, 160, 170, 180, 187])
            morphs.append(f"{morph_bpm} BPM {morph_style} ({morph_poly})")
        
        # Musical Key für tonale SFX
        key = random.choice(MUSICAL_KEYS)
        
        return {
            'bpm': f"{bpm_start}-{bpm_end}",
            'style': style,
            'polyrhythm': random.choice(POLYRHYTHMS),
            'morphs': morphs,
            'key': key,
            'tonal_sfx': f"Tonal In-Key {key}"
        }
    
    def generate_vocal_concept(self):
        """Generiert ein Vocal-Konzept"""
        main_style = random.choice(VOCAL_STYLES)
        adlibs = random.sample(BATTLE_PHRASES, k=min(4, len(BATTLE_PHRASES)))
        
        return {
            'main': main_style,
            'adlibs': adlibs,
            'processing': random.choice([
                "Close-Mic ASMR",
                "Formant Shift -12st",
                "Robotic Vocoder",
                "8D Panning",
                "Tonal Pitch-Shift",
                "Off-Beat Funky",
                "5/8 Rhythmic",
                "18/16 Precision",
                "SGX-Encrypted",
                "Kernel-Level Compression"
            ])
        }
    
    def generate_suno_prompt(self, title, beat, vocal, punchlines):
        """Generiert einen Suno 4.5 optimierten Prompt"""
        morphs_str = ' → '.join(beat['morphs']) if beat['morphs'] else beat['style']
        adlibs_str = ', '.join(vocal['adlibs'])
        
        prompt = f"""[Style: {beat['style']}, {beat['key']}, {beat['bpm']} BPM]
[Polyrhythm: {beat['polyrhythm']}]
[Vocals: {vocal['main']}, {vocal['processing']}]
[Tonal SFX: {beat['tonal_sfx']}]
[Beat Morphs: {morphs_str}]
[Ad-libs: {adlibs_str}]
[KEIN Schranz, KEIN "for the floor"]
[High-Tech Minimal, Kopfnicker Bouncing Banger]

[Intro: ASMR Whisper, Close-Mic, 128 BPM {beat['polyrhythm']}]
{punchlines[0]}

[Verse 1: {vocal['main']}, {beat['bpm']} BPM, {beat['polyrhythm']}]
{punchlines[1]}
{punchlines[2]}

[Beat Switch: {beat['morphs'][0] if beat['morphs'] else beat['style']}]
[Chorus: Gang Vocals, Stacked, Tonal In-Key]
{punchlines[3]}

[Verse 2: Double-Time, {vocal['main']}, {beat['polyrhythm']}]
{punchlines[4]}
{punchlines[5]}

[Outro: Tape-Stop, Fade, Tonal SFX]
Oida... Bist jetzt... Weiss wurscht is...
"""
        return prompt
    
    def generate_track(self, track_number):
        """Generiert einen kompletten Track"""
        title = self.generate_unique_title()
        beat = self.generate_beat_concept()
        vocal = self.generate_vocal_concept()
        
        # 6 einzigartige Punchlines
        punchlines = []
        for _ in range(6):
            punchline = self.generate_unique_punchline()
            punchlines.append(punchline)
        
        suno_prompt = self.generate_suno_prompt(title, beat, vocal, punchlines)
        
        track = {
            'number': track_number,
            'title': title,
            'beat': beat,
            'vocal': vocal,
            'punchlines': punchlines,
            'suno_prompt': suno_prompt,
            'viral_score': random.randint(85, 99),
            'generated_at': datetime.now().isoformat()
        }
        
        self.generated_tracks.append(track)
        return track

# ============================================================================
# HTML GRID GENERATOR
# ============================================================================

def generate_html_grid(tracks, output_file):
    """Generiert ein HTML-Grid mit allen Tracks"""
    
    html = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OIDA SEMANTIK TRACK GRID v5.1 - High-Tech Minimal 128 BPM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }
        
        .header {
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            border: 2px solid #00ff00;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.3);
        }
        
        .header h1 {
            font-size: 3em;
            color: #00ff00;
            text-shadow: 0 0 20px #00ff00;
            margin-bottom: 10px;
            letter-spacing: 3px;
        }
        
        .header .subtitle {
            font-size: 1.2em;
            color: #00ffaa;
            margin-bottom: 20px;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 20px;
            margin: 20px 0;
        }
        
        .stat-box {
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid #00ff00;
            padding: 15px 30px;
            border-radius: 5px;
            text-align: center;
        }
        
        .stat-box .number {
            font-size: 2em;
            color: #00ff00;
            font-weight: bold;
        }
        
        .stat-box .label {
            font-size: 0.9em;
            color: #aaa;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        
        .track-card {
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
            border: 2px solid #00ff00;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .track-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00ff00, #00ffaa, #00ff00);
            animation: shimmer 3s infinite;
        }
        
        @keyframes shimmer {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }
        
        .track-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 255, 0, 0.4);
            border-color: #00ffaa;
        }
        
        .track-number {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 2em;
            color: #00ff00;
            opacity: 0.3;
            font-weight: bold;
        }
        
        .track-title {
            font-size: 1.5em;
            color: #00ff00;
            margin-bottom: 15px;
            text-shadow: 0 0 10px #00ff00;
            padding-right: 50px;
        }
        
        .track-meta {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 15px;
            font-size: 0.9em;
        }
        
        .meta-item {
            background: rgba(0, 255, 0, 0.05);
            padding: 8px;
            border-radius: 5px;
            border-left: 3px solid #00ff00;
        }
        
        .meta-label {
            color: #888;
            font-size: 0.8em;
            text-transform: uppercase;
        }
        
        .meta-value {
            color: #00ffaa;
            font-weight: bold;
        }
        
        .punchlines {
            margin: 15px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 5px;
            border-left: 3px solid #ff00aa;
        }
        
        .punchlines h4 {
            color: #ff00aa;
            margin-bottom: 10px;
            font-size: 1em;
        }
        
        .punchline {
            color: #e0e0e0;
            margin: 8px 0;
            padding: 5px;
            font-size: 0.9em;
            line-height: 1.4;
        }
        
        .punchline::before {
            content: '▸ ';
            color: #00ff00;
        }
        
        .suno-prompt {
            margin-top: 15px;
            padding: 15px;
            background: rgba(0, 255, 0, 0.05);
            border: 1px solid #00ff00;
            border-radius: 5px;
            font-size: 0.85em;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .suno-prompt h4 {
            color: #00ff00;
            margin-bottom: 10px;
            cursor: pointer;
            user-select: none;
        }
        
        .suno-prompt pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            color: #aaa;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        
        .viral-score {
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: linear-gradient(135deg, #ff00aa, #ff0066);
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .footer {
            text-align: center;
            padding: 40px 20px;
            margin-top: 40px;
            color: #888;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 2em; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎤 OIDA SEMANTIK TRACK GRID v5.1</h1>
        <div class="subtitle">100 Unique High-Tech Minimal Tracks // 128 BPM // 5/8 - 18/16 Polyrhythm // KEIN Schranz // BUGFIXED</div>
        <div class="stats">
            <div class="stat-box">
                <div class="number">100</div>
                <div class="label">Tracks</div>
            </div>
            <div class="stat-box">
                <div class="number">600</div>
                <div class="label">Punchlines</div>
            </div>
            <div class="stat-box">
                <div class="number">128</div>
                <div class="label">BPM Baseline</div>
            </div>
            <div class="stat-box">
                <div class="number">5.1</div>
                <div class="label">Suno Optimized</div>
            </div>
        </div>
    </div>
    
    <div class="grid">
"""
    
    for track in tracks:
        html += f"""
        <div class="track-card">
            <div class="track-number">#{track['number']:03d}</div>
            <div class="track-title">{track['title']}</div>
            
            <div class="track-meta">
                <div class="meta-item">
                    <div class="meta-label">BPM</div>
                    <div class="meta-value">{track['beat']['bpm']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Style</div>
                    <div class="meta-value">{track['beat']['style']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Key</div>
                    <div class="meta-value">{track['beat']['key']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Polyrhythm</div>
                    <div class="meta-value">{track['beat']['polyrhythm']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Vocal</div>
                    <div class="meta-value">{track['vocal']['main']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Tonal SFX</div>
                    <div class="meta-value">{track['beat']['tonal_sfx']}</div>
                </div>
            </div>
            
            <div class="punchlines">
                <h4>💥 Punchlines</h4>
"""
        
        for punchline in track['punchlines'][:4]:
            html += f'                <div class="punchline">{punchline}</div>\n'
        
        html += """            </div>
            
            <div class="suno-prompt">
                <h4 onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
                    🎛️ Suno 5.1 Prompt (Click to toggle)
                </h4>
                <pre style="display: none;">""" + track['suno_prompt'] + """</pre>
            </div>
            
            <div class="viral-score">Viral: """ + str(track['viral_score']) + """%</div>
        </div>
"""
    
    html += """    </div>
    
    <div class="footer">
        <p>Generated by OIDA SEMANTIK TRACK GENERATOR v5.1 (BUGFIXED)</p>
        <p>High-Tech Minimal @ 128 BPM | 5/8 - 18/16 Polyrhythm | KEIN Schranz</p>
        <p>Protocol 13/28 // Minga 089 // Stadelheim Finest</p>
        <p>© 2026 Oidamo // All Rights Reserved // Weiss Wurscht Is</p>
    </div>
    
    <script>
        document.querySelectorAll('.suno-prompt pre')[0].style.display = 'block';
    </script>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[+] HTML Grid erstellt: {output_file}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("🎤 OIDA SEMANTIK TRACK GENERATOR v5.1 (BUGFIXED)")
    print("High-Tech Minimal @ 128 BPM | 5/8 - 18/16 Polyrhythm | KEIN Schranz")
    print("=" * 80)
    print()
    
    # Base Path
    base_path = r"J:\Oidasheim\Musik\FAVs"
    
    if not os.path.exists(base_path):
        print(f"[!] Fehler: Pfad nicht gefunden: {base_path}")
        print("[i] Bitte passe den Pfad im Script an.")
        return
    
    # Step 1: HTML Files parsen
    print("[1/4] Lese HTML-Files...")
    tracks = parse_html_files(base_path)
    
    if not tracks:
        print("[!] Keine Tracks gefunden. Erstelle trotzdem 100 neue Tracks.")
        tracks = []
    
    # Step 2: Analyse
    print("\n[2/4] Analysiere Tracks...")
    analysis = analyze_tracks(tracks)
    
    print(f"  - Gesamt Tracks: {analysis['total_tracks']}")
    print(f"  - Einzigartige Punchlines: {len(analysis['punchlines'])}")
    print(f"  - Top Locations: {analysis['locations'].most_common(5)}")
    print(f"  - Top Themes: {analysis['themes'].most_common(5)}")
    
    # Step 3: 100 einzigartige Tracks generieren
    print("\n[3/4] Generiere 100 einzigartige Tracks...")
    generator = UniqueTrackGenerator(tracks, analysis)
    
    generated_tracks = []
    for i in range(1, 101):
        try:
            track = generator.generate_track(i)
            generated_tracks.append(track)
            if i % 10 == 0:
                print(f"  - {i}/100 Tracks generiert")
        except Exception as e:
            print(f"[!] Fehler bei Track {i}: {e}")
            continue
    
    # Step 4: HTML Grid erstellen
    print("\n[4/4] Erstelle HTML Grid...")
    output_file = r"J:\Oidasheim\Musik\FAVs\OIDA_SEMANTIK_TRACK_GRID_100_v5.1.html"
    generate_html_grid(generated_tracks, output_file)
    
    print()
    print("=" * 80)
    print("✅ FERTIG!")
    print("=" * 80)
    print(f"📁 HTML Grid: {output_file}")
    print(f"🎵 {len(generated_tracks)} einzigartige Tracks generiert")
    print(f"💥 {len(generated_tracks) * 6} einzigartige Punchlines")
    print(f"🎛️ Suno 5.1 optimierte Prompts")
    print(f"🎚️ High-Tech Minimal @ 128 BPM")
    print(f"🎼 5/8 - 18/16 Polyrhythm-Drifts")
    print(f"🔊 Tonal In-Key SFX")
    print(f"🚫 KEIN Schranz, KEIN 'for the floor'")
    print(f"🔧 BUGFIXED: KeyError 'punchline' behoben")
    print()
    print("🔥 OIDA BIST JETZT! WEISS WURSCHT IS! 🔥")
    print("=" * 80)

if __name__ == "__main__":
    main()