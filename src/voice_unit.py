"""
模块: VoiceUnit（句子级剪辑单元 — VQ1）

定义 VoiceUnit 数据结构和标点切分逻辑。
每个 VoiceUnit = 一句话 = 一个画面 = 一条字幕。
"""

import re
from dataclasses import dataclass, field
from typing import ClassVar


# ── Chinese + English punctuation ──────────────────

_CHINESE_CUT: str = "，。？！；："
_ENGLISH_CUT: str = ",.?!;:"
BOUNDARY_PUNCTUATION: str = _CHINESE_CUT + _ENGLISH_CUT

_SHORT_JOINERS: str = "，,；;：:"


@dataclass
class VoiceUnit:
    """一句话对应一个画面、一条字幕、一段配音。"""
    unit_id: int
    scene_id: int
    text: str                          # 完整文本（含标点）
    clean_text: str = ""               # 去标点的纯文本（用于 TTS）
    punct: str = ""                    # 结尾标点
    scene_type: str = "general"
    mood: str = ""
    asset_tags: list[str] = field(default_factory=list)
    visual_intent: str = ""            # "俯瞰/湖景/古城/美食..."

    # Timing — filled after TTS
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    # Asset — filled after matching
    selected_asset_id: str = ""
    selected_asset_path: str = ""
    selected_asset_type: str = "video"
    is_fallback: bool = False
    risk_flag: str = ""
    risk_flags: list[str] = field(default_factory=list)

    # Minimum unit length (Chinese characters after stripping punctuation)
    MIN_CHARS: ClassVar[int] = 4
    MAX_CHARS: ClassVar[int] = 24
    PAUSE_MS: ClassVar[int] = 100      # pause between units (ms)


# ── Split Logic ────────────────────────────────────

def split_by_punctuation(text: str) -> list[str]:
    """
    按标点切分句子。保留标点。过滤纯空白。

    "大理古城，苍山脚下。洱海骑行！"
    → ["大理古城，", "苍山脚下。", "洱海骑行！"]
    """
    if not text or not text.strip():
        return []

    pattern = f"([{re.escape(BOUNDARY_PUNCTUATION)}])"
    parts = re.split(pattern, text)

    result = []
    buf = ""
    for p in parts:
        if not p:
            continue
        if p in BOUNDARY_PUNCTUATION:
            buf += p
            result.append(buf)
            buf = ""
        else:
            buf += p
    if buf.strip():
        result.append(buf)

    return [r for r in result if r.strip()]


def _char_count(text: str) -> int:
    """Count Chinese characters (exclude punctuation + whitespace)."""
    cleaned = re.sub(rf"[{re.escape(BOUNDARY_PUNCTUATION)}\s]", "", text)
    return len(cleaned)


def merge_short_units(units: list[str], min_chars: int = 4) -> list[str]:
    """合并过短的分句。"""
    if not units:
        return []
    merged = []
    buf = ""
    for u in units:
        if _char_count(u) < min_chars and buf:
            buf += u
        elif _char_count(u) < min_chars:
            buf = u
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(u)
    if buf:
        if merged and _char_count(buf) < min_chars:
            merged[-1] += buf
        else:
            merged.append(buf)
    return merged


def split_long_units(units: list[str], max_chars: int = 24) -> list[str]:
    """拆分过长 (>max_chars) 的分句。"""
    result = []
    for u in units:
        if _char_count(u) <= max_chars:
            result.append(u)
            continue
        # Try to cut at short joiners (，, ;, ：)
        sub_pattern = f"([{re.escape(_SHORT_JOINERS)}])"
        sub_parts = re.split(sub_pattern, u)
        sub_merged = []
        buf = ""
        for p in sub_parts:
            if not p:
                continue
            if p in _SHORT_JOINERS:
                buf += p
                sub_merged.append(buf)
                buf = ""
            else:
                buf += p
        if buf.strip():
            sub_merged.append(buf)
        # Recurse: if still too long, hard-cut at mid
        for s in sub_merged:
            if _char_count(s) > max_chars:
                # Hard cut: try to split evenly
                half = len(s) // 2
                # Find nearest short joiner
                for ch in _SHORT_JOINERS:
                    pos = s.find(ch, half - 8)
                    if 0 < pos < half + 8:
                        half = pos + 1
                        break
                result.append(s[:half])
                result.append(s[half:])
            else:
                result.append(s)
    return [r for r in result if r.strip()]


def build_voice_units(script) -> list[VoiceUnit]:
    """
    从 Script 对象构建 VoiceUnit 列表。

    流程: scenes → split_by_punctuation → merge → split long → VoiceUnit.
    """
    units = []
    uid = 0
    for scene in script.scenes:
        text = scene.text.strip()
        if not text:
            continue
        raw = split_by_punctuation(text)
        merged = merge_short_units(raw, VoiceUnit.MIN_CHARS)
        final = split_long_units(merged, VoiceUnit.MAX_CHARS)

        for i, segment in enumerate(final):
            punct = ""
            if segment and segment[-1] in BOUNDARY_PUNCTUATION:
                punct = segment[-1]
            clean = re.sub(rf"[{re.escape(BOUNDARY_PUNCTUATION)}]", "", segment).strip()

            # Estimate visual_intent from asset_tags + mood
            visual = ""
            if scene.asset_tags:
                visual = scene.asset_tags[0]

            units.append(VoiceUnit(
                unit_id=uid,
                scene_id=scene.id,
                text=segment,
                clean_text=clean,
                punct=punct,
                scene_type=getattr(scene, "scene_type", "general"),
                mood=getattr(scene, "mood", ""),
                asset_tags=list(getattr(scene, "asset_tags", [])),
                visual_intent=visual,
            ))
            uid += 1
    return units
