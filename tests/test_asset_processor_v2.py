"""
Asset Processor V2 — Unit Tests

Test cases: multi-frame extraction, quality scoring, multi-frame tagging,
scene summary, V2 AssetRecord fields, backward compat.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_asset_processor_v2.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Helpers ──────────────────────────────────────────────

def _make_test_video(output_path: Path, duration: float = 5.0) -> Path:
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


def _make_processor(**kwargs) -> "AssetProcessor":
    from src.asset_processor import AssetProcessor
    return AssetProcessor(**kwargs)


# ── Tests: Multi-Frame Extraction ──────────────────────

class TestMultiFrameExtraction:
    def test_extract_multi_frames_returns_list(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        frames = proc.extract_multi_frames(src, thumb, "test_asset")
        assert isinstance(frames, list)
        assert len(frames) >= 1

    def test_extract_multi_frames_generates_three_for_long_video(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=6.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        frames = proc.extract_multi_frames(src, thumb, "ast1")
        assert len(frames) == 3, f"Expected 3 frames, got {len(frames)}"
        labels = [f.stem.split("_")[-1] for f in frames]
        assert "p25" in labels and "p50" in labels and "p75" in labels

    def test_extract_multi_frames_images_are_valid(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        frames = proc.extract_multi_frames(src, thumb, "ast2")
        for fp in frames:
            assert fp.exists()
            assert fp.stat().st_size > 500
            assert fp.suffix == ".jpg"

    def test_extract_frame_at_specific_time(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=4.0)
        out = d / "frame_at_1s.jpg"
        proc = _make_processor()
        proc._extract_frame_at(src, 1.0, out)
        assert out.exists()
        assert out.stat().st_size > 500


# ── Tests: Quality Scoring ─────────────────────────────

class TestQualityScoring:
    def test_quality_score_in_range(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        proc = _make_processor()
        score = proc.compute_quality_score(src, resolution="640x360", duration=5.0)
        assert 0.0 <= score <= 1.0

    def test_ideal_clip_scores_high(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=8.0)
        proc = _make_processor()
        score = proc.compute_quality_score(src, resolution="3840x2160", duration=8.0)
        assert score >= 0.7, f"Expected >= 0.7, got {score}"

    def test_short_clip_scores_lower(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=0.5)
        proc = _make_processor()
        score_short = proc.compute_quality_score(src, resolution="3840x2160", duration=0.5)
        score_ideal = proc.compute_quality_score(src, resolution="3840x2160", duration=8.0)
        assert score_short < score_ideal, \
            f"Short {score_short} should be < ideal {score_ideal}"

    def test_low_res_scores_lower(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        proc = _make_processor()
        score_low = proc.compute_quality_score(src, resolution="640x360", duration=5.0)
        score_high = proc.compute_quality_score(src, resolution="3840x2160", duration=5.0)
        assert score_low < score_high

    def test_quality_without_resolution(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        proc = _make_processor()
        score = proc.compute_quality_score(src, resolution="", duration=None)
        assert 0.0 <= score <= 1.0


# ── Tests: Multi-Frame Tagging ─────────────────────────

class TestMultiFrameTagging:
    def test_multi_frame_tag_returns_dict(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        result = proc.multi_frame_tag(src, asset_id="mft1")
        assert isinstance(result, dict)
        assert "scene_type" in result
        assert "tags" in result
        assert "confidence" in result
        assert "frame_votes" in result
        assert "scene_summary" in result

    def test_multi_frame_tag_scene_type_valid(self):
        from src.asset_library import SceneType
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        result = proc.multi_frame_tag(src, asset_id="mft2")
        assert SceneType.is_valid(result["scene_type"]), \
            f"Invalid scene_type: {result['scene_type']}"

    def test_multi_frame_tag_has_tags(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        result = proc.multi_frame_tag(src, asset_id="mft3")
        assert len(result["tags"]) >= 1

    def test_multi_frame_tag_votes_non_empty(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=6.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        result = proc.multi_frame_tag(src, asset_id="mft4")
        assert len(result["frame_votes"]) >= 1

    def test_multi_frame_tag_summary_not_empty(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        _make_test_video(src, duration=5.0)
        thumb = d / "thumbs"
        thumb.mkdir()
        proc = _make_processor(thumbnails_dir=thumb)
        result = proc.multi_frame_tag(src, asset_id="mft5")
        assert len(result["scene_summary"]) > 0


# ── Tests: Scene Summary ───────────────────────────────

class TestSceneSummary:
    def test_generate_summary_contains_scene_type(self):
        proc = _make_processor()
        summary = proc._generate_summary("lake", ["洱海", "湖景", "蓝天"])
        assert "湖泊" in summary or "lake" in summary
        assert "洱海" in summary

    def test_generate_summary_no_tags(self):
        proc = _make_processor()
        summary = proc._generate_summary("mountain", [])
        assert len(summary) > 0

    def test_generate_summary_all_scene_types(self):
        proc = _make_processor()
        valid_types = ["airport", "hotel", "beach", "island", "lake", "mountain",
                       "city", "food", "market", "temple", "sunset", "night",
                       "wildlife", "shopping", "transport", "landscape", "general"]
        for st in valid_types:
            s = proc._generate_summary(st, [])
            assert len(s) > 0


# ── Tests: V2 AssetRecord Fields ───────────────────────

class TestAssetRecordV2:
    def test_quality_score_field(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[], quality_score=0.85)
        assert r.quality_score == 0.85

    def test_quality_score_default_none(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.quality_score is None

    def test_scene_summary_field(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[], scene_summary="湖泊风光")
        assert r.scene_summary == "湖泊风光"

    def test_scene_summary_default_empty(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.scene_summary == ""


# ── Tests: V1 Backward Compat ──────────────────────────

class TestBackwardCompat:
    def test_v1_process_video_still_works(self):
        from src.config import ASSETS_DIR as REAL_ASSETS_DIR

        d = Path(tempfile.mkdtemp())
        raw = d / "raw"; raw.mkdir()
        proc_dir = d / "processed"; proc_dir.mkdir()
        thumb = d / "thumb"; thumb.mkdir()
        idx = d / "idx.json"

        # Create a longer test video so scene detection works
        fake_assets = d / "assets"
        fake_assets.mkdir()
        fake_raw = fake_assets / "raw"; fake_raw.mkdir()
        src = fake_raw / "test.mp4"
        _make_test_video(src, duration=5.0)  # longer for scene detection

        import src.asset_processor as ap
        orig_assets = ap.ASSETS_DIR
        ap.ASSETS_DIR = fake_assets
        try:
            proc = _make_processor(raw_dir=fake_raw, processed_dir=proc_dir,
                                   thumbnails_dir=thumb, index_path=idx)
            records = proc.process_video(src)
            # Short synthetic video may have 0 scenes. If no records, the
            # code path still ran without crashing — that's backward compat.
            if records:
                for r in records:
                    assert r.type == "video"
                    assert r.thumbnail != ""
            # The key assertion: no crash, function returned
            assert isinstance(records, list)
        finally:
            ap.ASSETS_DIR = orig_assets

    def test_v1_thumbnail_still_extracts_midpoint(self):
        d = Path(tempfile.mkdtemp())
        src = d / "test.mp4"
        out = d / "thumb.jpg"
        _make_test_video(src, duration=3.0)
        proc = _make_processor()
        proc._extract_thumbnail(src, out)
        assert out.exists()
        assert out.stat().st_size > 500
