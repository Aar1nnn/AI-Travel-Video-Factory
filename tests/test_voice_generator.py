"""
Voice Generator — Unit Tests (Voice Profile System)

Test cases: profile loading, mood adjustments, per-scene TTS,
FFmpeg concat, backward compatibility, CLI --voice flag.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_voice_generator.py -v
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    TTSConfig, TEMP_DIR, VoiceProfile,
    get_voice_profiles, get_voice_profile,
)
from src.voice_generator import (
    VoiceGenerator, VOICE_FEMALE, VOICE_MALE,
    MOOD_RATE_ADJUSTMENTS,
)
from src.script_generator import Script, Scene


# ── Fixtures ──────────────────────────────────────────

def _make_script(texts: list[str] | None = None) -> Script:
    """Create a minimal Script with given texts."""
    if texts is None:
        texts = [
            "沙巴，马来西亚的宝藏目的地，5天4晚带你玩转热带天堂。",
            "第一天落地亚庇，入住海景酒店，傍晚去丹绒亚路看全球最美日落。",
            "第二天跳岛浮潜，马努干岛的玻璃海让你不想上岸。",
            "沙巴，一个来了就不想走的地方，关注我们获取更多旅行攻略。",
        ]

    moods = ["开场吸引", "轻松惬意", "活力刺激", "结尾号召"]
    scenes = [
        Scene(
            id=i + 1,
            text=t,
            mood=moods[i % len(moods)],
            asset_tags=["test"],
        )
        for i, t in enumerate(texts)
    ]

    return Script(title="测试脚本", topic="测试", scenes=scenes)


def _make_empty_script() -> Script:
    """Create a Script with all empty texts."""
    scenes = [
        Scene(id=1, text="", mood="开场吸引", asset_tags=["test"]),
        Scene(id=2, text="   ", mood="轻松惬意", asset_tags=["test"]),
    ]
    return Script(title="空脚本", topic="测试", scenes=scenes)


def _make_generator(voice: str = VOICE_FEMALE, per_scene: bool = True) -> VoiceGenerator:
    """Create a VoiceGenerator with legacy TTSConfig."""
    config = TTSConfig(provider="edge_tts", voice=voice, rate="+10%")
    return VoiceGenerator(tts_config=config, output_dir=TEMP_DIR, per_scene=per_scene)


def _make_profile_generator(profile_name: str = "travel_female") -> VoiceGenerator:
    """Create a VoiceGenerator from a voice profile."""
    profile = get_voice_profile(profile_name)
    assert profile is not None, f"Profile {profile_name} not found"
    return VoiceGenerator(profile=profile, output_dir=TEMP_DIR)


# ── Tests: Voice Profile Loading ──────────────────────

class TestVoiceProfiles:
    def test_load_all_profiles(self):
        """All 5 profiles load from config/voices.yaml."""
        profiles = get_voice_profiles()
        assert len(profiles) == 5
        expected = {"travel_female", "travel_male", "story_female", "story_male", "energetic_female"}
        assert set(profiles.keys()) == expected

    def test_travel_female_profile(self):
        """travel_female has correct defaults."""
        p = get_voice_profile("travel_female")
        assert p.name == "旅行女声"
        assert p.voice == VOICE_FEMALE
        assert p.rate == "+10%"

    def test_profile_fields(self):
        """All profiles have required fields."""
        for key, p in get_voice_profiles().items():
            assert p.name
            assert p.voice.startswith("zh-CN-")
            assert "%" in p.rate
            assert "Hz" in p.pitch
            assert "%" in p.volume

    def test_missing_profile_returns_none(self):
        """get_voice_profile for unknown name returns None."""
        assert get_voice_profile("nonexistent") is None


# ── Tests: Mood Adjustments ───────────────────────────

class TestMoodAdjustments:
    def test_all_defined_moods_in_map(self):
        """All expected moods have rate adjustments defined."""
        expected = {"开场吸引", "活力刺激", "轻松惬意", "神秘探索", "温馨感人", "结尾号召"}
        for mood in expected:
            assert mood in MOOD_RATE_ADJUSTMENTS, f"Missing mood: {mood}"

    def test_opening_is_faster(self):
        """开场吸引 should increase rate."""
        gen = _make_profile_generator()
        adjusted = gen._adjust_rate("+10%", "开场吸引")
        base_val = 10
        adj_val = int(adjusted.replace("%", "").replace("+", ""))
        assert adj_val > base_val, f"Expected faster than +10%, got {adjusted}"

    def test_relaxed_is_slower(self):
        """轻松惬意 should decrease rate."""
        gen = _make_profile_generator()
        adjusted = gen._adjust_rate("+10%", "轻松惬意")
        base_val = 10
        adj_val = int(adjusted.replace("%", "").replace("+", ""))
        assert adj_val < base_val, f"Expected slower than +10%, got {adjusted}"

    def test_mysterious_is_slowest(self):
        """神秘探索 should have the most negative adjustment."""
        gen = _make_profile_generator()
        adjusted = gen._adjust_rate("+10%", "神秘探索")
        assert adjusted == "+0%" or int(adjusted.replace("%", "").replace("+", "")) <= 0

    def test_unknown_mood_returns_base(self):
        """Unknown mood returns base rate unchanged."""
        gen = _make_profile_generator()
        adjusted = gen._adjust_rate("+15%", "不存在的mood")
        assert adjusted == "+15%"

    def test_rate_bounded(self):
        """Rate stays within Edge TTS range (-50% to +100%)."""
        gen = _make_profile_generator()
        # Test at boundary: base +50%, 活力刺激 +10% = +60% (OK)
        r1 = gen._adjust_rate("+50%", "活力刺激")
        assert "+60%" in r1 or int(r1.replace("%", "").replace("+", "")) <= 100
        # Test at lower bound: base -45%, 神秘探索 -10% = -55% (clamp to -50%)
        r2 = gen._adjust_rate("-45%", "神秘探索")
        val = int(r2.replace("%", "").replace("+", ""))
        assert val >= -50


# ── Tests: Per-Scene TTS ──────────────────────────────

class TestPerSceneTTS:
    """Tests that actually call Edge TTS — requires network."""

    def test_per_scene_generates_scene_files(self):
        """Per-scene mode generates scene_1.mp3, scene_2.mp3, etc."""
        gen = _make_profile_generator()
        script = _make_script()

        output_path = gen.generate(script)

        assert output_path.exists()
        assert output_path.name == "voice.mp3"

        # Check that scene files exist
        from pathlib import Path
        for scene in script.scenes:
            if scene.text.strip():
                scene_file = TEMP_DIR / f"scene_{scene.id}.mp3"
                assert scene_file.exists(), f"Missing: {scene_file}"
                assert scene_file.stat().st_size > 500

    def test_voice_mp3_is_valid(self):
        """Output voice.mp3 is valid and contains all scenes."""
        gen = _make_profile_generator()
        script = _make_script()

        output = gen.generate(script)
        size_kb = output.stat().st_size / 1024
        assert size_kb > 1.0, f"Expected > 1KB, got {size_kb:.1f} KB"

    def test_concat_single_file(self):
        """_concat_mp3 with single file copies correctly."""
        gen = _make_profile_generator()
        # Generate one scene
        script = _make_script(["测试文本。"])
        gen_per = VoiceGenerator(profile=gen.profile, output_dir=TEMP_DIR, per_scene=True)
        output = gen_per.generate(script)
        assert output.exists()
        assert output.stat().st_size > 500


# ── Tests: Backward Compatibility ─────────────────────

class TestBackwardCompat:
    """Legacy TTSConfig-based initialisation still works."""

    def test_legacy_tts_config_female(self):
        """Legacy generator with female voice works."""
        gen = _make_generator(VOICE_FEMALE, per_scene=False)
        script = _make_script()
        output_path = gen.generate(script)
        assert output_path.exists()
        assert output_path.stat().st_size > 500

    def test_legacy_tts_config_male(self):
        """Legacy generator with male voice works."""
        gen = _make_generator(VOICE_MALE, per_scene=False)
        script = _make_script()
        output_path = gen.generate(script)
        assert output_path.exists()
        assert output_path.stat().st_size > 500

    def test_profile_override_tts_config(self):
        """When profile is provided, it takes priority over tts_config."""
        config = TTSConfig(voice=VOICE_MALE, rate="+50%")
        profile = get_voice_profile("travel_female")
        gen = VoiceGenerator(tts_config=config, profile=profile)
        assert gen.profile.voice == VOICE_FEMALE  # profile wins
        assert gen.profile.rate == "+10%"          # profile wins

    def test_empty_text_raises(self):
        """Script with empty text → ValueError."""
        gen = _make_generator()
        script = _make_empty_script()
        with pytest.raises(ValueError):
            gen.generate(script)


# ── Tests: Text Utilities ─────────────────────────────

def test_collect_scene_texts():
    """_collect_scene_texts returns non-empty texts."""
    gen = _make_generator()
    script = _make_script()
    texts = gen._collect_scene_texts(script)
    assert len(texts) == 4
    assert all(t for t in texts)


def test_join_script_text():
    """_join_script_text concatenates with punctuation."""
    gen = _make_generator()
    script = _make_script()
    result = gen._join_script_text(script)
    assert len(result) > 0
    assert "。" in result
    assert "沙巴" in result


def test_voice_labels():
    """Available voices should return correct labels."""
    voices = VoiceGenerator.get_available_voices()
    assert len(voices) == 2
    ids = {v["id"] for v in voices}
    assert VOICE_FEMALE in ids
    assert VOICE_MALE in ids


def test_tts_config_defaults():
    """TTSConfig should have sensible defaults."""
    config = TTSConfig()
    assert config.provider == "edge_tts"
    assert config.voice == VOICE_FEMALE
    assert config.rate == "+10%"
    assert config.pitch == "+0Hz"
    assert config.volume == "+0%"


def test_voice_profile_model():
    """VoiceProfile Pydantic model validation."""
    vp = VoiceProfile(name="test", voice="zh-CN-Test", rate="+5%", pitch="+0Hz", volume="+0%")
    assert vp.name == "test"
    assert vp.voice == "zh-CN-Test"
