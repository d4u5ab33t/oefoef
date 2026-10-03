#!/usr/bin/env python3
"""
viral-strategy.py — Viral-Planer für Releases.

Subcommands:
    hook           Generiert Hook-Vorschläge aus 6 Frameworks
    hashtags       Hashtag-Mix pro Plattform
    posting-times  Optimum-Posting-Zeit pro Plattform+Wochentag
    caption        Caption-Generator mit Hook-Formel
    brief          Komplettes Strategy-Brief für einen Release
    snapshot       Viral-Health-Check Report
"""
import argparse
import json
from pathlib import Path

from config import DEFAULT_HASHTAG_NICHE

HOOK_FRAMEWORKS = {
    "F1": "Punch-Drop: Frame 1 ruhig, Beat leise. Frame 2 (Drop): harter Cut, Visual-Explosion. Ideal für Drops, Beat-Hits.",
    "F2": "Vorher/Nachher: Linke Hälfte normal, rechte Hälfte mit deinem Track. Transformation, Energy-Boost, Confidence.",
    "F3": "POV / Story-Starter: 'POV: du hörst [Song] zum ersten Mal'. Lyrics-Hook, Aha-Momente.",
    "F4": "Nostalgie-Trap: '90s-Kinder werden diesen Beat erkennen'. Remixe, Genre-Fusion, Sample-Reveal.",
    "F5": "Tutorial-Dress: 'Wie man X macht' – mit Twist, der nur mit deinem Song Sinn ergibt. Comedy.",
    "F6": "Relatable Pain: Alltags-Moment, der nervt. Dein Song als Antwort. Empowerment, Herz-Schmerz.",
}

POSTING_TIMES = {
    "tiktok": {
        "mo": "19:00", "di": "12:00", "mi": "19:00", "do": "15:00",
        "fr": "19:00", "sa": "11:00", "so": "18:00"
    },
    "instagram": {
        "mo": "12:30", "di": None, "mi": "12:30", "do": "12:30",
        "fr": "19:00", "sa": "10:00", "so": None
    },
    "youtube": {
        "mo": None, "di": "17:00", "mi": None, "do": "17:00",
        "fr": "16:00", "sa": None, "so": None
    },
    "x": {
        "mo": "09:00", "di": "09:00", "mi": None, "do": "10:00",
        "fr": None, "sa": "11:00", "so": None
    },
}

HASHTAG_TIERS = {
    "breit": ["#foryou", "#viral", "#music", "#newsong", "#indiemusic", "#germanmusic", "#fy", "#fyp"],
    "nische_hiphop": ["#deutschrap", "#hiphop", "#rap", "#boombap", "#trap", "#undergroundhiphop", "#808bass", "#germanhiphop", "#90sboombap"],
    "nische_electronic": ["#ambient", "#techno", "#idm", "#experimental", "#modular"],
    "nische_indie": ["#indiefolk", "#dreampop", "#shoegaze"],
    "nische_soul": ["#neosoul", "#rnb", "#altRnB"],
}


def cmd_hook(args):
    print("\n🎬 HOOK-FRAMEWORKS (wähle 1 pro Clip)\n")
    for code, desc in HOOK_FRAMEWORKS.items():
        print(f"\n[{code}] {desc}")
    print("\nEmpfehlung pro Release:")
    print(" - Lead-Track: F1 Punch-Drop")
    print(" - Story/Intro: F3 POV-Starter")
    print(" - Reichweite: F2 Vorher/Nachher oder F6 Relatable Pain")
    print(" - Humor: F5 Tutorial-Dress")
    print(" - Sample-Hook: F4 Nostalgie-Trap")


def cmd_posting(args):
    print("\n📅 POSTING-TIMES (DE/EU)\n")
    days = ["mo", "di", "mi", "do", "fr", "sa", "so"]
    day_names = {"mo": "Mo", "di": "Di", "mi": "Mi", "do": "Do", "fr": "Fr", "sa": "Sa", "so": "So"}
    if args.platform:
        plats = [args.platform]
    else:
        plats = list(POSTING_TIMES.keys())
    for p in plats:
        print(f"\n{p.upper()}:")
        for d in days:
            t = POSTING_TIMES[p].get(d)
            if t:
                print(f"  {day_names[d]} {t}")


def cmd_hashtags(args):
    print(f"\n# HASHTAG-MIX für {args.platform or 'TikTok'}\n")
    breit = HASHTAG_TIERS["breit"][:2]
    nische = HASHTAG_TIERS.get(f"nische_{args.niche or DEFAULT_HASHTAG_NICHE}",
                                HASHTAG_TIERS["nische_hiphop"])[:3]
    marke = [f"#{args.label or 'label'}"]
    print("Breit:  " + " ".join(breit))
    print("Nische: " + " ".join(nische))
    print("Marke:  " + " ".join(marke))
    print()
    print("Beispiel-Post:")
    print(" ".join(breit + nische + marke))


def cmd_caption(args):
    hook = args.hook or "Was passiert, wenn du nachts um 3 das Tape umdrehst"
    body = args.body or "Erster Vorgeschmack auf den neuen Track."
    cta = args.cta or "Welche Stadt brennt bei euch? Comment 👇"
    print(f"\n📝 CAPTION-DRAFT\n")
    print(f"{hook}\n")
    print(f"{body}\n")
    print(f"{cta}\n")
    print(f"#foryou #newsong #{args.label or 'label'} #{args.artist or 'artist'}")


def cmd_brief(args):
    """Komplettes Strategy-Brief (CLI-Wrapper um build_brief())."""
    data = build_brief(args.artist, args.track, args.release, label=args.label or "label")
    _print_brief(data)


def _hook_framework_for_mood(mood_tags: list | None, slang: dict | list | None) -> str:
    """Wählt ein Hook-Framework passend zur gelernten Song-Semantik (siehe
    song_semantics.py: mood_tags/slang aus Traktor-Tracklisten-Lyrics) statt
    immer pauschal F1/F3 zu empfehlen wie der bisherige feste --brief-Text.
    Rein heuristisch/deterministisch, kein Ersatz für redaktionelle Auswahl."""
    tags = set(mood_tags or [])
    if tags & {"aggressive", "menacing", "chaotic", "drill", "industrial", "glitch", "cyber"}:
        return "F1"  # Punch-Drop: harte, energiegeladene Moods
    if tags & {"nostalgic", "boom-bap", "boom bap", "lo-fi", "lofi", "dreamy"}:
        return "F4"  # Nostalgie-Trap: passt zu retro-/warmen Moods
    if tags & {"playful", "sarcastic", "arrogant"}:
        return "F5"  # Tutorial-Dress/Comedy: passt zu verspielten Moods
    if slang:
        return "F3"  # POV/Story-Starter: eigene Slang-Welt trägt die Story
    return "F6"  # Relatable Pain: neutraler Default, wenn keine Song-Semantik vorliegt


def build_brief(artist: str, track: str, release: str, label: str = "label",
                mood_tags: list | None = None, slang: list | None = None,
                niche: str | None = None) -> dict:
    """Strukturierte Fassung von cmd_brief() — von main.py nach jedem Render
    aufrufbar, um automatisch ein Release-Strategy-Brief JSON neben dem
    fertigen Video abzulegen. mood_tags/slang kommen optional aus
    song_semantics.get_semantics_for_song() und steuern die Hook-Framework-
    Wahl; ohne sie fällt es auf den generischen Default (F6) zurück. `niche`
    ist der GELERNTE Katalog-Default aus learn_default_niche() (main.py) —
    wird nur verwendet, wenn die Mood-Tags DIESES Songs selbst zu keiner
    Nische passen."""
    hook_code = _hook_framework_for_mood(mood_tags, slang)
    resolved_niche = _niche_for_mood(mood_tags, fallback=niche or DEFAULT_HASHTAG_NICHE)
    breit = HASHTAG_TIERS["breit"][:2]
    nische = HASHTAG_TIERS.get(f"nische_{resolved_niche}", HASHTAG_TIERS["nische_hiphop"])[:3]
    marke = [f"#{label}"]
    return {
        "artist": artist, "track": track, "release": release, "label": label,
        "mood_tags": mood_tags or [], "slang": slang or [],
        "niche": resolved_niche,
        "hook_framework": hook_code,
        "hook_framework_desc": HOOK_FRAMEWORKS[hook_code],
        "platforms": {p: {"best_time": _best_time_for_platform(p), "schedule": POSTING_TIMES[p]}
                      for p in sorted(POSTING_TIMES)},
        "hashtags": {"breit": breit, "nische": nische, "marke": marke},
        "kpi_targets_4_weeks": {"creation_count": 1000, "virality_rate_pct": 5,
                                 "engagement_pct": 8, "pre_saves": 500},
        "timeline": {
            "t_minus_6_wochen": "Influencer-Outreach starten",
            "t_minus_4_wochen": "Pre-Save-Campaign live",
            "t_minus_2_wochen": "Snippet-Teaser (TikTok zuerst)",
            "t_minus_1_woche": "Street-Promo + Reels-Welle",
            "t_0": "Release-Day, alle Kanäle gleichzeitig",
            "t_plus_2_wochen": "Reporting, Lessons-Learned",
        },
    }


# Mood-Tags (aus song_semantics.py, Traktor-Tracklisten-Lyrics) je Nische,
# analog zu _hook_framework_for_mood().
NICHE_MOOD_MAP = {
    "hiphop":     {"aggressive", "drill", "boom-bap", "boom bap", "trap",
                    "gritty", "menacing", "chaotic", "arrogant", "hiphop", "rap",
                    "hardcore", "street", "freestyle", "cypher", "flow", "bars", "spit",
                    "808", "urban", "underground"},
    "indie":      {"dreamy", "nostalgic", "melancholic", "lofi", "lo-fi",
                    "acoustic", "sad"},
    "soul":       {"romantic", "soul", "warm", "smooth", "sensual"},
    "electronic": {"epic", "energetic", "intense", "party", "night", "dark",
                    "cyber", "glitch", "industrial", "uplifting", "chaotic"},
}


def _niche_for_mood(mood_tags: list | None, fallback: str | None = "hiphop") -> str | None:
    """Wählt die Hashtag-Nische (Schlüssel-Suffix für HASHTAG_TIERS[f"nische_{x}"])
    anhand der gelernten Mood-Tags EINES Songs. Bei fehlendem/mehrdeutigem
    Match wird `fallback` zurückgegeben (main.py reicht hier den gelernten
    Katalog-Default aus learn_default_niche() durch statt hart "electronic")."""
    tags = {t.lower() for t in (mood_tags or [])}
    best_niche, best_overlap = None, 0
    for niche, keywords in NICHE_MOOD_MAP.items():
        overlap = len(tags & keywords)
        if overlap > best_overlap:
            best_niche, best_overlap = niche, overlap
    return best_niche or fallback


def learn_default_niche(all_song_semantics: list[dict] | None) -> str:
    """Ermittelt die im Song-Katalog am häufigsten vertretene Hashtag-Nische
    aus den Mood-Tags ALLER bisher gelernten Songs (siehe song_semantics.py /
    db.get_all_song_semantics()) statt einer fest verdrahteten Genre-Annahme.
    Wächst mit dem Katalog: je mehr Songs mit Song-Semantik gescannt wurden,
    desto repräsentativer wird dieser Fallback für Songs OHNE eigene
    Mood-Tags. Ganz ohne Daten (leerer/neuer Katalog) fällt es auf
    config.DEFAULT_HASHTAG_NICHE zurück (per Env überschreibbar, kein
    Hardcode mehr im Code)."""
    from collections import Counter
    counts = Counter()
    for entry in (all_song_semantics or []):
        niche = _niche_for_mood(entry.get("mood_tags") or [], fallback=None)
        if niche:
            counts[niche] += 1
    if counts:
        return counts.most_common(1)[0][0]
    from config import DEFAULT_HASHTAG_NICHE
    return DEFAULT_HASHTAG_NICHE


def _hashtag_string(hashtags: dict) -> str:
    all_tags = hashtags.get("breit", []) + hashtags.get("nische", []) + hashtags.get("marke", [])
    return " ".join(all_tags)


def build_platform_metadata(artist: str, track: str, release: str, label: str,
                             platform: str, mood_tags: list | None = None,
                             slang: list | None = None, niche: str | None = None) -> dict:
    """Fertige Upload-Metadaten (Titel/Beschreibung/Tags) für EINE konkrete
    Plattform ("youtube" oder "tiktok"), abgeleitet aus derselben Song-
    Semantik/Hook-Logik wie build_brief(). Anders als build_brief() (ein
    menschenlesbares Strategy-Briefing über ALLE Plattformen) liefert diese
    Funktion strukturierte Felder für den DIREKTEN, automatisierten Import in
    Upload-/Scheduling-Tools (siehe main.py -> .metadata.json je Render +
    gesammelte platform-CSV). `niche` ist der GELERNTE Katalog-Default aus
    learn_default_niche() (main.py) — greift nur, wenn die Mood-Tags DIESES
    Songs selbst zu keiner Nische passen."""
    hook_code = _hook_framework_for_mood(mood_tags, slang)
    hook_desc = HOOK_FRAMEWORKS[hook_code]
    resolved_niche = _niche_for_mood(mood_tags, fallback=niche or DEFAULT_HASHTAG_NICHE)
    breit = HASHTAG_TIERS["breit"][:2]
    nische = HASHTAG_TIERS.get(f"nische_{resolved_niche}", HASHTAG_TIERS["nische_hiphop"])[:3]
    marke = [f"#{label}"]
    hashtags = {"breit": breit, "nische": nische, "marke": marke}
    hashtag_str = _hashtag_string(hashtags)

    if platform == "youtube":
        title = f"{artist} - {track} (Official Music Video)"
        description_lines = [f'{artist} - "{track}"', "", f"Released via {label}."]
        if mood_tags:
            description_lines.append(f"Mood: {', '.join(mood_tags)}")
        description_lines += ["", hashtag_str]
        description = "\n".join(description_lines)
        tags_field = [t.lstrip("#") for t in (breit + nische + [artist, track, label])]
    else:  # tiktok (dient auch als Basis für Instagram Reels)
        title = f"{track} 🔥"
        cta = "Welche Stadt brennt bei euch? 👇"
        description = f"{hook_desc.split(':')[0]}: {track} von {artist}\n{cta}\n{hashtag_str}"
        tags_field = breit + nische + marke  # bei TikTok bleiben # sichtbar/relevant

    best_time_platform = platform if platform in POSTING_TIMES else "tiktok"
    return {
        "platform": platform,
        "artist": artist,
        "track": track,
        "release": release,
        "label": label,
        "niche": resolved_niche,
        "hook_framework": hook_code,
        "title": title,
        "description": description,
        "tags": tags_field,
        "hashtags": hashtag_str,
        "best_post_time": _best_time_for_platform(best_time_platform),
    }


def _print_brief(data: dict):
    print(f"\n{'=' * 50}")
    print(f"🎯 VIRAL STRATEGY BRIEF")
    print(f"{'=' * 50}")
    print(f"\nArtist: {data['artist']}")
    print(f"Track:  {data['track']}")
    print(f"Release: {data['release']}")
    print(f"\n--- PLATTFORM-PLAN ---")
    for p in ["tiktok", "instagram", "youtube", "x"]:
        print(f"\n[{p.upper()}]")
        print(f"  Sweet-Spot: {data['platforms'][p]['schedule']}")
        print(f"  Frequency: 3–7 / Woche")
    print(f"\n--- HOOK-FRAMEWORK-WAHL ---")
    if data["mood_tags"] or data["slang"]:
        print(f"Mood={data['mood_tags'] or '–'} Slang={data['slang'] or '–'} "
              f"-> [{data['hook_framework']}] {data['hook_framework_desc']}")
    else:
        print(f"Empfehlung: F1 Punch-Drop (Lead), F3 POV (Story)")
    print(f"\n--- HASHTAG-MIX ---")
    print("  Breit:  " + " ".join(data["hashtags"]["breit"]))
    print("  Nische: " + " ".join(data["hashtags"]["nische"]))
    print("  Marke:  " + " ".join(data["hashtags"]["marke"]))
    print(f"\n--- KPI-ZIELE (4 Wochen) ---")
    kpi = data["kpi_targets_4_weeks"]
    print(f"  Creation-Count: ≥ {kpi['creation_count']}")
    print(f"  Virality-Rate:  ≥ {kpi['virality_rate_pct']} %")
    print(f"  Engagement:     ≥ {kpi['engagement_pct']} %")
    print(f"  Pre-Saves:      ≥ {kpi['pre_saves']}")
    print(f"\n--- TIMELINE ---")
    for label_key, desc in data["timeline"].items():
        print(f"  {label_key}: {desc}")
    print(f"\n{'=' * 50}\n")


def _best_time_for_platform(platform: str) -> str | None:
    schedule = POSTING_TIMES.get(platform, {})
    for day_key in ["mo", "di", "mi", "do", "fr", "sa", "so"]:
        value = schedule.get(day_key)
        if value:
            return value
    return None


def build_snapshot(args) -> dict:
    platform_name = args.platform or "tiktok"
    platforms = {}
    for pname in sorted(POSTING_TIMES):
        platform_info = {"best_time": _best_time_for_platform(pname), "schedule": POSTING_TIMES[pname]}
        platforms[pname] = platform_info

    resolved_niche = getattr(args, "niche", None) or DEFAULT_HASHTAG_NICHE
    breit = HASHTAG_TIERS["breit"][:2]
    nische = HASHTAG_TIERS.get(f"nische_{resolved_niche}", HASHTAG_TIERS["nische_hiphop"])[:3]
    marke = [f"#{args.label or 'label'}"]

    data = {
        "artist": args.artist,
        "track": args.track,
        "release": args.release,
        "label": args.label or "label",
        "niche": resolved_niche,
        "platform": platform_name,
        "platforms": platforms,
        "hashtags": {"breit": breit, "nische": nische, "marke": marke},
    }
    return data


def cmd_snapshot(args):
    data = build_snapshot(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Snapshot saved to {output_path}")
    return data


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    # hook
    sub.add_parser("hook").set_defaults(func=cmd_hook)

    # posting-times
    p2 = sub.add_parser("posting")
    p2.add_argument("--platform", choices=list(POSTING_TIMES.keys()))
    p2.set_defaults(func=cmd_posting)

    # hashtags
    p3 = sub.add_parser("hashtags")
    p3.add_argument("--platform")
    p3.add_argument("--niche")
    p3.add_argument("--label")
    p3.set_defaults(func=cmd_hashtags)

    # caption
    p4 = sub.add_parser("caption")
    p4.add_argument("--hook")
    p4.add_argument("--body")
    p4.add_argument("--cta")
    p4.add_argument("--artist")
    p4.add_argument("--label")
    p4.set_defaults(func=cmd_caption)

    # brief
    p5 = sub.add_parser("brief")
    p5.add_argument("--artist", required=True)
    p5.add_argument("--track", required=True)
    p5.add_argument("--release", required=True)
    p5.add_argument("--label", default="label")
    p5.set_defaults(func=cmd_brief)

    # snapshot
    p6 = sub.add_parser("snapshot")
    p6.add_argument("--artist", required=True)
    p6.add_argument("--track", required=True)
    p6.add_argument("--release", required=True)
    p6.add_argument("--label", default="label")
    p6.add_argument("--platform", default="tiktok", choices=list(POSTING_TIMES.keys()))
    p6.add_argument("--output", required=True)
    p6.set_defaults(func=cmd_snapshot)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()