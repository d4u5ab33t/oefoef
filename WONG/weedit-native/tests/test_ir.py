from core.ir import SongAST, ShotIntent, CameraIntent
def test_song_ast():
    song = SongAST(title="Test", artist="Artist", total_duration_ms=30000, sections=[], global_energy_curve=[0.5]*100, global_emotion_curve=[0.5]*100)
    assert song.title == "Test"
