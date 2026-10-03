"""
clip_vision_tagger.py -- Ergaenzt clip_pool.py um ECHTE visuelle Content-Tags
via CLIP Zero-Shot-Klassifikation gegen config.TAG_VOCAB, fuer Clips deren
Tag-Vektor nach der reinen Dateiname-/Ordner-Analyse (clip_pool._tags_from_path)
leer geblieben ist.

Diagnose (siehe Chat): 97% des 32k-Clip-Pools hat KEINE auswertbaren
Dateinamen/Ordner-Hinweise (v.a. der 20260714_Grok_*-Batch, 64% des Pools,
99.5% davon leer) -> "semantisches Matching" degradiert dort silent zu
reinem Energie-/Motion-Matching. Dieses Skript ersetzt die fehlenden
Datei-basierten Tags durch Tags, die direkt aus den Clip-BILDERN erkannt
werden (CLIP-Bild-Encoder + Zero-Shot gegen dieselbe TAG_VOCAB).

Laeuft komplett ADDITIV zu clip_pool.py:
  - liest/schreibt denselben flat-globe Cache (db.load_flat_globe/save_flat_globe)
  - veraendert NUR Clips mit leerem Tag-Vektor (bereits gut getaggte Clips
    werden nicht angefasst)
  - markiert bearbeitete Eintraege mit "vision_tagged": VISION_TAG_VERSION,
    ein Re-Run verarbeitet dadurch nur neue/ungetaggte Clips (resumable)
  - inkrementelles Speichern alle --save-every Clips (Fortschritt uebersteht
    Abbruch/Neustart, gleiches atomares Save wie db.save_flat_globe sonst auch)
  - der neue Tag-Vektor nutzt dieselbe build_tag_vector()-Funktion wie
    mp3_scanner/clip_pool -> KEINE Aenderung an semantic_matching.py oder
    timeline_builder.py noetig, die Clips werden einfach "sichtbarer" fuer
    die bestehende Matching-Logik.

Nutzung:
    python clip_vision_tagger.py --calibrate          # Scores fuer wenige Clips ansehen
    python clip_vision_tagger.py --limit 200           # Testlauf
    python clip_vision_tagger.py                       # voller Lauf (alle ungetaggten Clips)
"""
import argparse
import random
import time

import cv2
import numpy as np
import open_clip
import torch
from PIL import Image

import db
from clip_pool import _ffprobe_duration, _sample_frames
from config import TAG_VOCAB
from mp3_scanner import build_tag_vector

VISION_TAG_VERSION = 1
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
TEMPLATES = ["a photo of {}", "a video frame showing {}", "{}"]
DEFAULT_THRESHOLD = 0.24
MAX_TAGS_PER_CLIP = 10


def _clip_vector_is_empty(vec) -> bool:
    return not vec or not any(vec)


def load_model(device: str):
    print(f"[clip_vision_tagger] lade {MODEL_NAME} ({PRETRAINED}) auf {device} ...")
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    model = model.to(device).eval()
    if device == "cuda":
        model = model.half()
    return model, tokenizer, preprocess


def build_text_features(model, tokenizer, device):
    with torch.no_grad():
        all_feats = []
        for tag in TAG_VOCAB:
            prompts = [t.format(tag) for t in TEMPLATES]
            tokens = tokenizer(prompts).to(device)
            feats = model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            avg = feats.mean(dim=0)
            avg = avg / avg.norm()
            all_feats.append(avg)
        stacked = torch.stack(all_feats)
        if device == "cuda":
            stacked = stacked.half()
        return stacked


def frames_to_batch(frames, preprocess, device):
    images = []
    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        images.append(preprocess(Image.fromarray(rgb)))
    batch = torch.stack(images).to(device)
    if device == "cuda":
        batch = batch.half()
    return batch


def score_clip(frames, model, preprocess, text_features, device):
    """Gibt (tag, max_similarity) fuer ALLE TAG_VOCAB-Eintraege zurueck,
    absteigend sortiert -- fuer Kalibrierung/Debug. Fuer den eigentlichen
    Tag-Run wird daraus per Threshold gefiltert."""
    if not frames:
        return []
    batch = frames_to_batch(frames, preprocess, device)
    with torch.no_grad():
        image_features = model.encode_image(batch)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        sims = image_features @ text_features.T  # [frames, tags]
    max_sim, _ = sims.max(dim=0)
    scored = list(zip(TAG_VOCAB, max_sim.float().cpu().tolist()))
    scored.sort(key=lambda x: -x[1])
    return scored


def run_calibration(device, sample_size=6):
    globe = db.load_flat_globe()
    candidates = [p for p, m in globe.items()
                  if isinstance(m, dict) and not m.get("failed")
                  and _clip_vector_is_empty(m.get("vector"))]
    random.seed(42)
    sample = random.sample(candidates, min(sample_size, len(candidates)))

    model, tokenizer, preprocess = load_model(device)
    text_features = build_text_features(model, tokenizer, device)

    for path in sample:
        meta = globe[path]
        duration = meta.get("duration") or _ffprobe_duration(path)
        frames = _sample_frames(path, duration, samples=8)
        scored = score_clip(frames, model, preprocess, text_features, device)
        print(f"\n{path}")
        if not scored:
            print("  (keine Frames lesbar)")
            continue
        for tag, sim in scored[:10]:
            print(f"  {sim:.3f}  {tag}")


def run_tagging(device, limit, threshold, save_every):
    globe = db.load_flat_globe()
    todo = [p for p, m in globe.items()
            if isinstance(m, dict) and not m.get("failed")
            and m.get("vision_tagged") != VISION_TAG_VERSION
            and _clip_vector_is_empty(m.get("vector"))]
    if limit:
        todo = todo[:limit]
    print(f"[clip_vision_tagger] {len(todo)} Clips ohne Vokabular-Treffer zu taggen "
          f"(threshold={threshold}, device={device})")
    if not todo:
        return

    model, tokenizer, preprocess = load_model(device)
    text_features = build_text_features(model, tokenizer, device)

    t0 = time.time()
    processed = 0
    tagged_count = 0
    failed_count = 0
    for path in todo:
        meta = globe[path]
        duration = meta.get("duration") or _ffprobe_duration(path)
        try:
            frames = _sample_frames(path, duration, samples=8)
            scored = score_clip(frames, model, preprocess, text_features, device)
        except Exception as e:
            print(f"  FEHLER bei {path}: {type(e).__name__}: {e}")
            scored = []
            failed_count += 1

        vision_tags = [tag for tag, sim in scored if sim >= threshold][:MAX_TAGS_PER_CLIP]
        if vision_tags:
            merged_tags = sorted(set((meta.get("tags") or []) + vision_tags))
            meta["tags"] = merged_tags
            meta["vector"] = build_tag_vector(merged_tags)
            meta["objects"] = [t for t in merged_tags if t not in TAG_VOCAB]
            content_summary = ", ".join(vision_tags)
            old_desc = meta.get("description") or ""
            if "[CLIP-vision]" not in old_desc:
                meta["description"] = f"[CLIP-vision] {content_summary} | {old_desc}"
            tagged_count += 1
        meta["vision_tagged"] = VISION_TAG_VERSION
        processed += 1

        if processed % save_every == 0:
            db.save_flat_globe(globe)
            elapsed = time.time() - t0
            rate = processed / elapsed
            remaining_min = (len(todo) - processed) / max(rate, 0.001) / 60
            print(f"  {processed}/{len(todo)}  neu getaggt={tagged_count}  "
                  f"fehler={failed_count}  {rate:.2f} clips/s  ETA {remaining_min:.1f} min")

    db.save_flat_globe(globe)
    total_min = (time.time() - t0) / 60
    print(f"[clip_vision_tagger] FERTIG: {processed} verarbeitet, {tagged_count} neu getaggt, "
          f"{failed_count} Fehler, {total_min:.1f} min")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true",
                         help="Zeigt Top-10-Score je Clip fuer ein paar Beispiele, taggt nichts.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--save-every", type=int, default=100)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if args.calibrate:
        run_calibration(device)
    else:
        run_tagging(device, args.limit, args.threshold, args.save_every)


if __name__ == "__main__":
    main()
