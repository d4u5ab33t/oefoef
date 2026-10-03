# SYNAPSE AUDIO DYNAMICS

Lokales Skelett fuer das 5-Node-Label-System. Alle Nodes lesen/schreiben
eine zentrale `hive_mind.json`. Keine Cloud-Abhaengigkeiten im Default.

## Rollen (Nodes)

| Node  | Rolle                 | Datei            | Status        |
|-------|-----------------------|------------------|---------------|
| KAIRO | Production / Stems    | `kairo.py`       | Stub          |
| VEGA  | Mastering / Loudness  | `vega.py`        | Stub          |
| JINX  | Visuals / Social      | `jinx.py`        | Stub          |
| ORION | A&R / Promo / Sync    | `orion.py`       | Stub          |
| ATLAS | Buchhaltung / ROI     | `atlas.py`       | Stub          |
| CORE  | Orchestrator          | `core.py`        | aktiv         |

## Was ist echt lauffaehig

- `core.py` kann Hive-Mind laden, Nodes aufrufen, Audit-Log schreiben.
- Alle Node-Stubs validieren Inputs und schreiben nach `hive_mind.json`.
- Stub-Funktionen markieren sich selbst mit `TODO: real impl` im Code.

## Was ist NICHT enthalten und warum

Diese Dinge brauchen reale Accounts/Vertrage/Wallets, nicht Python:

- **TikTok/Instagram/YouTube Auto-Posting**  -> Plattform-APIs geschlossen,
  OAuth-Tokens persoenlich beantragen.
- **Spotify-Pitching**                        -> nur ueber Spotify for Artists,
  verifizierter Kuenstler-Account noetig.
- **Smart-Contract-Splits**                   -> brauchen Wallet + Chain-Auswahl
  (Polygon/Base empfohlen) + Smart-Contract-Audit.
- **Automatische Meta/TikTok-Ads**            -> Business-Account, Steuer-ID,
  Zahlungsmittel.
- **Sync-Licensing-Deals (Netflix, Ubisoft)** -> manuell, ueber Agenturen.

Diese Luecken sind Absicht, nicht Bug.

## Schnellstart

```bash
pip install -r requirements.txt
python core.py                # Smoke-Test
python core.py --track pfad/zur/mp3 --clips pfad/zu/clips
```

## Lizenz

Privat. Nicht offen verteilen - enthaelt Strategie-Texte aus dem Konzept.
