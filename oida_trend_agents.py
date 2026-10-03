from pathlib import Path

base = Path("/mnt/data/oida_viral_grid.py")
new = Path("/mnt/data/oida_trend_agents.py")

script = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OIDA TREND AGENT NETWORK
========================
Multi-agent trend/prognosis layer for the Oida Viral Grid.

Agents:
  US, UK, ESP, FR, IT, POL, RUS, DE_MAINSTREAM, DE_UNDERGROUND, REST_OF_WORLD

Each agent has:
- regional trend vocabulary
- search queries
- sound/culture signals
- local-vs-global balance
- underground/mainstream weighting
- forecast horizon: 7 / 30 / 90 days
- confidence and explainable reasons

The network does NOT claim that web trends predict virality with certainty.
It produces comparative signals that are fed into the local track scores.

Usage:
  python oida_trend_agents.py --root "J:\\Oidasheim\\Musik\\FAVs"
  python oida_trend_agents.py --root "J:\\Oidasheim\\Musik\\FAVs" --out "oida_viral_output"
  python oida_trend_agents.py --watch --interval 21600

Recommended:
  install mutagen for MP3 tags:
      pip install mutagen
"""

from __future__ import annotations
import argparse, hashlib, html, json, math, re, time
import urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None

DEFAULT_ROOT = Path(r"J:\Oidasheim\Musik\FAVs")
DEFAULT_OUT = Path("oida_viral_output")

# ---------------------------------------------------------------------------
# AGENT DEFINITIONS
# ---------------------------------------------------------------------------

AGENTS = {
    "US": {
        "name": "US Rap Agent",
        "locale": "US",
        "weight": 1.00,
        "queries": [
            "US rap trends 2026 underground hip hop",
            "US rap TikTok trends 2026",
            "SoundCloud rap trends 2026 US",
            "Atlanta rap underground 2026",
            "New York underground rap 2026",
            "jerk rap 2026 US",
        ],
        "terms": {
            "jerk":1.6,"rage":1.2,"plugg":1.1,"underground":1.4,
            "soundcloud":1.2,"atlanta":1.0,"new york":1.0,"detroit":1.0,
            "pluggnb":1.1,"opium":.8,"experimental":1.1,"cloud rap":1.0,
            "meme":1.2,"short-form":1.0,"tiktok":1.0,"808":.7,
        },
        "signals": ["jerk","plugg","rage","experimental","soundcloud","meme"],
        "locality": ["atlanta","new york","detroit","los angeles","dmv"],
    },
    "UK": {
        "name": "UK Rap Agent",
        "locale": "UK",
        "weight": 1.05,
        "queries": [
            "UK rap trends 2026 underground",
            "UK underground rap 2026 SoundCloud",
            "UK drill grime garage rap 2026 trends",
            "UK jerk rap 2026",
            "UK rap TikTok 2026",
        ],
        "terms": {
            "uk underground":1.7,"jerk":1.5,"grime":1.2,"drill":1.1,
            "uk garage":1.3,"garage":1.2,"soundcloud":1.4,"alternative":1.0,
            "electropop":1.0,"bassline":1.0,"club":.9,"syncopated":1.1,
            "cross-scene":1.2,"underground":1.4,
        },
        "signals": ["jerk","grime","drill","uk garage","soundcloud","club"],
        "locality": ["london","manchester","birmingham","south london"],
    },
    "ESP": {
        "name": "Spanish Rap Agent",
        "locale": "ES",
        "weight": .95,
        "queries": [
            "Spanish rap trends 2026 underground urbano",
            "Spain rap TikTok trends 2026",
            "Madrid Barcelona rap underground 2026",
            "Spanish trap drill rap 2026",
            "hip hop español nuevos sonidos 2026",
        ],
        "terms": {
            "urbano":1.4,"trap":1.0,"drill":1.0,"reggaeton":1.1,
            "jerk":.8,"underground":1.2,"madrid":.8,"barcelona":.8,
            "flamenco":1.1,"club":.9,"tiktok":1.0,"viral":1.0,
        },
        "signals": ["urbano","trap","drill","reggaeton","flamenco","club"],
        "locality": ["madrid","barcelona","sevilla"],
    },
    "FR": {
        "name": "French Rap Agent",
        "locale": "FR",
        "weight": 1.00,
        "queries": [
            "French rap trends 2026 underground",
            "rap français tendances 2026 underground",
            "French rap TikTok viral 2026",
            "Paris rap underground 2026",
            "French drill rap trends 2026",
        ],
        "terms": {
            "rap français":1.5,"underground":1.3,"drill":1.0,"afro":1.0,
            "club":1.0,"tiktok":1.0,"viral":1.1,"electro":1.0,
            "paris":.7,"new wave":1.2,"rap":.5,
        },
        "signals": ["new wave","club","drill","afro","electro","viral"],
        "locality": ["paris","marseille","lyon"],
    },
    "IT": {
        "name": "Italian Rap Agent",
        "locale": "IT",
        "weight": .90,
        "queries": [
            "Italian rap trends 2026 underground",
            "rap italiano 2026 underground nuovi suoni",
            "Italian trap drill rap TikTok 2026",
            "Milan Rome underground rap 2026",
        ],
        "terms": {
            "rap italiano":1.5,"trap":1.0,"drill":1.0,"urban":1.0,
            "club":1.0,"tiktok":1.1,"viral":1.0,"milano":.7,
            "napoli":.7,"new wave":1.0,"underground":1.3,
        },
        "signals": ["trap","drill","club","new wave","urban","viral"],
        "locality": ["milano","roma","napoli"],
    },
    "POL": {
        "name": "Polish Rap Agent",
        "locale": "PL",
        "weight": .85,
        "queries": [
            "Polish rap trends 2026 underground",
            "polski rap 2026 underground nowe brzmienie",
            "Polish trap drill rap TikTok 2026",
            "Warsaw underground rap 2026",
        ],
        "terms": {
            "polski rap":1.5,"trap":1.0,"drill":1.0,"underground":1.4,
            "tiktok":1.1,"viral":1.0,"club":.9,"new wave":1.0,
            "warsaw":.7,"warszawa":.7,"experimental":1.0,
        },
        "signals": ["new wave","experimental","trap","drill","club","viral"],
        "locality": ["warsaw","warszawa","krakow","kraków"],
    },
    "RUS": {
        "name": "Russian Rap Agent",
        "locale": "RU",
        "weight": .75,
        "queries": [
            "Russian rap trends 2026 underground",
            "русский рэп тренды 2026 андеграунд",
            "Russian rap TikTok 2026",
            "Moscow underground rap 2026",
            "Russian trap drill rap 2026",
        ],
        "terms": {
            "underground":1.3,"trap":1.0,"drill":1.0,"cloud":1.0,
            "experimental":1.1,"tiktok":1.0,"viral":1.0,"club":.9,
            "moscow":.7,"moscow":.7,"new wave":1.0,
        },
        "signals": ["experimental","trap","drill","cloud","club","viral"],
        "locality": ["moscow","moskva","st petersburg"],
    },
    "DE_MAINSTREAM": {
        "name": "Deutschrap Mainstream Agent",
        "locale": "DE",
        "weight": 1.25,
        "queries": [
            "Deutschrap Charts Trends 2026",
            "Deutschrap TikTok viral 2026",
            "Deutschrap Hits 2026 Spotify",
            "deutscher Rap Mainstream Trends 2026",
            "German rap new releases 2026",
        ],
        "terms": {
            "deutschrap":1.6,"charts":1.3,"viral":1.4,"tiktok":1.3,
            "spotify":1.0,"hook":1.1,"melodic":1.0,"trap":.9,
            "pop":.9,"mainstream":1.3,"newcomer":1.2,"berlin":.8,
            "hamburg":.7,"frankfurt":.7,"münchen":.9,"089":1.2,
        },
        "signals": ["hook","viral","tiktok","melodic","newcomer","charts"],
        "locality": ["berlin","hamburg","frankfurt","münchen","köln"],
    },
    "DE_UNDERGROUND": {
        "name": "Deutschrap Underground Agent",
        "locale": "DE",
        "weight": 1.40,
        "queries": [
            "Deutschrap Underground 2026 OFFCULT",
            "German underground rap 2026 SoundCloud",
            "Deutschrap New Wave 2026 underground",
            "German rap experimental 2026",
            "München 089 underground rap 2026",
            "German alternative rap 2026",
        ],
        "terms": {
            "underground":1.8,"offcult":1.7,"new wave":1.5,"soundcloud":1.5,
            "experimental":1.4,"alternative":1.3,"independent":1.3,
            "boom bap":1.1,"jerk":1.2,"glitch":1.1,"club":1.0,
            "münchen":1.0,"089":1.4,"minga":1.5,"oida":1.5,
            "absurd":1.1,"meme":1.3,"DIY":1.2,
        },
        "signals": ["underground","new wave","experimental","089","minga","oida","meme"],
        "locality": ["münchen","089","berlin","hamburg","köln"],
    },
    "REST": {
        "name": "Best of Rest of World Agent",
        "locale": "GLOBAL",
        "weight": .80,
        "queries": [
            "global hip hop trends 2026 underground",
            "global rap new wave 2026",
            "African rap trends 2026",
            "Latin rap trends 2026",
            "Asian underground hip hop trends 2026",
            "global TikTok rap trends 2026",
        ],
        "terms": {
            "afro":1.2,"amapiano":1.0,"afrobeats":1.2,"latin":1.0,
            "reggaeton":1.0,"jerk":1.0,"new wave":1.3,"club":1.1,
            "experimental":1.2,"underground":1.3,"tiktok":1.0,
            "global":.8,"cross-border":1.2,
        },
        "signals": ["new wave","club","afro","latin","experimental","cross-border"],
        "locality": ["lagos","johannesburg","mexico city","seoul","tokyo"],
    },
}

# ---------------------------------------------------------------------------
# WEB RESEARCH
# ---------------------------------------------------------------------------

UA = "Mozilla/5.0 OidaTrendAgentNetwork/1.0"

def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def search_web(query, limit=5):
    # DuckDuckGo HTML is used as a lightweight public search fallback.
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        text = fetch(url)
    except Exception:
        return []
    hits=[]
    for m in re.finditer(r'nuddg=([^&"]+)', text):
        u=urllib.parse.unquote(m.group(1))
        if u.startswith("http"):
            hits.append(u)
    return list(dict.fromkeys(hits))[:limit]

def page_signal(url, agent):
    try:
        text=fetch(url, timeout=8)
        low=text.lower()
        found={}
        for term,w in agent["terms"].items():
            c=low.count(term.lower())
            if c:
                found[term]=min(c,20)
        return {"url":url,"ok":True,"found":found}
    except Exception as e:
        return {"url":url,"ok":False,"error":str(e)}

def run_agent(agent_id, cfg):
    started=time.time()
    pages=[]
    all_counts=Counter()
    query_results=[]
    for q in cfg["queries"]:
        urls=search_web(q, limit=4)
        query_results.append({"query":q,"urls":urls})
        for u in urls:
            result=page_signal(u,cfg)
            pages.append(result)
            for term,c in result.get("found",{}).items():
                all_counts[term]+=c

    weighted=sum(min(c,10)*cfg["terms"].get(term,.5)
                 for term,c in all_counts.items())
    denom=max(10,len(cfg["queries"])*8)
    base=min(1.0,weighted/denom)

    signal_scores={}
    for term in cfg["signals"]:
        signal_scores[term]=min(1.0, all_counts.get(term,0)/5)

    reasons=[]
    top=all_counts.most_common(8)
    for term,c in top[:5]:
        reasons.append(f"{term} x{c}")

    return {
        "agent_id":agent_id,
        "name":cfg["name"],
        "locale":cfg["locale"],
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "runtime_sec":round(time.time()-started,2),
        "trend_score":round(base,4),
        "signal_scores":signal_scores,
        "top_terms":dict(top),
        "reasons":reasons,
        "pages":pages,
        "queries":query_results,
        "confidence":round(min(.95,.35 + .08*len(pages) + .10*min(1,base)),3),
        "forecast":{
            "7d":round(min(1,base*1.00),3),
            "30d":round(min(1,base*1.05),3),
            "90d":round(min(1,base*.95),3),
        }
    }

# ---------------------------------------------------------------------------
# LOCAL TRACK MATCHING
# ---------------------------------------------------------------------------

def normalize(x):
    x=str(x or "").lower()
    x=re.sub(r"[^a-z0-9äöüßа-яё]+"," ",x)
    return re.sub(r"\s+"," ",x).strip()

def load_html_tracks(root):
    # Minimal parser: reads text from Traktor exports. Existing grid script
    # remains responsible for deep table parsing; this layer focuses on agent
    # matching and can consume its generated CSV when available.
    import csv
    csvs=sorted(root.glob("oida_viral_output/song_grid_v*.csv"))
    if not csvs:
        csvs=sorted(Path("oida_viral_output").glob("song_grid_v*.csv"))
    if not csvs:
        return []
    latest=csvs[-1]
    with latest.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def match_agent(track, cfg, report):
    text=normalize(" ".join([
        track.get("title",""),track.get("artist",""),track.get("genre",""),
        track.get("comment",""),track.get("lyrics","")
    ]))
    scores=[]
    for term,w in cfg["terms"].items():
        if normalize(term) in text:
            global_count=report.get("top_terms",{}).get(term,0)
            scores.append(w*(1+min(global_count,5)/10))
    return min(1.0,sum(scores)/max(2,len(cfg["signals"])))

# ---------------------------------------------------------------------------
# NETWORK SYNTHESIS
# ---------------------------------------------------------------------------

def synthesize(reports):
    total_weight=sum(AGENTS[a]["weight"] for a in reports)
    weighted=sum(r["trend_score"]*AGENTS[r["agent_id"]]["weight"] for r in reports)
    global_score=weighted/max(.01,total_weight)

    ranked=sorted(reports,key=lambda r:r["trend_score"],reverse=True)
    cross=[]
    for r in ranked:
        cross.append({
            "agent":r["agent_id"],
            "score":r["trend_score"],
            "confidence":r["confidence"],
            "top_terms":r["top_terms"],
        })

    return {
        "network_score":round(global_score,4),
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "ranked_agents":cross,
        "consensus":round(
            sum(r["trend_score"] for r in reports)/max(1,len(reports)),4),
        "forecast_timeline":{
            "7d":round(sum(r["forecast"]["7d"]*AGENTS[r["agent_id"]]["weight"] for r in reports)/max(.01,total_weight),4),
            "30d":round(sum(r["forecast"]["30d"]*AGENTS[r["agent_id"]]["weight"] for r in reports)/max(.01,total_weight),4),
            "90d":round(sum(r["forecast"]["90d"]*AGENTS[r["agent_id"]]["weight"] for r in reports)/max(.01,total_weight),4),
        }
    }

def build_dashboard(reports, network, tracks, out):
    version=1
    old=list(out.glob("trend_agents_v*.html"))
    if old:
        nums=[int(x.stem.split("_v")[-1]) for x in old if x.stem.split("_v")[-1].isdigit()]
        version=max(nums,default=0)+1

    rows=[]
    for r in network["ranked_agents"]:
        rr=next(x for x in reports if x["agent_id"]==r["agent"])
        rows.append(f"""
        <tr><td><b>{html.escape(r['agent'])}</b><br>{html.escape(r['agent'])}</td>
        <td>{r['score']:.3f}</td><td>{r['confidence']:.2f}</td>
        <td>{html.escape(', '.join(f"{k} ({v})" for k,v in list(r['top_terms'].items())[:10]))}</td>
        <td>{html.escape('; '.join(rr['reasons']))}</td></tr>""")

    track_rows=[]
    for t in tracks[:1000]:
        vals=[]
        for aid,cfg in AGENTS.items():
            # use report matching
            rep=next((x for x in reports if x["agent_id"]==aid),None)
            vals.append((aid,match_agent(t,cfg,rep or {})))
        vals.sort(key=lambda x:x[1],reverse=True)
        top=", ".join(f"{a}:{s:.2f}" for a,s in vals[:4])
        track_rows.append(f"<tr><td>{html.escape(t.get('title',''))}</td><td>{html.escape(t.get('artist',''))}</td><td>{html.escape(top)}</td></tr>")

    payload=html.escape(json.dumps({"reports":reports,"network":network},ensure_ascii=False))

    page=f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>Oida Trend Agent Network v{version:03d}</title>
<style>
body{{background:#101114;color:#eee;font-family:system-ui;margin:0}}
header,.box{{padding:20px;background:#191c22;margin:12px;border-radius:14px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #30343d;text-align:left}}
th{{background:#252a33;position:sticky;top:0}}small{{color:#aaa}} a{{color:#72b8ff}}
.score{{font-size:42px;font-weight:900}}
</style></head><body>
<header><h1>OIDA TREND AGENT NETWORK · v{version:03d}</h1>
<p>{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}</p>
<div class="score">{network['network_score']:.3f}</div>
<p>Consensus · 7d {network['forecast_timeline']['7d']:.3f}
· 30d {network['forecast_timeline']['30d']:.3f}
· 90d {network['forecast_timeline']['90d']:.3f}</p></header>

<div class="box"><h2>Agent Radar</h2><table>
<tr><th>Agent</th><th>Trend</th><th>Confidence</th><th>Top Signals</th><th>Interpretation</th></tr>
{''.join(rows)}</table></div>

<div class="box"><h2>Track × Agent Matrix</h2><table>
<tr><th>Track</th><th>Artist</th><th>Best regional fits</th></tr>
{''.join(track_rows)}</table></div>

<div class="box"><h2>Agent Mission</h2>
<p>Jeder Agent sucht seine eigene Szene, statt US/UK-Muster blind auf Deutschrap zu übertragen.
Der DE-Underground-Agent bekommt bewusst ein höheres Gewicht, damit frühe New-Wave-/DIY-Signale
nicht von Mainstream-Charts plattgebügelt werden.</p>
</div>
<script type="application/json" id="data">{payload}</script>
</body></html>"""
    fn=out/f"trend_agents_v{version:03d}.html"
    fn.write_text(page,encoding="utf-8")
    return fn

def run(root,out):
    out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for aid,cfg in AGENTS.items():
        print(f"[AGENT] {aid} ...")
        reports.append(run_agent(aid,cfg))
    network=synthesize(reports)

    tracks=load_html_tracks(root)
    dashboard=build_dashboard(reports,network,tracks,out)

    state={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "agents":reports,
        "network":network,
    }
    statefile=out/"trend_agent_state.json"
    statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")

    # Human-readable forecast
    forecast=out/"trend_forecast.md"
    lines=[
        "# Oida Trend Forecast",
        "",
        f"Network score: {network['network_score']:.3f}",
        f"Consensus: {network['consensus']:.3f}",
        "",
        "## Timeline",
        *[f"- {k}: {v:.3f}" for k,v in network["forecast_timeline"].items()],
        "",
        "## Agent ranking",
    ]
    for r in network["ranked_agents"]:
        lines.append(f"- **{r['agent']}** — {r['score']:.3f} — confidence {r['confidence']:.2f} — {', '.join(r['top_terms'].keys())}")
    forecast.write_text("\n".join(lines),encoding="utf-8")

    print(f"[OIDA] Dashboard: {dashboard}")
    print(f"[OIDA] State:     {statefile}")
    print(f"[OIDA] Forecast:  {forecast}")
    return dashboard

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=str(DEFAULT_ROOT))
    ap.add_argument("--out",default=str(DEFAULT_OUT))
    ap.add_argument("--watch",action="store_true")
    ap.add_argument("--interval",type=int,default=21600)
    args=ap.parse_args()
    root=Path(args.root); out=Path(args.out)
    while True:
        try:
            run(root,out)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[OIDA] ERROR:",e)
        if not args.watch:
            break
        time.sleep(max(60,args.interval))

if __name__=="__main__":
    main()
'''

new.write_text(script, encoding="utf-8")
print(new)
