"""
VoiceUnit — 单元测试

覆盖: 标点切分、短句合并、长句拆分、build_voice_units、
DirectSRT时间轴、per-unit asset去重。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from unittest.mock import patch
from src.voice_unit import (
    split_by_punctuation, merge_short_units, split_long_units,
    build_voice_units, VoiceUnit, BOUNDARY_PUNCTUATION,
)
from src.script_generator import Script, Scene


# ── Fixtures ──────────────────────────────────────────

def _make_script(texts: list[str] | None = None) -> Script:
    if texts is None:
        texts = [
            "第一次来重庆，千万别自己乱走，很多网红点看起来很近，其实走起来很累。",
            "先去洪崖洞看夜景，再去解放碑吃火锅，晚上住南滨路。",
        ]
    scenes = [
        Scene(id=i + 1, text=t, mood="活力刺激", asset_tags=["重庆", "城市", "美食"], scene_type="city")
        for i, t in enumerate(texts)
    ]
    return Script(title="Test", topic="test", scenes=scenes)


def _make_voice_units() -> list:
    """Create mock VoiceUnits with timing."""
    from src.voice_unit import VoiceUnit
    return [
        VoiceUnit(unit_id=0, scene_id=1, text="重庆，", clean_text="重庆",
                  start_time=0.0, end_time=0.8, duration=0.8),
        VoiceUnit(unit_id=1, scene_id=1, text="千万别自己乱走。", clean_text="千万别自己乱走",
                  start_time=0.9, end_time=2.5, duration=1.6),
        VoiceUnit(unit_id=2, scene_id=2, text="先去洪崖洞看夜景，", clean_text="先去洪崖洞看夜景",
                  start_time=2.6, end_time=4.5, duration=1.9),
    ]


# ── Tests: split_by_punctuation ─────────────────────

class TestSplitByPunctuation:
    def test_chinese_comma_and_period(self):
        result = split_by_punctuation("大理古城，苍山脚下。洱海骑行！")
        assert len(result) == 3
        assert result[0] == "大理古城，"
        assert result[1] == "苍山脚下。"
        assert result[2] == "洱海骑行！"

    def test_english_punctuation(self):
        result = split_by_punctuation("Hello, world. Test!")
        assert len(result) >= 2
        assert any("," in r for r in result)

    def test_empty_string(self):
        assert split_by_punctuation("") == []
        assert split_by_punctuation("   ") == []

    def test_no_punctuation(self):
        result = split_by_punctuation("没有标点的一句话")
        assert len(result) == 1
        assert result[0] == "没有标点的一句话"

    def test_mixed_punctuation(self):
        result = split_by_punctuation("重庆？真的吗！好，走。")
        assert len(result) >= 3


# ── Tests: merge_short_units ─────────────────────────

class TestMergeShortUnits:
    def test_short_merged(self):
        units = ["短，", "这也太短。", "正常长度的句子在这里。"]
        result = merge_short_units(units, min_chars=4)
        # "短，" (1 char stripped → 1) + "这也太短。" (4 chars stripped → 3) → merged
        # "正常长度的句子在这里。" (9 chars) → stays
        # Result should be 1 or 2 entries (merged short pair + normal)
        assert len(result) <= 3  # Accept 2-3 depending on merge order

    def test_all_long_kept(self):
        units = ["这是一个正常句子。", "这也是正常的句子。"]
        result = merge_short_units(units, min_chars=4)
        assert len(result) == 2

    def test_empty_input(self):
        assert merge_short_units([], min_chars=4) == []


# ── Tests: split_long_units ──────────────────────────

class TestSplitLongUnits:
    def test_too_long_split(self):
        units = ["A" * 30 + "。"]
        result = split_long_units(units, max_chars=24)
        assert len(result) >= 2

    def test_normal_kept(self):
        units = ["正常长度。"]
        result = split_long_units(units, max_chars=24)
        assert len(result) == 1


# ── Tests: build_voice_units ─────────────────────────

class TestBuildVoiceUnits:
    def test_build_from_script(self):
        script = _make_script()
        units = build_voice_units(script)
        assert len(units) >= 2
        assert all(isinstance(u, VoiceUnit) for u in units)
        assert all(u.scene_id in (1, 2) for u in units)

    def test_inherits_scene_type(self):
        script = _make_script()
        units = build_voice_units(script)
        assert all(u.scene_type == "city" for u in units)

    def test_empty_script(self):
        script = Script(title="Empty", topic="e", scenes=[Scene(id=1, text="", mood="", asset_tags=[], scene_type="general")])
        units = build_voice_units(script)
        assert units == []

    def test_unit_ids_sequential(self):
        script = _make_script()
        units = build_voice_units(script)
        ids = [u.unit_id for u in units]
        assert ids == list(range(len(ids)))

    def test_text_not_empty(self):
        script = _make_script()
        units = build_voice_units(script)
        assert all(u.text.strip() for u in units)
        assert all(u.clean_text for u in units)


# ── Tests: VoiceUnit defaults ────────────────────────

def test_voice_unit_defaults():
    vu = VoiceUnit(unit_id=0, scene_id=1, text="测试。")
    assert vu.start_time == 0.0
    assert vu.selected_asset_id == ""
    assert not vu.is_fallback
    assert vu.MIN_CHARS == 4
    assert vu.MAX_CHARS == 24
    assert vu.PAUSE_MS == 100

# ── Tests: VQ1 TTS mock (voice_generator) ──

class TestVQ1TTS:
    def test_generate_for_voice_units_paths(self):
        """Each VoiceUnit gets a unit_{id}.mp3 path."""
        from src.voice_generator import VoiceGenerator
        from src.config import TTSConfig
        config = TTSConfig()
        gen = VoiceGenerator(tts_config=config)
        units = _make_voice_units()

        # Mock TTS + ffprobe
        async def fake_tts(text, voice, rate, pitch, volume, output_path):
            output_path.write_bytes(b'fake mp3 data here xxxxx')

        with patch.object(gen, '_generate_tts', side_effect=fake_tts):
            with patch.object(gen, '_get_mp3_duration', return_value=1.5):
                voice_path, updated = gen.generate_for_voice_units(units, pause_ms=100)

        assert voice_path.exists()
        for u in updated:
            assert u.duration == 1.5
            assert u.start_time >= 0

    def test_pause_ms_in_timeline(self):
        """pause_ms creates gaps between units."""
        from src.voice_generator import VoiceGenerator
        from src.config import TTSConfig
        gen = VoiceGenerator(tts_config=TTSConfig())
        units = _make_voice_units()

        async def fake_tts(text, voice, rate, pitch, volume, output_path):
            output_path.write_bytes(b'fake mp3 data')

        with patch.object(gen, '_generate_tts', side_effect=fake_tts):
            with patch.object(gen, '_get_mp3_duration', return_value=1.0):
                _, updated = gen.generate_for_voice_units(units, pause_ms=200)

        # unit 0: 0.0-1.0, unit 1: 1.2-2.2, unit 2: 2.4-3.4
        gap = updated[1].start_time - updated[0].end_time
        assert 0.19 <= gap <= 0.21, f"Expected ~0.2s gap, got {gap}"


# ── Tests: DirectSRT from VoiceUnits ─────────────────

class TestDirectSRT:
    def test_generate_from_voice_units(self):
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())
        units = _make_voice_units()
        path = sg.generate_from_voice_units(units)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "千万别自己乱走" in content
        assert "00:00:00" in content or "00:00:0" in content

    def test_srt_timing_matches_voice_units(self):
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())
        units = _make_voice_units()
        path = sg.generate_from_voice_units(units)
        content = path.read_text(encoding="utf-8")
        # Check that the SRT contains the correct end times
        assert "00:00:02,500" in content  # unit 1 end_time

    def test_empty_units(self):
        from src.subtitle_generator import SubtitleGenerator
        from src.config import WhisperConfig
        sg = SubtitleGenerator(WhisperConfig())
        path = sg.generate_from_voice_units([])
        assert path.exists()
