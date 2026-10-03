"""
unreal_side/setup_project_assets.py -- EINMALIGES Setup-Skript, das die von
unreal_renderer._check_configured() (siehe oefoef/unreal_renderer.py) fest
geforderten Render-Assets tatsaechlich im Projekt anlegt:

  - Map:        config.UNREAL_MAP        ("/Game/Maps/BeatSyncStage")
  - MRQ-Preset: config.UNREAL_MRQ_CONFIG ("/Game/MRQ/DefaultConfig")

Laeuft wie unreal_side/build_and_render.py NUR innerhalb von Unreals
eingebettetem Python (UnrealEditor-Cmd.exe <project> -ExecutePythonScript=...),
NICHT als normales Python-Skript -- das "unreal"-Modul existiert sonst nicht.

Idempotent: bereits vorhandene Assets werden uebersprungen statt neu
angelegt/ueberschrieben (siehe _asset_exists) -- gefahrlos mehrfach ausfuehrbar.

WICHTIGER HINWEIS ZUM VIDEO-OUTPUT (siehe auch unreal_renderer.py-Docstring):
Dieses Skript probiert beim Anlegen des MRQ-Presets der Reihe nach echte
Video-Encoder-Settings durch (ProRes/DNxHR, je nachdem welches Plugin im
Projekt aktiviert ist) und faellt, wenn KEINS davon verfuegbar ist, auf eine
PNG-Bildsequenz zurueck (immer verfuegbar, kein Zusatz-Plugin noetig). Eine
PNG-Sequenz ist aber KEINE fertige .mp4-Datei -- main.py/unreal_renderer.py
erwarten aktuell eine einzelne .mp4 unter output_path. Falls dieses Skript
auf den PNG-Fallback zurueckfaellt, ist der Unreal-Render-Pfad danach zwar
technisch "konfiguriert" (unreal_renderer._check_configured() findet die
Assets), liefert aber noch keine direkt abspielbare .mp4 -- das braucht dann
zusaetzlich entweder ein aktiviertes Video-Encoder-Plugin (Edit > Plugins >
"Apple ProRes Media" oder "Avid DNxHR Media" aktivieren, Editor neu starten,
dieses Skript erneut laufen lassen -- vorher /Game/MRQ/DefaultConfig im
Content Browser loeschen, damit es neu angelegt wird) oder einen zusaetzlichen
ffmpeg-Mux-Schritt ueber die erzeugte PNG-Sequenz.
"""
import unreal

MAP_PATH = "/Game/Maps/BeatSyncStage"
MRQ_PACKAGE_PATH = "/Game/MRQ"
MRQ_ASSET_NAME = "DefaultConfig"
MRQ_ASSET_PATH = f"{MRQ_PACKAGE_PATH}/{MRQ_ASSET_NAME}"

# Reihenfolge der Versuchskandidaten fuer den Video-Output -- Verfuegbarkeit
# haengt davon ab, welche MRQ-Encoder-Plugins im Projekt aktiviert sind
# (Edit > Plugins). Erster tatsaechlich vorhandener Klassenname gewinnt.
_VIDEO_OUTPUT_CANDIDATES = [
    "MoviePipelineAppleProResOutput",  # AppleProResMedia-Plugin, .mov, Software-Encoder (auch unter Windows)
    "MoviePipelineAvidDNxOutput",      # AvidDNxMedia-Plugin, .mxf
]


def _asset_exists(asset_path: str) -> bool:
    return unreal.EditorAssetLibrary.does_asset_exist(asset_path)


def _ensure_map() -> None:
    if _asset_exists(MAP_PATH):
        unreal.log(f"[setup_project_assets] Map existiert bereits, ueberspringe: {MAP_PATH}")
        return
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ok = level_subsystem.new_level(MAP_PATH, False)
    if not ok:
        raise RuntimeError(f"new_level({MAP_PATH}) ist fehlgeschlagen.")
    unreal.log(f"[setup_project_assets] Leere Map angelegt + gespeichert -> {MAP_PATH}")


def _ensure_mrq_config() -> None:
    if _asset_exists(MRQ_ASSET_PATH):
        unreal.log(f"[setup_project_assets] MRQ-Preset existiert bereits, ueberspringe: {MRQ_ASSET_PATH}")
        return

    config = unreal.MoviePipelinePrimaryConfig()

    output_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    output_setting.output_resolution = unreal.IntPoint(1920, 1080)
    output_setting.zero_pad_frame_numbers = 4

    # Render-Pass: liefert das eigentliche Bild (Standard-Deferred-Renderer,
    # deckt sich mit dem, was in der Editor-UI per Default vorausgewaehlt ist).
    render_pass = config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    render_pass.disable_multisample_effects = True

    chosen_output = None
    for class_name in _VIDEO_OUTPUT_CANDIDATES:
        output_class = getattr(unreal, class_name, None)
        if output_class is None:
            continue
        config.find_or_add_setting_by_class(output_class)
        chosen_output = class_name
        break

    if chosen_output is None:
        # Fallback: PNG-Bildsequenz, IMMER verfuegbar (Teil des Kern-MRQ-
        # Plugins, kein Zusatz-Plugin noetig) -- siehe Modul-Docstring fuer
        # die Konsequenz (keine fertige .mp4, sondern eine PNG-Sequenz).
        config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
        unreal.log_warning(
            "[setup_project_assets] Kein Video-Encoder-Plugin (ProRes/DNxHR) verfuegbar -> "
            "MRQ-Preset nutzt PNG-Bildsequenz-Fallback. Fuer eine direkt abspielbare "
            "Videodatei siehe Hinweis im Modul-Docstring (Plugin aktivieren + Skript erneut laufen lassen)."
        )
    else:
        unreal.log(f"[setup_project_assets] Video-Output-Setting verwendet: {chosen_output}")

    result = unreal.MoviePipelineEditorLibrary.export_config_to_asset(
        config, MRQ_PACKAGE_PATH, MRQ_ASSET_NAME, True
    )
    if result is None:
        raise RuntimeError("export_config_to_asset() lieferte kein Ergebnis (unerwartet).")
    out_asset, out_error_reason = result
    if out_asset is None:
        raise RuntimeError(f"MRQ-Preset konnte nicht gespeichert werden: {out_error_reason}")
    unreal.log(f"[setup_project_assets] MRQ-Preset angelegt + gespeichert -> {MRQ_ASSET_PATH}")


def main():
    unreal.log("[setup_project_assets] Starte einmaliges Asset-Setup fuer --renderer unreal ...")
    _ensure_map()
    _ensure_mrq_config()
    unreal.log("[setup_project_assets] Fertig. unreal_renderer._check_configured() sollte jetzt durchlaufen.")


if __name__ == "__main__":
    main()
