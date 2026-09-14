"""
otio_exporter.py — OpenTimelineIO (OTIO) & NLE project exporter.
"""
import json
from typing import Dict, Any
from genome_engine.compiler.timeline import EditDecisionList


class OTIOExporter:
    """Exports EditDecisionList to OpenTimelineIO JSON representation."""

    @staticmethod
    def export_otio(edl: EditDecisionList) -> str:
        otio_schema = {
            "OTIO_SCHEMA": "Timeline.1",
            "name": f"GenomeEngine_{edl.style_name}",
            "global_start_time": {"rational_time": {"rate": 30.0, "value": 0}},
            "tracks": {
                "OTIO_SCHEMA": "Stack.1",
                "children": [
                    {
                        "OTIO_SCHEMA": "Track.1",
                        "kind": "Video",
                        "name": "V1",
                        "children": [
                            {
                                "OTIO_SCHEMA": "Clip.1",
                                "name": f"Segment_{seg.segment_id}_{seg.sync_type}",
                                "media_reference": {
                                    "OTIO_SCHEMA": "ExternalReference.1",
                                    "target_url": seg.assigned_clip_path or "missing_clip.mp4"
                                },
                                "source_range": {
                                    "OTIO_SCHEMA": "TimeRange.1",
                                    "start_time": {"rate": 30.0, "value": int(seg.clip_in_sec * 30)},
                                    "duration": {"rate": 30.0, "value": int(seg.duration_sec * 30)}
                                }
                            }
                            for seg in edl.segments
                        ]
                    }
                ]
            }
        }
        return json.dumps(otio_schema, indent=2)
