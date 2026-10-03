#!/usr/bin/env python3
"""Local CLI for the Synapse OS release core."""
import argparse
import json
from pathlib import Path

from synapse_os import ReleaseManager, ReleaseStage


DEFAULT_STORE = Path(__file__).parent / "data" / "synapse_releases.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Synapse OS release operations")
    parser.add_argument("--store", default=str(DEFAULT_STORE), help="Lokale Release-Datenbank als JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Release anlegen und Artefakte planen")
    create.add_argument("release_id")
    create.add_argument("artist")
    create.add_argument("title")

    show = subparsers.add_parser("show", help="Release anzeigen")
    show.add_argument("release_id")

    advance = subparsers.add_parser("advance", help="Release einen Pipeline-Schritt weiterführen")
    advance.add_argument("release_id")
    advance.add_argument("stage", choices=[stage.value for stage in ReleaseStage])
    advance.add_argument("--approve", action="append", default=[], help="QC-Freigabe: sentinel oder aether")

    args = parser.parse_args()
    manager = ReleaseManager(args.store)

    if args.command == "create":
        release = manager.create_release(args.release_id, args.artist, args.title)
        artifacts = manager.plan(args.release_id)
        print(json.dumps({"release": release.to_dict(), "planned_artifacts": len(artifacts)}, indent=2))
    elif args.command == "show":
        print(json.dumps(manager.get_release(args.release_id).to_dict(), indent=2))
    else:
        release = manager.advance(args.release_id, args.stage, set(args.approve))
        print(json.dumps(release.to_dict(), indent=2))


if __name__ == "__main__":
    main()
