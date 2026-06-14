"""Shared UI config, voice mapping, and voice preview for the dashboard."""

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Voice Display Name → voice_id Mapping ──────────

VOICE_DISPLAY_TO_ID = {
    "女声｜温柔旅行解说":       "travel_female",
    "男声｜沉稳纪录片旁白":     "travel_male",
    "女声｜清晰攻略讲解":       "story_female",
    "男声｜文艺叙述风格":       "story_male",
    "女声｜活力短视频主播":     "energetic_female",
}

VOICE_ID_TO_DISPLAY = {v: k for k, v in VOICE_DISPLAY_TO_ID.items()}

VOICE_DISPLAY_NAMES = list(VOICE_DISPLAY_TO_ID.keys())

DEFAULT_VOICE_DISPLAY = "女声｜温柔旅行解说"
DEFAULT_VOICE_ID = "travel_female"

# ── Status Label Mapping ───────────────────────────

STATUS_LABELS = {
    "recommended": "✅ 推荐发布",
    "needs_review": "⚠️ 需复查",
    "not_recommended": "❌ 不推荐",
    "ok": "✅ 正常",
    "warning": "⚠️ 警告",
    "failed": "❌ 失败",
    "success": "✅ 成功",
    "missing_tags": "缺少标签",
    "duplicate_source": "来源重复",
    "low_quality": "质量较低",
    "missing_thumbnail": "缺少缩略图",
    "duplicate_assets_present": "存在重复素材",
    "duplicate_assets_high": "重复素材过多",
    "asset_match_too_low": "素材匹配过低",
    "weak_or_missing_bgm": "BGM 缺失或过弱",
    "weak_hook": "开头钩子较弱",
    "pacing_issue": "节奏问题",
    "duration_too_short": "时长过短",
    "duration_too_long": "时长过长",
}

def status_label(key: str) -> str:
    return STATUS_LABELS.get(key, key)


# ── Voice Preview ──────────────────────────────────

VOICE_PREVIEW_DIR = Path("output/voice_preview")
VOICE_PREVIEW_TEXT = "你好，我是你的旅行视频解说员。接下来，我会用这个声音为你生成旅游短视频旁白。"


def get_voice_preview_path(voice_id: str) -> Path:
    """Get the cached preview path for a voice_id."""
    VOICE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    return VOICE_PREVIEW_DIR / f"{voice_id}.mp3"


def generate_voice_preview(voice_id: str) -> Path | None:
    """Generate a short preview audio for the given voice_id. Returns path or None."""
    output_path = get_voice_preview_path(voice_id)

    # Return cached if exists
    if output_path.exists() and output_path.stat().st_size > 500:
        return output_path

    try:
        from src.voice_generator import VoiceGenerator
        from src.config import TTSConfig, VoiceProfile
        from src.config import get_voice_profile

        profile = get_voice_profile(voice_id)
        if not profile:
            # Fallback: use TTSConfig directly
            config = TTSConfig(voice=voice_id)
            gen = VoiceGenerator(tts_config=config, output_dir=VOICE_PREVIEW_DIR, per_scene=False)
        else:
            gen = VoiceGenerator(profile=profile, output_dir=VOICE_PREVIEW_DIR, per_scene=False)

        # Use the merged generation mode for preview
        import asyncio
        import edge_tts

        async def _preview():
            communicate = edge_tts.Communicate(
                text=VOICE_PREVIEW_TEXT,
                voice=voice_id if not profile else profile.voice,
                rate="+0%",
                pitch="+0Hz",
                volume="+0%",
            )
            await communicate.save(str(output_path))

        asyncio.run(_preview())

        if output_path.exists() and output_path.stat().st_size > 500:
            return output_path
        return None
    except Exception as e:
        print(f"Voice preview failed for {voice_id}: {e}")
        return None
