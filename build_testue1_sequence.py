import unreal
import json
import os

# Pfad zu deinen von der Pipeline generierten JSON-Daten
JSON_DATA_PATH = r"I:\Users\daaau\Documents\Unreal Projects\testue1\outputs\ue_sequences\sequence_data.json"

def build_testue1_sequence():
    if not os.path.exists(JSON_DATA_PATH):
        unreal.log_error(f"[Pipeline] JSON-Datei nicht gefunden unter: {JSON_DATA_PATH}")
        return

    with open(JSON_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    job_id = data.get("job_id", "testue1_job")
    target_fps = data.get("fps", 60)
    frame_rate = unreal.FrameRate(target_fps, 1)

    # 1. Level Sequence Asset im Projekt erstelle (/Game/Cinematics/Generated)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    package_path = "/Game/Cinematics/Generated"
    sequence_name = f"LS_{job_id}"
    
    sequence = asset_tools.create_asset(
        sequence_name, 
        package_path, 
        unreal.LevelSequence, 
        unreal.LevelSequenceFactoryNew()
    )
    sequence.set_display_rate(frame_rate)

    # 2. Tracks initialisieren
    camera_cut_track = sequence.add_master_track(unreal.MovieSceneCameraCutTrack)
    audio_track = sequence.add_master_track(unreal.MovieSceneAudioTrack)

    # 3. Audio-Track einbinden (falls Import in UE erfolgt ist)
    audio_file_path = data.get("audio_track", "")
    if audio_file_path and unreal.Paths.file_exists(audio_file_path):
        sound_wave = unreal.EditorAssetLibrary.load_asset(audio_file_path)
        if sound_wave:
            audio_section = audio_track.add_section()
            audio_section.set_start_frame_exact(0)
            audio_section.set_sound(sound_wave)

    # 4. Kameras & Frame-Genaue Cuts auf der Timeline platzieren
    for cut in data.get("cuts", []):
        start_frame = int(cut["start_time"] * target_fps)
        end_frame = int(cut["end_time"] * target_fps)

        # Cine Camera Actor in der UE-World spawnen
        cam_name = f"Cam_Cut_{cut['cut_index']:03d}_{cut['clip_id']}"
        camera_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.CineCameraActor, 
            unreal.Vector(0, 0, 100), 
            unreal.Rotator(0, 0, 0)
        )
        camera_actor.set_actor_label(cam_name)

        # Kamera-Binding zur Level Sequence hinzufügen
        cam_binding = sequence.add_possessable(camera_actor)

        # Camera Cut Section erzeugen
        cut_section = camera_cut_track.add_section()
        cut_section.set_range_exact(start_frame, end_frame)
        
        # Binding-ID der Kamera zuweisen
        camera_binding_id = unreal.MovieSceneObjectBindingID()
        camera_binding_id.set_editor_property("guid", cam_binding.get_id())
        cut_section.set_camera_binding_id(camera_binding_id)

    unreal.log(f"[Pipeline] Sequence '{sequence_name}' wurde in testue1 unter {package_path} erstellt!")

if __name__ == "__main__":
    build_testue1_sequence()