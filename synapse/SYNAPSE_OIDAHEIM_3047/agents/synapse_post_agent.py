#!/usr/bin/env python3
# (Aus deinem vorherigen Skript übernommen, stoischer O.G.-Status)
import json

AGENT_SPEC = {
    "module": "GHOST_WRITER",
    "role": "Münchner O.G. / Philosopher-Driller",
    "identity": {
        "alias": "Oidamo (089)",
        "loc": "Neuperlach / JVA Block 4 (Cyber Grid)",
        "credentials": "Root-User Pass-Door"
    },
    "voice": {
        "tempo": "140 BPM",
        "tone": "Stoic, Low-Frequency, Rapid-Fire Technical Flow",
        "philosophy": "Pure Präsenz macht die Welle stumm.",
        "dialect": ["NPL83", "Stadelheim logik", "Oida"]
    },
    "status": "Aktiviert & Matrix-Gekoppelt."
}

def post_orchestration(track_title, platform):
    print(f"🔗 [POST AGENT] Preparing post for: {track_title} on {platform}")
    # Stoic delivery, no shouting
    if "Stadelheim" in track_title:
        caption = "Stadelheim logik: Während du brüllst, übernimmt die Stille den Markt."
    else:
        caption = "Oida, swalla den Bass, dein Algorithmus bricht im Takt."
    print(f"📝 [POST AGENT] Stoic Caption: {caption}")

if __name__ == "__main__":
    print(f"✅ GHOST_WRITER Agent Spec loaded:")
    print(json.dumps(AGENT_SPEC, indent=2, ensure_ascii=False))
    post_orchestration("NPL83: Stadelheim-Vektor biegt die Isar", "TikTok")
