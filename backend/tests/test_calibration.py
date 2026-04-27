from backend.storage.storage import load_artifact, save_artifact


def test_calibration_storage():
    # Test that saving and loading artifacts works (this touches DB or filesystem, mock or real test if sqlite works)
    # The actual calibration module uses these heavily
    save_artifact("test_artifact", {"test": "data"}, artifact_type="json", session_id="test_calib")

    loaded = load_artifact("test_artifact", session_id="test_calib")
    assert loaded == {"test": "data"}
