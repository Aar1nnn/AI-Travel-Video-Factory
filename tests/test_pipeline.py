"""
Pipeline — Unit Tests (MVP)

Test cases: data conversion, init wiring, missing asset detection,
e2e with mocked LLM, SubtitleGenerator, Exporter.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    init_config, AppConfig, ASSETS_DIR, ASSETS_INDEX, TEMP_DIR,
)
from src.pipeline import Pipeline, PipelineResult
from src.asset_library import AssetLibraryManager, MatchedAsset
from src.script_generator import Script, Scene


# ── Helpers ──────────────────────────────────────────────

def _make_matched_asset(id_, path, type_="image", score=0.6):
    return MatchedAsset(
        id=id_,
        path=path,
        type=type_,
        tags=[],
        duration=None,
        match_score=score,
    )


def _make_sample_script():
    return Script(
        title="Test Travel",
        topic="Test Topic",
        scenes=[
            Scene(
                id=1,
                text="第一段测试文本十个中文字符测试。",
                mood="开场吸引",
                asset_tags=["海岛", "俯瞰", "沙巴"],
            ),
            Scene(
                id=2,
                text="第二段测试文本也是十个字左右。",
                mood="轻松惬意",
                asset_tags=["日落", "海滩", "沙巴"],
            ),
            Scene(
                id=3,
                text="第三段测试文本再来十个字哦。",
                mood="活力刺激",
                asset_tags=["美食", "海鲜", "夜市"],
            ),
        ],
    )


def _create_pipeline_with_mock_script_gen(config):
    """Create Pipeline with ScriptGenerator.__init__ mocked out."""
    with patch("src.pipeline.ScriptGenerator.__init__", return_value=None):
        p = Pipeline(config, output_dir=TEMP_DIR)
        p.script_gen = MagicMock()
        return p


def _e2e_mock_script():
    """Mock script whose asset_tags match only EXISTING assets on disk."""
    return Script(
        title="Mock Test Travel",
        topic="mock",
        scenes=[
            Scene(
                id=1,
                text="第一段文本用于测试十个字。",
                mood="开场吸引",
                asset_tags=["玻璃海", "跳岛"],
            ),
            Scene(
                id=2,
                text="第二段文本测试匹配十个字。",
                mood="轻松惬意",
                asset_tags=["背景", "通用"],
            ),
        ],
    )


# ── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def config():
    return init_config()


@pytest.fixture
def sample_script():
    return _make_sample_script()


# ── Tests: Data Conversion ───────────────────────────────

class TestBuildScriptWithAssets:
    """Unit tests for _build_script_with_assets."""

    def test_conversion(self, config, sample_script):
        """_build_script_with_assets converts Script + match results correctly."""
        p = _create_pipeline_with_mock_script_gen(config)
        script_dict = sample_script.model_dump()

        match_results = [
            {"scene_id": 1, "matched_assets": [
                _make_matched_asset("asset_001", "island/manukan_aerial.mp4", "video"),
            ]},
            {"scene_id": 2, "matched_assets": [
                _make_matched_asset("asset_007", "general/travel_compass.jpg", "image"),
            ]},
            {"scene_id": 3, "matched_assets": [
                _make_matched_asset("asset_005", "food/seafood_platter.jpg", "image"),
            ]},
        ]

        result = p._build_script_with_assets(script_dict, match_results)

        assert result["title"] == "Test Travel"
        assert len(result["scenes"]) == 3
        assert result["scenes"][0]["id"] == 1
        assert result["scenes"][0]["assets"][0]["path"] == "island/manukan_aerial.mp4"
        assert result["scenes"][0]["assets"][0]["type"] == "video"

    def test_multi_assets_per_scene(self, config, sample_script):
        """Multiple assets per scene are preserved."""
        p = _create_pipeline_with_mock_script_gen(config)
        script_dict = sample_script.model_dump()
        match_results = [
            {"scene_id": 1, "matched_assets": [
                _make_matched_asset("a1", "p1.jpg"),
                _make_matched_asset("a2", "p2.jpg"),
            ]},
            {"scene_id": 2, "matched_assets": [
                _make_matched_asset("a3", "p3.jpg"),
            ]},
            {"scene_id": 3, "matched_assets": [
                _make_matched_asset("a4", "p4.mp4", "video"),
            ]},
        ]
        result = p._build_script_with_assets(script_dict, match_results)
        assert len(result["scenes"][0]["assets"]) == 2
        assert len(result["scenes"][1]["assets"]) == 1
        assert len(result["scenes"][2]["assets"]) == 1

    def test_missing_match_uses_fallback(self, config, sample_script):
        """Scene with no matched assets uses the fallback asset."""
        p = _create_pipeline_with_mock_script_gen(config)
        script_dict = sample_script.model_dump()
        match_results = [
            {"scene_id": 1, "matched_assets": [_make_matched_asset("a1", "p1.jpg")]},
            {"scene_id": 2, "matched_assets": []},
            {"scene_id": 3, "matched_assets": [_make_matched_asset("a3", "p3.jpg")]},
        ]
        result = p._build_script_with_assets(script_dict, match_results)
        assert result["scenes"][1]["assets"][0]["path"] == "general/travel_compass.jpg"


# ── Tests: Init & Wiring ─────────────────────────────────

def test_pipeline_init_creates_modules(config):
    """Pipeline.__init__ creates all 6 sub-module instances."""
    with patch("src.pipeline.ScriptGenerator.__init__", return_value=None):
        p = Pipeline(config, output_dir=TEMP_DIR)
        p.script_gen = MagicMock()

    assert p.script_gen is not None
    assert p.asset_mgr is not None
    assert p.voice_gen is not None
    assert p.subtitle_gen is not None
    assert p.composer is not None
    assert p.exporter is not None

    from src.asset_library import AssetLibraryManager
    from src.voice_generator import VoiceGenerator
    from src.subtitle_generator import SubtitleGenerator
    from src.video_composer import VideoComposer
    from src.exporter import Exporter

    assert isinstance(p.asset_mgr, AssetLibraryManager)
    assert isinstance(p.voice_gen, VoiceGenerator)
    assert isinstance(p.subtitle_gen, SubtitleGenerator)
    assert isinstance(p.composer, VideoComposer)
    assert isinstance(p.exporter, Exporter)


def test_pipeline_asset_manager_loads_index(config):
    """Asset manager loads real index.json and has records."""
    with patch("src.pipeline.ScriptGenerator.__init__", return_value=None):
        p = Pipeline(config, output_dir=TEMP_DIR)
        p.script_gen = MagicMock()
    records = p.asset_mgr.get_all_records()
    assert len(records) > 0


# ── Tests: Subtitle Generator ────────────────────────────

class TestSubtitleGenerator:
    """Unit tests for SubtitleGenerator — no disk I/O needed."""

    def test_split_long_line(self, config):
        """_split_long_line splits at punctuation within max_chars."""
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())

        # Short text stays intact
        assert sg._split_long_line("短文本", 18) == ["短文本"]

        # Long text split at punctuation
        result = sg._split_long_line("第一句十五个字，第二句也差不多十五字。", 18)
        assert len(result) >= 2
        assert all(len(t) <= 18 for t in result)

        # Very long without punctuation — hard split
        long_text = "A" * 30
        result = sg._split_long_line(long_text, 18)
        assert all(len(t) <= 18 for t in result)

    def test_split_segments(self, config):
        """_split_segments splits Whisper segments into max_chars lines."""
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())

        segments = [
            {"start": 0.0, "end": 2.0, "text": "短文本"},
            {"start": 2.0, "end": 6.0, "text": "这是一段超过十八个中文字符的长文本需要被切分成多个短行显示"},
        ]
        result = sg._split_segments(segments, max_chars=18)
        assert len(result) >= 2
        for seg in result:
            assert len(seg["text"]) <= 18
            assert "start" in seg
            assert "end" in seg

    def test_seconds_to_srt_time(self, config):
        """_seconds_to_srt_time formats correctly."""
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())

        assert sg._seconds_to_srt_time(0.0) == "00:00:00,000"
        assert sg._seconds_to_srt_time(1.5) == "00:00:01,500"
        assert sg._seconds_to_srt_time(61.0) == "00:01:01,000"
        assert sg._seconds_to_srt_time(3661.0) == "01:01:01,000"

    def test_to_srt(self, config):
        """_to_srt generates valid SRT format."""
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())

        segments = [
            {"start": 0.0, "end": 2.5, "text": "第一段字幕"},
            {"start": 2.5, "end": 5.0, "text": "第二段字幕"},
        ]
        srt = sg._to_srt(segments)
        lines = srt.split("\n")
        assert lines[0] == "1"
        assert lines[1] == "00:00:00,000 --> 00:00:02,500"
        assert lines[2] == "第一段字幕"
        assert lines[3] == ""
        assert lines[4] == "2"

    def test_generate_missing_file(self, config):
        """Missing voice file raises FileNotFoundError."""
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())
        with pytest.raises(FileNotFoundError):
            sg.generate(Path("/nonexistent/voice.mp3"))


# ── Tests: Exporter ──────────────────────────────────────

class TestExporter:
    """Unit tests for Exporter."""

    def test_export_creates_files(self, config):
        """Export copies video and writes metadata."""
        from src.exporter import Exporter
        # Use a known existing video as source
        src_video = TEMP_DIR / "composed_video.mp4"
        if not src_video.exists():
            pytest.skip("composed_video.mp4 not found — run full pipeline first")

        exporter = Exporter(output_dir=TEMP_DIR, temp_dir=TEMP_DIR, cleanup=False)
        result = exporter.export(
            composed_video_path=src_video,
            topic="Test Export",
            metadata={"topic": "Test Export", "duration": 10.0},
        )
        assert result.video_path.exists()
        assert result.metadata_path.exists()
        assert result.file_size_mb > 0

    def test_sanitize_filename(self, config):
        """_sanitize_filename removes unsafe chars."""
        from src.exporter import Exporter
        exporter = Exporter(output_dir=TEMP_DIR, temp_dir=TEMP_DIR)
        assert ":" not in exporter._sanitize_filename("a:b")
        assert "/" not in exporter._sanitize_filename("a/b")
        assert len(exporter._sanitize_filename("A" * 100)) <= 50

    def test_export_missing_file(self, config):
        """Missing source video raises FileNotFoundError."""
        from src.exporter import Exporter
        exporter = Exporter(output_dir=TEMP_DIR, temp_dir=TEMP_DIR)
        with pytest.raises(FileNotFoundError):
            exporter.export(Path("/nonexistent/video.mp4"), "Test", {})


# ── Tests: PipelineResult Model ──────────────────────────

def test_pipeline_result_model():
    """PipelineResult Pydantic model validation."""
    result = PipelineResult(
        script_path=TEMP_DIR / "script.json",
        script_with_assets_path=TEMP_DIR / "script_with_assets.json",
        voice_path=TEMP_DIR / "voice.mp3",
        subtitle_path=TEMP_DIR / "subtitles.srt",
        composed_video_path=TEMP_DIR / "composed_video.mp4",
        final_video_path=TEMP_DIR / "final.mp4",
        metadata_path=TEMP_DIR / "metadata.json",
        duration=30.0,
        scene_count=5,
        asset_count=15,
        file_size_mb=2.5,
    )
    assert result.duration == 30.0
    assert result.scene_count == 5
    assert result.file_size_mb == 2.5
    assert result.resolution == "1080x1920"
