"""
Asset Processor — Unit Tests

Test cases: module import, scene detection, clip cutting, thumbnail generation,
index merging, empty directory, non-video filtering, min_scene_duration filter.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_asset_processor.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Helpers ──────────────────────────────────────────────

def _make_processor(**kwargs) -> "AssetProcessor":
    from src.asset_processor import AssetProcessor
    return AssetProcessor(**kwargs)


def _make_test_video(output_path: Path, duration: float = 3.0) -> Path:
    """Generate a small test MP4 with FFmpeg for testing."""
    FFMPEG = str(Path(
        "C:/Users/aarinsim/AppData/Local/Microsoft/WinGet/Packages/"
        "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
        "ffmpeg-8.1.1-full_build/bin/ffmpeg.exe"
    ))
    import subprocess
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=640x360:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create test video: {result.stderr[:300]}")
    return output_path


# ── Tests: Module & Init ────────────────────────────────

class TestInit:
    def test_import(self):
        """AssetProcessor can be imported."""
        from src.asset_processor import AssetProcessor
        assert AssetProcessor is not None

    def test_init_default_dirs(self):
        """Default dirs are set from config."""
        proc = _make_processor()
        from src.config import ASSETS_RAW_DIR, ASSETS_PROCESSED_DIR, ASSETS_THUMBNAILS_DIR, ASSETS_INDEX
        assert proc.raw_dir == ASSETS_RAW_DIR
        assert proc.processed_dir == ASSETS_PROCESSED_DIR
        assert proc.thumbnails_dir == ASSETS_THUMBNAILS_DIR
        assert proc.index_path == ASSETS_INDEX

    def test_init_custom_dirs(self):
        """Custom dirs override defaults."""
        d = Path(tempfile.mkdtemp())
        proc = _make_processor(
            raw_dir=d / "raw",
            processed_dir=d / "out",
            thumbnails_dir=d / "thumb",
            index_path=d / "index.json",
        )
        assert proc.raw_dir == d / "raw"
        assert proc.processed_dir == d / "out"

    def test_dirs_created_on_init(self):
        """Directories are created if they don't exist."""
        d = Path(tempfile.mkdtemp())
        r = d / "raw"; p = d / "processed"; t = d / "thumb"
        _make_processor(raw_dir=r, processed_dir=p, thumbnails_dir=t, index_path=d / "idx.json")
        assert r.exists() and p.exists() and t.exists()

    def test_min_scene_duration_default(self):
        """Default min_scene_duration is 1.0 seconds."""
        proc = _make_processor()
        assert proc.min_scene_duration == 1.0


# ── Tests: Empty / Missing ─────────────────────────────

class TestEmptyScenarios:
    def test_empty_raw_dir(self):
        """Empty raw/ dir returns empty list."""
        d = Path(tempfile.mkdtemp())
        raw = d / "raw"; raw.mkdir()
        proc = _make_processor(raw_dir=raw, processed_dir=d / "out",
                               thumbnails_dir=d / "thumb", index_path=d / "idx.json")
        result = proc.process_all()
        assert result == []

    def test_process_missing_file(self):
        """Non-existent video raises FileNotFoundError."""
        proc = _make_processor()
        with pytest.raises(FileNotFoundError):
            proc.process_video(Path("/nonexistent/video.mp4"))

    def test_non_video_skipped_in_raw(self):
        """Non-video files in raw/ are ignored."""
        d = Path(tempfile.mkdtemp())
        raw = d / "raw"; raw.mkdir()
        (raw / "readme.txt").write_text("hello")
        (raw / ".gitkeep").write_text("")
        proc = _make_processor(raw_dir=raw, processed_dir=d / "out",
                               thumbnails_dir=d / "thumb", index_path=d / "idx.json")
        videos = proc._find_raw_videos()
        assert len(videos) == 0


# ── Tests: Scene Detection ─────────────────────────────

class TestSceneDetection:
    def test_detect_scenes_returns_list(self):
        """_detect_scenes returns [(start, end), ...] or []."""
        d = Path(tempfile.mkdtemp())
        test_vid = d / "test.mp4"
        _make_test_video(test_vid, duration=3.0)
        proc = _make_processor()
        scenes = proc._detect_scenes(test_vid)
        assert isinstance(scenes, list)
        # Short test video may return empty or 1 scene
        if scenes:
            assert len(scenes[0]) == 2
            assert scenes[0][0] < scenes[0][1]

    def test_detect_scenes_missing_file(self):
        """_detect_scenes on non-existent file returns empty list gracefully."""
        proc = _make_processor()
        scenes = proc._detect_scenes(Path("/nonexistent/video.mp4"))
        assert scenes == []


# ── Tests: Clip Cutting ────────────────────────────────

class TestClipCutting:
    def test_cut_clip_creates_file(self):
        """_cut_clip produces a valid non-empty MP4 file."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        out = d / "out.mp4"
        _make_test_video(src, duration=3.0)
        proc = _make_processor()
        proc._cut_clip(src, start=0.0, duration=1.5, output=out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_cut_clip_respects_duration(self):
        """Cut clip duration is roughly correct."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        out = d / "out.mp4"
        _make_test_video(src, duration=3.0)
        proc = _make_processor()
        proc._cut_clip(src, start=0.5, duration=2.0, output=out)
        dur = proc._get_duration(out)
        assert dur is not None
        assert 1.5 < dur < 2.5  # ~2.0s with some tolerance


# ── Tests: Thumbnail Generation ────────────────────────

class TestThumbnail:
    def test_extract_thumbnail_creates_file(self):
        """_extract_thumbnail creates a non-empty jpg."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        thumb = d / "thumb.jpg"
        _make_test_video(src, duration=3.0)
        proc = _make_processor()
        proc._extract_thumbnail(src, thumb)
        assert thumb.exists()
        assert thumb.stat().st_size > 500

    def test_thumbnail_is_valid_jpeg(self):
        """Thumbnail file starts with JPEG magic bytes."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        thumb = d / "thumb.jpg"
        _make_test_video(src, duration=3.0)
        proc = _make_processor()
        proc._extract_thumbnail(src, thumb)
        header = thumb.read_bytes()[:3]
        assert header == b'\xff\xd8\xff', f"Not a valid JPEG: {header.hex()}"


# ── Tests: Index Merging ───────────────────────────────

class TestIndexMerging:
    def test_merge_index_creates_file(self):
        """_merge_index creates index.json if it doesn't exist."""
        from src.asset_library import AssetRecord
        d = Path(tempfile.mkdtemp())
        idx = d / "index.json"
        proc = _make_processor(
            raw_dir=d / "raw", processed_dir=d / "out",
            thumbnails_dir=d / "thumb", index_path=idx,
        )
        r = AssetRecord(
            id="asset_test", path="processed/test.mp4", type="video", tags=[],
            duration=2.0, thumbnail="thumbnails/test.jpg",
            source_video="raw/orig.mp4", start_time=0.0, end_time=2.0,
        )
        proc._merge_index([r])
        assert idx.exists()
        data = json.loads(idx.read_text())
        assert len(data) == 1
        assert data[0]["id"] == "asset_test"
        assert data[0]["thumbnail"] == "thumbnails/test.jpg"

    def test_merge_index_appends(self):
        """_merge_index appends to existing records."""
        from src.asset_library import AssetRecord
        d = Path(tempfile.mkdtemp())
        idx = d / "index.json"
        idx.write_text(json.dumps([{"id": "a1", "path": "p1.mp4", "type": "video", "tags": []}]))
        proc = _make_processor(
            raw_dir=d / "raw", processed_dir=d / "out",
            thumbnails_dir=d / "thumb", index_path=idx,
        )
        r = AssetRecord(
            id="a2", path="processed/a2.mp4", type="video", tags=[],
            duration=3.0, thumbnail="thumbnails/a2.jpg",
            source_video="raw/orig.mp4", start_time=2.0, end_time=5.0,
        )
        proc._merge_index([r])
        data = json.loads(idx.read_text())
        assert len(data) == 2


# ── Tests: Probe ───────────────────────────────────────

class TestProbe:
    def test_probe_resolution(self):
        """_probe_resolution returns WxH string."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        _make_test_video(src, duration=2.0)
        proc = _make_processor()
        res = proc._probe_resolution(src)
        assert res == "640x360"

    def test_get_duration_positive(self):
        """_get_duration returns positive float."""
        d = Path(tempfile.mkdtemp())
        src = d / "src.mp4"
        _make_test_video(src, duration=2.5)
        proc = _make_processor()
        dur = proc._get_duration(src)
        assert dur is not None
        assert 2.0 < dur < 3.0


# ── Tests: AssetRecord Fields ──────────────────────────

class TestAssetRecordFields:
    def test_new_fields_exist(self):
        """AssetRecord has thumbnail, source_video, start_time, end_time."""
        from src.asset_library import AssetRecord
        r = AssetRecord(
            id="x", path="y", type="image", tags=[],
            thumbnail="t.jpg", source_video="raw/z.mp4",
            start_time=1.0, end_time=5.0,
        )
        assert r.thumbnail == "t.jpg"
        assert r.source_video == "raw/z.mp4"
        assert r.start_time == 1.0
        assert r.end_time == 5.0

    def test_new_fields_have_defaults(self):
        """New fields default to empty/None."""
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.thumbnail == ""
        assert r.source_video == ""
        assert r.start_time is None
        assert r.end_time is None


# ── Tests: ID Generation ───────────────────────────────

class TestIDGeneration:
    def test_next_asset_id(self):
        """_next_asset_id generates sequential IDs."""
        proc = _make_processor()
        assert proc._next_asset_id(0) == "asset_001"
        assert proc._next_asset_id(5) == "asset_006"
        assert proc._next_asset_id(99) == "asset_100"

    def test_load_existing_ids(self):
        """_load_existing_ids returns count from existing index."""
        d = Path(tempfile.mkdtemp())
        idx = d / "index.json"
        idx.write_text(json.dumps([
            {"id": "a1", "path": "p1", "type": "image", "tags": []},
            {"id": "a2", "path": "p2", "type": "video", "tags": []},
        ]))
        proc = _make_processor(index_path=idx)
        assert proc._load_existing_ids() == 2
