"""
Video Composer — Unit Tests (MVP)

Test cases: audio duration, scene calc, image→video, video trim,
concat, missing asset, missing voice, CompositionResult.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_video_composer.py -v
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.video_composer import VideoComposer, CompositionResult
from src.config import TEMP_DIR


# ── Fixtures ──────────────────────────────────────────

VOICE_PATH = TEMP_DIR / "voice.mp3"
TEST_IMAGE = PROJECT_ROOT / "assets" / "general" / "travel_compass.jpg"
TEST_VIDEO = PROJECT_ROOT / "assets" / "island" / "manukan_aerial.mp4"


def _make_composer() -> VideoComposer:
    return VideoComposer(output_dir=TEMP_DIR, temp_dir=TEMP_DIR)


def _make_script_with_assets():
    """Mock script_with_assets dict with real asset paths."""
    return {
        "title": "Test Video",
        "scenes": [
            {
                "id": 1,
                "text": "测试文本第一段共十五个中文字符",
                "assets": [
                    {"path": "general/travel_compass.jpg", "type": "image"},
                ],
            },
            {
                "id": 2,
                "text": "第二段文本十个中文字符测试",
                "assets": [
                    {"path": "general/travel_compass.jpg", "type": "image"},
                ],
            },
        ],
    }


# ── Tests: Audio Duration ─────────────────────────────

def test_get_audio_duration():
    """ffprobe should return voice.mp3 duration as float."""
    composer = _make_composer()
    duration = composer._get_audio_duration(VOICE_PATH)

    assert isinstance(duration, float)
    assert duration > 0
    assert 5 < duration < 60  # Should be ~30s


def test_get_audio_duration_missing_file():
    """Missing audio file → FileNotFoundError."""
    composer = _make_composer()
    try:
        composer._get_audio_duration(Path("nonexistent.mp3"))
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


# ── Tests: Scene Duration Calculation ─────────────────

def test_calculate_scene_durations():
    """Duration allocation proportional to text length."""
    composer = _make_composer()
    scenes = [
        {"id": 1, "text": "AAAAAAAAAA"},  # 10 chars
        {"id": 2, "text": "AAAAA"},       # 5 chars
    ]
    durations = composer._calculate_scene_durations(scenes, total_dur=30.0)

    assert durations[1] == pytest.approx(20.0, abs=0.5)
    assert durations[2] == pytest.approx(10.0, abs=0.5)
    assert abs(durations[1] + durations[2] - 30.0) < 0.5


def test_calculate_scene_durations_empty_text():
    """All empty text → ValueError."""
    composer = _make_composer()
    scenes = [
        {"id": 1, "text": ""},
        {"id": 2, "text": ""},
    ]
    try:
        composer._calculate_scene_durations(scenes, 30.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ── Tests: Image → Video Clip ─────────────────────────

def test_image_to_clip():
    """Image should be converted to a video clip."""
    composer = _make_composer()
    output = composer._image_to_clip(TEST_IMAGE, duration=2.0, index=0)

    assert output.exists()
    assert output.stat().st_size > 0
    assert output.suffix == ".mp4"


def test_image_to_clip_file_not_found():
    """Missing image → FFmpeg error → RuntimeError."""
    composer = _make_composer()
    try:
        composer._image_to_clip(Path("nonexistent.jpg"), 2.0, 99)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


# ── Tests: Video → Clip ───────────────────────────────

def test_video_to_clip():
    """Video should be trimmed and resized."""
    composer = _make_composer()
    output = composer._video_to_clip(TEST_VIDEO, duration=2.0, index=100)

    assert output.exists()
    assert output.stat().st_size > 0


def test_video_to_clip_missing_file():
    """Missing video → RuntimeError."""
    composer = _make_composer()
    try:
        composer._video_to_clip(Path("nope.mp4"), 2.0, 99)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


# ── Tests: Concat ─────────────────────────────────────

def test_concat_clips():
    """Two clips concatenated into one video (V2: _concat_with_crossfade)."""
    composer = _make_composer()

    # Create 2 short image clips
    clip1 = composer._image_to_clip(TEST_IMAGE, duration=1.0, index=200)
    clip2 = composer._image_to_clip(TEST_IMAGE, duration=1.0, index=201)

    output = composer._concat_with_crossfade([clip1, clip2], {})

    assert output.exists()
    assert output.stat().st_size > 0


# ── Tests: Asset Path Resolution ──────────────────────

def test_resolve_asset_path():
    """Relative path → absolute path under assets/."""
    composer = _make_composer()
    abs_path = composer._resolve_asset_path("general/travel_compass.jpg")

    assert abs_path.is_absolute()
    assert abs_path.exists()


# ── Tests: Error Handling ─────────────────────────────

def test_compose_missing_voice():
    """Missing voice.mp3 → FileNotFoundError."""
    composer = _make_composer()
    script = _make_script_with_assets()

    try:
        composer.compose(script, Path("nope.mp3"))
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_compose_empty_scenes():
    """Empty scene list → ValueError."""
    composer = _make_composer()

    try:
        composer.compose({"scenes": []}, VOICE_PATH)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_compose_scene_no_assets():
    """Scene with no assets → ValueError."""
    composer = _make_composer()
    script = {
        "scenes": [
            {"id": 1, "text": "test", "assets": []},
        ],
    }

    try:
        composer.compose(script, VOICE_PATH)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_compose_missing_asset_file():
    """Asset path points to non-existent file → FileNotFoundError."""
    composer = _make_composer()
    script = {
        "scenes": [
            {
                "id": 1,
                "text": "test text here for duration",
                "assets": [{"path": "general/nonexistent.jpg", "type": "image"}],
            },
        ],
    }

    try:
        composer.compose(script, VOICE_PATH)
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


# ── Tests: Full Composition ───────────────────────────

def test_full_composition():
    """End-to-end: compose a real video with voice.mp3."""
    composer = _make_composer()
    script = _make_script_with_assets()

    result = composer.compose(script, VOICE_PATH)

    assert isinstance(result, CompositionResult)
    assert result.video_path.exists()
    assert result.video_path.stat().st_size > 0
    assert result.duration > 0
    assert result.scene_count == 2
    assert result.asset_count == 2
    assert result.resolution == "1080x1920"

    print(f"  Video: {result.video_path}")
    print(f"  Duration: {result.duration:.1f}s")
    print(f"  Scenes: {result.scene_count}, Assets: {result.asset_count}")
    size_mb = result.video_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")


# ── Main ───────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    print("=" * 60)
    print("  Video Composer — Unit Tests")
    print("=" * 60)

    tests = [
        ("Audio duration", test_get_audio_duration),
        ("Audio missing file", test_get_audio_duration_missing_file),
        ("Scene duration calc", test_calculate_scene_durations),
        ("Scene empty text", test_calculate_scene_durations_empty_text),
        ("Image to clip", test_image_to_clip),
        ("Image missing file", test_image_to_clip_file_not_found),
        ("Video to clip", test_video_to_clip),
        ("Video missing file", test_video_to_clip_missing_file),
        ("Concat clips", test_concat_clips),
        ("Resolve asset path", test_resolve_asset_path),
        ("Compose missing voice", test_compose_missing_voice),
        ("Compose empty scenes", test_compose_empty_scenes),
        ("Compose no assets", test_compose_scene_no_assets),
        ("Compose missing asset file", test_compose_missing_asset_file),
        ("Full composition E2E", test_full_composition),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)
