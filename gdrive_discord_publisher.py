#!/usr/bin/env python3
"""
gdrive_discord_publisher.py — Uploads Music Video, Metadata & Setcard to Google Drive and posts Discord Webhook.
Target Google Drive Folder: https://drive.google.com/drive/folders/1sa62QVhB-y9zESjQqyGJ7T98TZqxw73u?usp=drive_link
"""

import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.parse
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from config import (
        GDRIVE_RELEASE_FOLDER_ID,
        GDRIVE_RELEASE_FOLDER_URL,
        DISCORD_WEBHOOK_OIDA,
        DISCORD_WEBHOOK_WONG,
        DISCORD_WEBHOOK_URLS
    )
except ImportError:
    GDRIVE_RELEASE_FOLDER_ID = "1sa62QVhB-y9zESjQqyGJ7T98TZqxw73u"
    GDRIVE_RELEASE_FOLDER_URL = f"https://drive.google.com/drive/folders/{GDRIVE_RELEASE_FOLDER_ID}?usp=drive_link"
    DISCORD_WEBHOOK_OIDA = "https://discord.com/api/webhooks/1551732581471621122/K32qznEZnrIDkT2lg_ylLxYOAnzDokvpo9HuIEEBcfeGm7DgiiVQBLrXRcqqIRP5ZS7K"
    DISCORD_WEBHOOK_WONG = "https://discord.com/api/webhooks/1550973113100140687/MDlSN-HdPwBeVMQjHmYWzxgVFiK5xoY97lyno5bDD-oUeLTn1NArc8QA7pYX6Q6bn3nQ"
    DISCORD_WEBHOOK_URLS = {"oida": DISCORD_WEBHOOK_OIDA, "wong": DISCORD_WEBHOOK_WONG, "default": DISCORD_WEBHOOK_OIDA}

GDRIVE_FOLDER_ID = GDRIVE_RELEASE_FOLDER_ID
GDRIVE_FOLDER_URL = GDRIVE_RELEASE_FOLDER_URL

def generate_setcard_html(meta: Dict[str, Any], output_path: Path) -> Path:
    """Generates an aesthetic, responsive HTML Setcard."""
    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SETCARD — {meta.get('track_title', 'Track')} | {meta.get('artist', 'Artist')}</title>
    <style>
        :root {{
            --bg-color: #0b0c10;
            --card-bg: #1f2833;
            --accent-primary: #66fcf1;
            --accent-secondary: #45a29e;
            --text-main: #c5c6c7;
            --text-bright: #ffffff;
            --danger: #ff0055;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 24px;
        }}
        .setcard {{
            background: var(--card-bg);
            border-radius: 20px;
            border: 1px solid rgba(102, 252, 241, 0.2);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 20px rgba(102, 252, 241, 0.1);
            max-width: 900px;
            width: 100%;
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1f2833 0%, #0b0c10 100%);
            border-bottom: 2px solid var(--accent-primary);
            padding: 36px 40px;
            text-align: center;
            position: relative;
        }}
        .badge {{
            display: inline-block;
            background: rgba(102, 252, 241, 0.15);
            color: var(--accent-primary);
            padding: 4px 14px;
            border-radius: 50px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 12px;
            border: 1px solid rgba(102, 252, 241, 0.3);
        }}
        .header h1 {{
            color: var(--text-bright);
            font-size: 2.6rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            margin-bottom: 6px;
        }}
        .header h3 {{
            color: var(--accent-secondary);
            font-size: 1.2rem;
            font-weight: 500;
        }}
        .content-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            padding: 36px 40px;
        }}
        .box {{
            background: rgba(11, 12, 16, 0.6);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .box.full-width {{
            grid-column: span 2;
        }}
        .box-title {{
            color: var(--accent-primary);
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            font-size: 0.95rem;
        }}
        .info-row:last-child {{ margin-bottom: 0; }}
        .label {{ color: #8a94b8; font-size: 0.85rem; text-transform: uppercase; }}
        .value {{ color: var(--text-bright); font-weight: 600; font-family: monospace; font-size: 1rem; }}
        .drive-btn {{
            display: inline-block;
            width: 100%;
            background: linear-gradient(135deg, var(--accent-secondary), var(--accent-primary));
            color: #0b0c10;
            text-align: center;
            padding: 14px 20px;
            border-radius: 10px;
            font-weight: 700;
            text-decoration: none;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 252, 241, 0.3);
            margin-top: 10px;
        }}
        .drive-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 252, 241, 0.5);
        }}
        .tags-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}
        .tag {{
            background: rgba(102, 252, 241, 0.1);
            color: var(--accent-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
        }}
        .footer {{
            background: #0b0c10;
            padding: 18px 40px;
            text-align: center;
            font-size: 0.8rem;
            color: #555e70;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}
    </style>
</head>
<body>
    <div class="setcard">
        <div class="header">
            <div class="badge">Official Synapse Release</div>
            <h1>{meta.get('track_title', 'Track')}</h1>
            <h3>Artist: {meta.get('artist', 'Oidamo')}</h3>
        </div>
        <div class="content-grid">
            <div class="box">
                <div class="box-title">💿 Release Details</div>
                <div class="info-row"><span class="label">ISRC</span><span class="value">{meta.get('isrc', 'DE-SYN-26-08901')}</span></div>
                <div class="info-row"><span class="label">UPC</span><span class="value">{meta.get('upc', '42600929112233')}</span></div>
                <div class="info-row"><span class="label">BPM</span><span class="value">{meta.get('bpm', 140)} BPM</span></div>
                <div class="info-row"><span class="label">Genre</span><span class="value">{meta.get('genre', 'Bavarian Drill / Boom Bap')}</span></div>
            </div>
            <div class="box">
                <div class="box-title">🏛️ Label & Rights</div>
                <div class="info-row"><span class="label">Label</span><span class="value">{meta.get('label', 'SYNAPSE AUDIO DYNAMICS')}</span></div>
                <div class="info-row"><span class="label">Territory</span><span class="value">GLOBAL (Worldwide)</span></div>
                <div class="info-row"><span class="label">Engine</span><span class="value">BeatSync v1.0 OIDA</span></div>
                <div class="info-row"><span class="label">Release ID</span><span class="value">{meta.get('release_id', 'REL-089-ROBOT')}</span></div>
            </div>
            <div class="box full-width">
                <div class="box-title">☁️ Cloud Storage & Public Delivery</div>
                <div class="info-row"><span class="label">Google Drive Folder</span><span class="value" style="color: var(--accent-primary);">{GDRIVE_FOLDER_URL}</span></div>
                <div class="info-row"><span class="label">Video Asset</span><span class="value">{meta.get('video_filename', 'video.mp4')}</span></div>
                <div class="info-row"><span class="label">Audio Master</span><span class="value">{meta.get('audio_filename', 'audio.mp3')}</span></div>
                <a href="{GDRIVE_FOLDER_URL}" target="_blank" class="drive-btn">📂 Open Google Drive Folder</a>
            </div>
            <div class="box full-width">
                <div class="box-title">🎨 Concept & Visual DNA</div>
                <p style="font-size: 0.95rem; line-height: 1.6; color: #a0aabf;">{meta.get('concept', 'Autonome Beat-synchrone Visuals mit schnellen Cuts, Virtual Camera Dynamics und OIDA Visual DNA.')}</p>
                <div class="tags-container">
                    {"".join(f'<span class="tag">{t}</span>' for t in meta.get('hashtags', ['#Oidamo', '#BeatSync', '#München', '#BavarianDrill']))}
                </div>
            </div>
        </div>
        <div class="footer">
            POWERED BY SYNAPSE AUDIO DYNAMICS • OIDASHEIM ECOSYSTEM
        </div>
    </div>
</body>
</html>
"""
    output_path.write_text(html_content, encoding="utf-8")
    return output_path

def resolve_or_create_mastered_mp3(video_path: Path, audio_path: Optional[Path] = None, profile: str = "cinematic") -> Path:
    """Finds, masters via VEGA Neural DSP, or extracts high quality 320kbps mastered MP3 audio."""
    out_dir = video_path.parent
    track_title = video_path.stem.split("_beatsync")[0]
    target_mp3 = out_dir / f"{track_title}_mastered.mp3"

    # 1. If target_mp3 already exists and is valid (>100KB), return it
    if target_mp3.exists() and target_mp3.stat().st_size > 100 * 1024:
        return target_mp3

    # 2. Prefer VEGA Neural DSP Mastering from source audio
    src = None
    if audio_path and Path(audio_path).exists():
        src = Path(audio_path)
    else:
        parent_mp3 = video_path.parent.parent / f"{track_title}.mp3"
        if parent_mp3.exists():
            src = parent_mp3
        else:
            candidates = list(video_path.parent.parent.glob("*.mp3"))
            if candidates:
                src = candidates[0]

    if src and src.exists():
        try:
            from vega_mastering import VEGAMasteringEngine
            engine = VEGAMasteringEngine(profile)
            if engine.master_audio(src, target_mp3):
                return target_mp3
        except Exception as e:
            print(f"  ⚠️ VEGA Mastering Exception ({e}), fallback auf Audio-Extraktion...")

    # 3. Extract mastered audio from rendered MP4 video via ffmpeg
    if video_path.exists() and video_path.stat().st_size > 1024 * 1024:
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", str(video_path),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            "-id3v2_version", "3",
            "-metadata", f"title={track_title}",
            "-metadata", "artist=Oidamo",
            "-metadata", "album=SYNAPSE AUDIO DYNAMICS",
            str(target_mp3)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and target_mp3.exists() and target_mp3.stat().st_size > 0:
                print(f"  🎵 Mastered MP3 extrahiert (320kbps): {target_mp3.name}")
                return target_mp3
        except Exception as e:
            print(f"  ⚠️ Audio-Extraktion fehlgeschlagen ({e})...")

    # 4. Fallback to passed audio_path or source MP3 in folder
    if src and src.exists():
        return src

    return target_mp3

def build_release_bundle(video_path: Path, audio_path: Optional[Path] = None, output_dir: Optional[Path] = None, meta_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Builds complete metadata and setcard package for a rendered video."""
    out_dir = output_dir or video_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target_meta_dir = meta_dir or out_dir
    target_meta_dir.mkdir(parents=True, exist_ok=True)

    # Extract clean track title
    stem_clean = video_path.stem
    for tag in ("_16zu9", "_9zu16", "_tiktok", "_beatsync"):
        if tag in stem_clean:
            stem_clean = stem_clean.split(tag)[0]
    track_title = stem_clean.strip()

    isrc = f"DE-SYN-26-{uuid.uuid4().int % 100000:05d}"
    upc = f"42600929{uuid.uuid4().int % 1000000:06d}"
    release_id = f"REL-{uuid.uuid4().hex[:8].upper()}"

    # Resolve Mastered MP3 in main song directory
    mastered_audio = resolve_or_create_mastered_mp3(video_path, audio_path)

    meta = {
        "release_id": release_id,
        "isrc": isrc,
        "upc": upc,
        "track_title": track_title,
        "artist": "Oidamo",
        "label": "SYNAPSE AUDIO DYNAMICS",
        "genre": "Bavarian Drill / Boom Bap Parody",
        "bpm": 140,
        "video_path": str(video_path.resolve()),
        "video_filename": video_path.name,
        "audio_path": str(mastered_audio.resolve()) if mastered_audio and mastered_audio.exists() else None,
        "audio_filename": mastered_audio.name if mastered_audio else "mastered_audio.mp3",
        "gdrive_folder_id": GDRIVE_FOLDER_ID,
        "gdrive_folder_url": GDRIVE_FOLDER_URL,
        "hashtags": ["#Oidamo", "#BavarianDrill", "#BoomBap", "#BeatSync", "#München089", "#SynapseAudio"],
        "concept": "Dynamische Virtual Camera Schnitte, präzises Takt- & Downbeat-Snapping und volle visuelle Energie im Oidasheim-Style.",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Write Meta JSON into meta_dir
    meta_path = target_meta_dir / f"META_ASSET_{track_title.replace(' ', '_')}.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write Setcard HTML into meta_dir
    setcard_path = target_meta_dir / f"SETCARD_{track_title.replace(' ', '_')}.html"
    generate_setcard_html(meta, setcard_path)

    meta["meta_file"] = str(meta_path.resolve())
    meta["setcard_file"] = str(setcard_path.resolve())
    return meta

def send_discord_webhook(meta: Dict[str, Any], webhook_url: str, attach_files: bool = True, log_fn=print) -> bool:
    """Dispatches a rich Discord Embed with actual file attachments (Mastered MP3, Setcard HTML, Meta JSON) to Discord Webhook."""
    payload = {
        "username": "SYNAPSE PUBX Gateway",
        "avatar_url": "https://i.imgur.com/8N4Z4Z4.png",
        "content": f"🚀 **NEUES MUSIKVIDEO & MASTERED AUDIO RELEASE!**\n**Track:** `{meta['track_title']}`\n**Google Drive:** <{meta['gdrive_folder_url']}>",
        "embeds": [
            {
                "title": f"🎬 {meta['track_title']} — Offizielles Musikvideo, Mastered MP3 & Setcard",
                "url": meta["gdrive_folder_url"],
                "description": meta.get("concept", ""),
                "color": 6749425,  # #66FCF1 Cyan
                "fields": [
                    {"name": "🎤 Artist", "value": meta.get("artist", "Oidamo"), "inline": True},
                    {"name": "🏷️ Label", "value": meta.get("label", "SYNAPSE AUDIO DYNAMICS"), "inline": True},
                    {"name": "🆔 ISRC", "value": f"`{meta.get('isrc')}`", "inline": True},
                    {"name": "📦 UPC", "value": f"`{meta.get('upc')}`", "inline": True},
                    {"name": "🔊 Mastered MP3 Track", "value": f"[`{meta.get('audio_filename')}`]({meta['gdrive_folder_url']})", "inline": True},
                    {"name": "🎞️ Video Datei", "value": f"[`{meta.get('video_filename')}`]({meta['gdrive_folder_url']})", "inline": True},
                    {"name": "📄 Setcard Datei", "value": f"[`{Path(meta.get('setcard_file', '')).name}`]({meta['gdrive_folder_url']})", "inline": True},
                    {"name": "📂 Google Drive Folder", "value": f"[Hier alle Dateien öffnen & laden]({meta['gdrive_folder_url']})", "inline": False},
                    {"name": "📲 Hashtags", "value": " ".join(meta.get("hashtags", [])), "inline": False},
                ],
                "footer": {
                    "text": "SYNAPSE AUDIO DYNAMICS • Automated Multi-Platform Release Gateway"
                },
                "timestamp": meta.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            }
        ]
    }

    files_to_attach = {}
    opened_files = []

    if attach_files:
        # 1. Mastered MP3 Audio
        if meta.get("audio_path") and Path(meta["audio_path"]).exists():
            mp3_p = Path(meta["audio_path"])
            if mp3_p.stat().st_size <= 24 * 1024 * 1024:  # Discord Webhook file limit
                f_mp3 = open(mp3_p, "rb")
                opened_files.append(f_mp3)
                idx = len(files_to_attach)
                files_to_attach[f"files[{idx}]"] = (mp3_p.name, f_mp3, "audio/mpeg")
                log_fn(f"  📎 Hänge gemastertes MP3 an Discord an ({mp3_p.stat().st_size / 1024 / 1024:.2f} MB): {mp3_p.name}")

        # 2. Setcard HTML
        if meta.get("setcard_file") and Path(meta["setcard_file"]).exists():
            sc_p = Path(meta["setcard_file"])
            f_sc = open(sc_p, "rb")
            opened_files.append(f_sc)
            idx = len(files_to_attach)
            files_to_attach[f"files[{idx}]"] = (sc_p.name, f_sc, "text/html")
            log_fn(f"  📎 Hänge Setcard HTML an Discord an: {sc_p.name}")

        # 3. Meta Asset JSON
        if meta.get("meta_file") and Path(meta["meta_file"]).exists():
            m_p = Path(meta["meta_file"])
            f_m = open(m_p, "rb")
            opened_files.append(f_m)
            idx = len(files_to_attach)
            files_to_attach[f"files[{idx}]"] = (m_p.name, f_m, "application/json")
            log_fn(f"  📎 Hänge Meta Asset JSON an Discord an: {m_p.name}")

    try:
        if files_to_attach:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files=files_to_attach,
                headers={"User-Agent": "Antigravity-PUBXGateway/3.1"},
                timeout=45
            )
        else:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"User-Agent": "Antigravity-PUBXGateway/3.1"},
                timeout=15
            )

        status = response.status_code
        if status in (200, 204):
            log_fn(f"  ✅ Discord Webhook mit Dateianhängen erfolgreich gesendet (Status: {status})")
            return True
        else:
            log_fn(f"  ❌ Discord Webhook fehlgeschlagen (Status: {status}): {response.text[:200]}")
            return False
    except Exception as e:
        log_fn(f"  ❌ Fehler beim Senden des Discord Webhooks: {e}")
        return False
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass

def upload_to_gdrive(file_paths: list[Path], folder_id: str = GDRIVE_FOLDER_ID, credentials_path: Optional[str] = None) -> list[dict]:
    """Uploads files to Google Drive folder using google-api-python-client if credentials are available."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        import google_auth_oauthlib.flow

        creds = None
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        # 1. Check passed credentials path or env var
        cred_file = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_file and Path(cred_file).exists():
            try:
                creds = service_account.Credentials.from_service_account_file(cred_file, scopes=SCOPES)
            except Exception:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
                creds = flow.run_local_server(port=0)
        
        if not creds:
            print("ℹ️ Keine Google Drive API Credentials gefunden. Verwende Public Drive Folder Link.")
            return []

        service = build('drive', 'v3', credentials=creds)
        uploaded = []
        for fp in file_paths:
            if not fp.exists():
                continue
            print(f"⬆️ Uploading to Google Drive: {fp.name}...")
            file_metadata = {
                'name': fp.name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(str(fp), resumable=True)
            file_drive = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            print(f"✅ Upload abgeschlossen: {fp.name} (ID: {file_drive.get('id')})")
            uploaded.append(file_drive)
        return uploaded
    except Exception as e:
        print(f"⚠️ Google Drive API Upload nicht direkt ausführbar ({e}).")
        return []

def publish_release(
    video_path: Path,
    audio_path: Optional[Path] = None,
    webhook_urls: Optional[list[str]] = None,
    upload_gdrive: bool = False,
    credentials_path: Optional[str] = None,
    log_fn=print
) -> Dict[str, Any]:
    """
    Kombinierter Publisher:
    1. Erstellt Release-Bundle (Setcard HTML, Meta JSON, Mastered 320k MP3)
    2. Optional: Google Drive Upload
    3. Sendet Webhook (Discord Embeds + Dateianhänge)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        log_fn(f"❌ [PUBX] Video-Datei nicht gefunden: {video_path}")
        return {"success": False, "error": "Video not found"}

    log_fn(f"📦 [PUBX] Erstelle Release-Paket für: {video_path.name}")
    bundle = build_release_bundle(video_path, audio_path=audio_path)
    
    setcard_p = bundle.get("setcard_file")
    meta_p = bundle.get("meta_file")
    audio_p = bundle.get("audio_path")
    
    log_fn(f"  📄 Setcard HTML erstellt: {Path(setcard_p).name if setcard_p else '–'}")
    log_fn(f"  🏷️ Meta Asset JSON erstellt: {Path(meta_p).name if meta_p else '–'}")
    if audio_p and Path(audio_p).exists():
        log_fn(f"  🎵 Mastered Audio bereit: {Path(audio_p).name}")

    # 1. Google Drive Upload
    uploaded_drive = []
    if upload_gdrive:
        files_to_upload = [video_path]
        if audio_p and Path(audio_p).exists():
            files_to_upload.append(Path(audio_p))
        if setcard_p and Path(setcard_p).exists():
            files_to_upload.append(Path(setcard_p))
        if meta_p and Path(meta_p).exists():
            files_to_upload.append(Path(meta_p))
        
        uploaded_drive = upload_to_gdrive(files_to_upload, GDRIVE_RELEASE_FOLDER_ID, credentials_path)

    # 2. Webhooks bestimmen
    webhooks_to_call = []
    if webhook_urls:
        webhooks_to_call = [u for u in webhook_urls if u]
    elif os.environ.get("DISCORD_WEBHOOK_URL"):
        webhooks_to_call = [os.environ.get("DISCORD_WEBHOOK_URL")]
    else:
        # Default Webhooks aus Konfiguration
        from config import DISCORD_WEBHOOK_OIDA, DISCORD_WEBHOOK_WONG
        webhooks_to_call = [w for w in (DISCORD_WEBHOOK_OIDA, DISCORD_WEBHOOK_WONG) if w]

    posted_ok = 0
    posted_fail = 0

    if webhooks_to_call:
        log_fn(f"📡 [PUBX] Sende Webhook(s) an {len(webhooks_to_call)} Endpunkt(e)...")
        for wh_url in webhooks_to_call:
            tag = "Oi.Da" if "1551732581471621122" in wh_url else ("WONG" if "1550973113100140687" in wh_url else "Custom")
            log_fn(f"  🚀 Dispatching Setcard & Meta Asset an [{tag}]...")
            ok = send_discord_webhook(bundle, wh_url, attach_files=True)
            if ok:
                posted_ok += 1
            else:
                posted_fail += 1

    return {
        "success": True,
        "track_title": bundle.get("track_title"),
        "release_id": bundle.get("release_id"),
        "isrc": bundle.get("isrc"),
        "upc": bundle.get("upc"),
        "setcard_file": setcard_p,
        "meta_file": meta_p,
        "audio_path": audio_p,
        "video_path": str(video_path.resolve()),
        "gdrive_folder_url": bundle.get("gdrive_folder_url"),
        "discord_posted": posted_ok > 0,
        "webhooks_sent": posted_ok,
        "webhooks_failed": posted_fail,
        "bundle": bundle
    }

def find_all_rendered_videos(search_root: Path) -> list[Path]:
    """Finds all non-chunk rendered music videos across the music folder."""
    found = []
    if not search_root.exists():
        return found
    for p in search_root.rglob("*.mp4"):
        # Ignore chunk directories, temp files, and raw clips
        parts = [part.lower() for part in p.parts]
        if any("chunk" in part or "_tmp" in part or "_raw" in part for part in parts):
            continue
        if p.name.startswith("seg_") or p.name.startswith("chunk"):
            continue
        if p.stat().st_size > 5 * 1024 * 1024:  # > 5MB
            found.append(p)
    found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return found

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Drive & Discord Publisher")
    parser.add_argument("--video", type=str, help="Pfad zum gerenderten Video (.mp4)")
    parser.add_argument("--batch", action="store_true", help="Alle gerenderten Videos im Batch verarbeiten")
    parser.add_argument("--webhook", type=str, help="Discord Webhook URL")
    parser.add_argument("--credentials", type=str, help="Pfad zu credentials.json / Service Account")
    args = parser.parse_args()

    root_music = Path(r"J:\Oidasheim\Musik\FAVs")

    if args.batch:
        videos_to_process = find_all_rendered_videos(root_music)
        print(f"🔍 Batch-Modus aktiv: {len(videos_to_process)} gerenderte Videos gefunden.")
    elif args.video:
        videos_to_process = [Path(args.video)]
    else:
        # Default to most recent video in 16zu9
        default_dir = root_music / "ALT + F4" / "16zu9"
        videos = sorted(default_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not videos:
            videos = find_all_rendered_videos(root_music)
        if not videos:
            print("Keine MP4-Dateien gefunden.")
            sys.exit(1)
        videos_to_process = [videos[0]]

    webhooks_to_call = []
    if args.webhook:
        webhooks_to_call = [args.webhook]
    elif os.environ.get("DISCORD_WEBHOOK_URL"):
        webhooks_to_call = [os.environ.get("DISCORD_WEBHOOK_URL")]
    else:
        webhooks_to_call = [DISCORD_WEBHOOK_OIDA, DISCORD_WEBHOOK_WONG]

    for i, video_p in enumerate(videos_to_process, 1):
        print(f"\n[{i}/{len(videos_to_process)}] 📦 Verarbeite: {video_p.name}")
        bundle = build_release_bundle(video_p)
        print(f"  ✅ Setcard erstellt: {bundle['setcard_file']}")
        print(f"  ✅ Meta-Asset erstellt: {bundle['meta_file']}")

        # Google Drive Upload: Video + Mastered MP3 + Setcard + Meta Asset
        files_to_upload = [video_p, Path(bundle['setcard_file']), Path(bundle['meta_file'])]
        if bundle.get("audio_path") and Path(bundle["audio_path"]).exists():
            files_to_upload.insert(1, Path(bundle["audio_path"]))
            print(f"  🎵 Mastered MP3 hinzugefügt: {Path(bundle['audio_path']).name}")

        upload_to_gdrive(files_to_upload, GDRIVE_RELEASE_FOLDER_ID, args.credentials)

        for wh_url in webhooks_to_call:
            tag = "Oi.Da" if "1551732581471621122" in wh_url else ("WONG" if "1550973113100140687" in wh_url else "Custom")
            print(f"  📡 Sende Discord Webhook an [{tag} #exec-la-bat]...")
            send_discord_webhook(bundle, wh_url)

    print(f"\n✨ Fertig: {len(videos_to_process)} Release-Pakete bereitgestellt!")


