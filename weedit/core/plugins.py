"""
weedit.core.plugins — Extensible Plugin System for WE.ED.IT v9 Studio
"""

class BasePlugin:
    name = "base_plugin"

    def process(self, timeline_segments: list, audio_analysis) -> list:
        return timeline_segments

class BeatDropPlugin(BasePlugin):
    name = "beat_drop"

    def process(self, timeline_segments: list, audio_analysis) -> list:
        drop_times = getattr(audio_analysis, "drop_times", [])
        if not drop_times:
            return timeline_segments

        for seg in timeline_segments:
            for dt in drop_times:
                if abs(seg.start_sec - dt) < 0.3:
                    seg.camera = "snap"
                    seg.cut_style = "push"
                    seg.sync_type = "snap_drop"
        return timeline_segments

class WobbleZoomPlugin(BasePlugin):
    name = "wobble_zoom"

    def process(self, timeline_segments: list, audio_analysis) -> list:
        for seg in timeline_segments:
            if getattr(seg, "target_energy", 0.0) > 0.8:
                seg.camera = "bass_wobble"
        return timeline_segments

class ColorGradePlugin(BasePlugin):
    name = "color_grade"

    def process(self, timeline_segments: list, audio_analysis) -> list:
        for seg in timeline_segments:
            if getattr(seg, "structure_label", "verse") == "hook":
                seg.color = "vivid"
            elif getattr(seg, "structure_label", "verse") in ("breakdown", "outro"):
                seg.color = "desaturated"
        return timeline_segments

class PluginManager:
    def __init__(self):
        self.plugins = [
            BeatDropPlugin(),
            WobbleZoomPlugin(),
            ColorGradePlugin()
        ]

    def register(self, plugin: BasePlugin):
        self.plugins.append(plugin)

    def run_all(self, timeline_segments: list, audio_analysis) -> list:
        for p in self.plugins:
            timeline_segments = p.process(timeline_segments, audio_analysis)
        return timeline_segments
