"""
unreal_side/build_and_render.py — läuft NICHT als normales Python-Skript,
sondern wird von unreal_renderer.py per

    UnrealEditor-Cmd.exe <project> <map> -ExecutePythonScript=<dieses Skript>
        -OidasheimManifest=<pfad zum JSON-Manifest>

(BUGFIX: KEIN "-game" mehr -- dieses Skript braucht Editor-Kontext, siehe
unreal_renderer.py für die Begründung) INNERHALB von Unreal Engines
eingebettetem Python-Interpreter ausgeführt.
Das "unreal"-Modul unten ist deshalb außerhalb des Editors/dieses Kontexts
NICHT importierbar -- das ist normal und kein Fehler in diesem Repo.

STATUS: Vorlage/Scaffold. Unreal ist auf diesem Rechner noch nicht
installiert, entsprechend ist dieses Skript noch nicht gegen ein echtes
Projekt/Assets getestet. Die Struktur (Manifest laden -> Level Sequence mit
Media-Track pro Segment bauen -> Movie Render Queue Job starten -> Engine
sauber beenden) ist der vorgesehene Ablauf; die exakten Asset-Pfade
(Sequence-Template, Media-Source-Factory, MRQ-Preset) müssen einmalig auf
das konkrete Unreal-Projekt abgestimmt werden, sobald es existiert.
"""
import json
import sys

try:
    import unreal
except ImportError as exc:  # pragma: no cover - nur außerhalb von Unreal relevant
    raise RuntimeError(
        "unreal_side/build_and_render.py kann nur INNERHALB von Unreal "
        "Engines eingebettetem Python ausgeführt werden (das 'unreal'-Modul "
        "existiert nur dort). Dieses Skript wird von unreal_renderer.py "
        "automatisch per UnrealEditor-Cmd.exe -ExecutePythonScript= "
        "aufgerufen -- nicht direkt mit einem normalen Python-Interpreter."
    ) from exc


def _read_manifest_path() -> str:
    """Liest den Manifest-Pfad aus der Unreal-Kommandozeile
    (-OidasheimManifest=<pfad>, siehe unreal_renderer.py::render_music_video)."""
    for arg in sys.argv:
        if arg.startswith("-OidasheimManifest="):
            return arg.split("=", 1)[1]
    # Fallback: Unreal reicht Kommandozeilen-Args manchmal separat durch.
    cmdline = unreal.SystemLibrary.get_command_line()
    for token in cmdline.split():
        if token.startswith("-OidasheimManifest="):
            return token.split("=", 1)[1]
    raise RuntimeError("-OidasheimManifest=<pfad> fehlt in der Unreal-Kommandozeile.")


def _load_manifest(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_level_sequence(manifest: dict):
    """Baut eine Level Sequence und legt pro Timeline-Segment eine Media-
    Track-Section an, die exakt den gleichen Clip-Ausschnitt (clip_path,
    start_sec/end_sec, clip_in_point) referenziert wie der ffmpeg-Renderer --
    Unreal übernimmt so den identischen Schnitt, kann aber zusätzlich
    Post-Process/3D-Overlays der Szene einblenden.

    TODO (sobald das konkrete Unreal-Projekt existiert):
    - Media-Source-Assets für jede clip_path anlegen/wiederverwenden
      (unreal.AssetToolsHelpers + unreal.FileMediaSource), statt Pfade roh
      auf eine Media-Player-Komponente zu setzen.
    - Sequence-Template-Asset (Kamera-Rig/Basis-Setup) referenzieren statt
      eine komplett leere Sequence zu erzeugen.
    """
    sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name="BeatSyncRender",
        package_path="/Game/Oidasheim/GeneratedSequences",
        asset_class=unreal.LevelSequence,
        factory=unreal.LevelSequenceFactoryNew(),
    )
    if manifest.get("storyline"):
        # Rein informativ (keine Unreal-API dafür, die eine Sequence direkt
        # mit Freitext beschriftet) -- landet im Editor-Log, damit man beim
        # späteren manuellen Set-Dressing/Nachvertonen im Sequencer sofort
        # den Song-Kontext zur Hand hat, ohne extra das Manifest-JSON öffnen
        # zu müssen (siehe main.py::_build_storyline für die Herkunft).
        unreal.log(f"[build_and_render] Storyline (Song-Kontext): {manifest['storyline']}")
    # BUGFIX: vorher wurde hier der reine PACKAGE-Pfad ("/Game/.../
    # BeatSyncRender", ohne Objekt-Suffix) manuell zusammengebaut und später
    # als job.sequence = SoftObjectPath(sequence_path) verwendet. Ein gültiger
    # SoftObjectPath für ein Asset braucht aber "Package.ObjectName" (z.B.
    # "/Game/.../BeatSyncRender.BeatSyncRender") -- ohne den Objektnamen nach
    # dem Punkt löst Unreal den Pfad zu keinem echten Objekt auf, und die MRQ
    # Job-Konfiguration (job.sequence) würde ins Leere zeigen. sequence.
    # get_path_name() liefert den korrekten, vollständigen Objekt-Pfad direkt
    # vom bereits erstellten Asset, statt ihn erneut (und diesmal unvollständig)
    # von Hand zu konstruieren.
    sequence_path = sequence.get_path_name()

    # Optionales Intro-Standbild (siehe unreal_renderer._resolve_start_image /
    # config.UNREAL_START_IMAGE_PATH) -- schiebt ALLE Clip-Segmente um dessen
    # duration_sec nach hinten, statt sie mit Segment 0 zu überlappen. Die
    # eigentlichen Segment-Zeiten im Manifest (seg["start_sec"]/["end_sec"])
    # bleiben dabei unverändert -- der Offset wird NUR hier beim Bauen der
    # Sequence-Sections addiert, damit main.py's .edl.json/Render-Reward-
    # Buchhaltung (die dieselben Segment-Objekte auch für den ffmpeg-Pfad
    # nutzt) von der Unreal-spezifischen Verschiebung unberührt bleibt.
    start_image = manifest.get("start_image")
    image_offset_sec = float(start_image["duration_sec"]) if start_image else 0.0

    total_end = max((seg["end_sec"] for seg in manifest["segments"]), default=0.0) + image_offset_sec
    fps = unreal.FrameRate(30, 1)
    sequence.set_display_rate(fps)
    sequence.set_playback_start(0)
    sequence.set_playback_end(int(total_end * fps.numerator))

    media_track = sequence.add_track(unreal.MovieSceneMediaTrack)

    if start_image:
        # TODO (sobald das konkrete Unreal-Projekt existiert): FileMediaSource
        # ist für Video-Quellen gedacht (Media Framework braucht einen
        # Player/Codec, der ein Einzelbild i.d.R. nicht als "Video" öffnet).
        # Für ein robustes Standbild empfiehlt sich stattdessen ein Image-Plate
        # (unreal.MovieSceneImagePlateTrack o.ä.) oder ein per Texture2D/
        # Material gerendertes Standbild. Hier bewusst mit demselben
        # FileMediaSource-Muster wie die Clip-Segmente gehalten, damit die
        # Track-Struktur konsistent bleibt -- exaktes Asset-Setup ist wie beim
        # Rest dieser Datei erst mit echtem Projekt/Assets final zu verifizieren.
        image_source = unreal.FileMediaSource()
        image_source.set_editor_property("file_path", start_image["path"])
        image_section = media_track.add_section()
        image_section.set_range(0, int(image_offset_sec * fps.numerator))
        image_section.set_editor_property("media_source", image_source)
        unreal.log(f"[build_and_render] Start-Image-Section: {start_image['path']} "
                   f"(0s - {image_offset_sec:.1f}s).")

    for seg in manifest["segments"]:
        media_source = unreal.FileMediaSource()
        media_source.set_editor_property("file_path", seg["clip_path"])

        start_frame = int((seg["start_sec"] + image_offset_sec) * fps.numerator)
        end_frame = int((seg["end_sec"] + image_offset_sec) * fps.numerator)
        section = media_track.add_section()
        section.set_range(start_frame, end_frame)
        section.set_editor_property("media_source", media_source)
        # clip_in_point als Start-Offset innerhalb der Quelldatei:
        section.set_editor_property(
            "start_frame_offset", int(seg["clip_in_point"] * fps.numerator)
        )

    unreal.EditorAssetLibrary.save_loaded_asset(sequence)
    return sequence, sequence_path


def _run_movie_render_queue(sequence_path: str, manifest: dict):
    """Startet einen Movie Render Queue Job für die generierte Sequence und
    wartet synchron auf dessen Abschluss (Rückgabe True=Erfolg)."""
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueEngineSubsystem)
    queue = subsystem.get_queue()
    queue.delete_all_jobs()

    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.map = unreal.SoftObjectPath(manifest["map"])
    job.sequence = unreal.SoftObjectPath(sequence_path)

    config_asset = unreal.EditorAssetLibrary.load_asset(manifest["mrq_config"])
    if config_asset:
        job.get_configuration().copy_from(config_asset)

    import os
    output_setting = job.get_configuration().find_or_add_setting_by_class(
        unreal.MoviePipelineOutputSetting
    )
    out_path = manifest["output_path"]
    output_setting.output_directory = unreal.DirectoryPath(os.path.dirname(out_path))
    output_setting.file_name_format = os.path.splitext(os.path.basename(out_path))[0]

    # BUGFIX (kritisch): Der vorherige Code wartete hier mit einem
    # blockierenden time.sleep()-Poll-Loop auf result_holder["done"]. Dieses
    # Skript läuft aber synchron im Haupt-Game-Thread von -ExecutePythonScript
    # -- ein blockierender Python-Sleep an dieser Stelle friert den
    # Engine-Tick komplett ein. render_queue_with_executor_instance() startet
    # einen ASYNCHRONEN Render, der über mehrere Engine-Ticks hinweg Frames
    # akkumuliert/schreibt; ohne Ticks kommt er nie voran -> garantierter
    # Deadlock bis zum harten UNREAL_RENDER_TIMEOUT_SEC-Timeout in
    # unreal_renderer.py, JEDES Mal.
    #
    # Zusätzlich (siehe Epic-Doku zu EditorPythonScripting.
    # set_keep_python_script_alive/Forum "Prevent Editor from exiting when
    # running from command line with -ExecutePythonScript"): sobald das
    # Python-Skript aus -ExecutePythonScript zurückkehrt, schließt sich der
    # Editor standardmäßig im NÄCHSTEN Tick von selbst -- noch bevor der
    # Render überhaupt starten könnte. main() setzt deshalb jetzt vorab
    # set_keep_python_script_alive(True) (siehe unten), main() kehrt hier
    # normal zurück (kein Blockieren mehr), die Engine tickt normal weiter,
    # und _on_finished() beendet den Prozess selbst -- erst dann, wenn der
    # Render wirklich fertig ist.
    def _on_finished(executor, success):
        if success:
            unreal.log(f"[build_and_render] MRQ-Render erfolgreich abgeschlossen -> {manifest['output_path']}")
        else:
            unreal.log_error("[build_and_render] Movie Render Queue Job fehlgeschlagen.")
        # quit_editor() beendet den Prozess in BEIDEN Fällen sauber -- der
        # Exit-Code allein ist bei Unreal kein verlässliches Erfolgssignal,
        # deshalb prüft unreal_renderer.py zusätzlich, ob output_path danach
        # tatsächlich existiert und eine plausible Größe hat.
        unreal.SystemLibrary.quit_editor()

    executor = unreal.MoviePipelinePIEExecutor()
    executor.on_executor_finished_delegate.add_callable_unique(_on_finished)
    subsystem.render_queue_with_executor_instance(executor)


def main():
    # BUGFIX (kritisch, siehe Epic-Doku unreal.EditorPythonScripting sowie
    # Forum-Thread "Prevent Editor from exiting when running from command
    # line with -ExecutePythonScript"): OHNE diesen Aufruf schließt der
    # Editor sich standardmäßig im TICK direkt NACH Rückkehr aus main()
    # von selbst -- der gerade erst über render_queue_with_executor_instance()
    # gestartete, asynchrone MRQ-Job würde dadurch sofort abgewürgt, bevor
    # er auch nur ein Frame gerendert hat. quit_editor() wird stattdessen
    # explizit im _on_finished-Callback in _run_movie_render_queue()
    # aufgerufen, erst wenn der Render TATSÄCHLICH fertig ist.
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)

    manifest_path = _read_manifest_path()
    manifest = _load_manifest(manifest_path)
    unreal.log(f"[build_and_render] Manifest geladen: {manifest_path} "
               f"({len(manifest['segments'])} Segmente).")

    sequence, sequence_path = _build_level_sequence(manifest)
    unreal.log(f"[build_and_render] Level Sequence gebaut: {sequence_path}")

    # Startet den Render nur noch; main() kehrt danach normal zurück (KEIN
    # sys.exit hier mehr) -- der Prozess läuft weiter, bis _on_finished()
    # in _run_movie_render_queue() unreal.SystemLibrary.quit_editor() ruft.
    _run_movie_render_queue(sequence_path, manifest)
    unreal.log("[build_and_render] Render-Job eingereicht, warte auf Fertigstellung "
               "(Editor beendet sich selbst über den Fertig-Callback) ...")


if __name__ == "__main__":
    main()
