"""
模块 4: Subtitle Generator（字幕生成器 — MVP 版本）

职责：
- 用 Whisper 对 voice.mp3 做语音识别
- 获取 segment 级时间戳
- 每行 ≤ 18 字，长句自动拆分
- 生成 SRT 格式字幕
"""

import os
import re
from pathlib import Path

import whisper

from src.config import WhisperConfig, TEMP_DIR
from src.utils import ensure_dir

# Ensure FFmpeg is in PATH (Whisper needs ffmpeg for audio decoding)
import shutil as _shutil
_ffmpeg_path = _shutil.which("ffmpeg")
if _ffmpeg_path:
    _ffmpeg_dir = str(Path(_ffmpeg_path).parent)
    if _ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


class SubtitleGenerator:
    """
    字幕生成器。使用 OpenAI Whisper 本地模型做语音识别。

    Attributes:
        whisper_config: WhisperConfig 实例（model, language 等）
        output_dir: 输出目录
        _model: Whisper 模型实例（懒加载）
    """

    def __init__(self, whisper_config: WhisperConfig, output_dir: Path | None = None):
        self.whisper_config = whisper_config
        self.output_dir = output_dir or TEMP_DIR
        self._model = None
        ensure_dir(self.output_dir)

    # ── Public API ───────────────────────────────────────

    def generate(self, voice_path: Path) -> Path:
        """
        从配音音频生成 SRT 字幕。

        流程：
            voice.mp3 → Whisper 转录 → segments (start/end/text)
            → 切分长句 → 生成 SRT 格式

        Args:
            voice_path: voice.mp3 文件路径

        Returns:
            subtitles.srt 文件路径

        Raises:
            FileNotFoundError: 配音文件不存在
            RuntimeError: Whisper 转录失败
        """
        if not voice_path.exists():
            raise FileNotFoundError(f"配音文件不存在: {voice_path}")

        # 1. 加载模型（懒加载 + 缓存）
        model = self._load_model()

        # 2. Whisper 转录
        print(f"  [SubtitleGenerator] Whisper 转录中...")
        result = model.transcribe(
            str(voice_path),
            language=self.whisper_config.language,
            word_timestamps=self.whisper_config.word_timestamps,
        )

        # 3. 提取 segments
        raw_segments = result.get("segments", [])
        if not raw_segments:
            raise RuntimeError("Whisper 转录结果没有 segments")

        # 4. 拆分长句 → 每行 ≤ 18 字
        segments = self._split_segments(raw_segments, max_chars=18)

        # 5. 转为 SRT 格式
        srt_text = self._to_srt(segments)

        # 6. 保存
        output_path = self.output_dir / "subtitles.srt"
        output_path.write_text(srt_text, encoding="utf-8")

        print(f"  [SubtitleGenerator] [OK] 字幕生成: {output_path} "
              f"({len(segments)} 条)")
        return output_path

    # ── Model ────────────────────────────────────────────

    def _load_model(self):
        """懒加载 Whisper 模型（首次调用时下载到本地缓存）。"""
        if self._model is None:
            model_name = self.whisper_config.model
            print(f"  [SubtitleGenerator] 加载 Whisper 模型: {model_name}...")
            self._model = whisper.load_model(model_name)
        return self._model

    # ── Text Splitting ───────────────────────────────────

    def _split_segments(self, raw_segments: list[dict], max_chars: int = 18) -> list[dict]:
        """
        将 Whisper segments 中的长文本切分为短行。

        规则：
        - 每行 ≤ max_chars 个中文字符
        - 优先在标点处断行（，。！？、；：）
        - 无标点时按字符数硬切

        Args:
            raw_segments: Whisper segments 列表
            max_chars: 每行最大字符数

        Returns:
            拆分后的 segments 列表（保留 start/end 时间估算）
        """
        result = []
        for seg in raw_segments:
            text = seg["text"].strip()
            if not text:
                continue

            start = seg["start"]
            end = seg["end"]
            duration = end - start

            # 如果文本不长，直接保留
            if len(text) <= max_chars:
                result.append({"start": start, "end": end, "text": text})
                continue

            # 长句 → 按标点拆分，均分时间
            sub_texts = self._split_long_line(text, max_chars)
            sub_duration = duration / len(sub_texts)

            for i, sub in enumerate(sub_texts):
                result.append({
                    "start": round(start + i * sub_duration, 3),
                    "end": round(start + (i + 1) * sub_duration, 3),
                    "text": sub,
                })

        return result

    def _split_long_line(self, text: str, max_chars: int = 18) -> list[str]:
        """
        按标点符号切分长文本。

        Args:
            text: 原始文本
            max_chars: 每行最大字符数

        Returns:
            切分后的文本列表
        """
        result = []
        remaining = text

        while remaining:
            if len(remaining) <= max_chars:
                result.append(remaining)
                break

            # 在 max_chars 范围内找最后一个标点
            chunk = remaining[:max_chars]
            punct_positions = [
                chunk.rfind(p)
                for p in ["，", "。", "！", "？", "、", "；", "：", " ", ","]
            ]
            split_at = max(punct_positions) if any(p >= 0 for p in punct_positions) else -1

            if split_at >= max_chars // 2:  # 标点位置合理（不在太前面）
                cut = split_at + 1  # 包含标点
            else:
                cut = max_chars  # 硬切

            result.append(remaining[:cut])
            remaining = remaining[cut:]

        # 过滤空字符串
        return [r for r in result if r.strip()]

    # ── SRT Formatting ───────────────────────────────────

    def _to_srt(self, segments: list[dict]) -> str:
        """
        将 segments 列表转为 SRT 格式字符串。

        SRT 格式:
            1
            00:00:00,000 --> 00:00:02,500
            字幕文本

            2
            00:00:02,500 --> 00:00:05,000
            字幕文本

        Args:
            segments: [{"start": 0.0, "end": 2.5, "text": "..."}, ...]

        Returns:
            SRT 格式文本
        """
        lines = []
        for i, seg in enumerate(segments, 1):
            start_ts = self._seconds_to_srt_time(seg["start"])
            end_ts = self._seconds_to_srt_time(seg["end"])
            lines.append(str(i))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(seg["text"])
            lines.append("")  # 空行分隔
        return "\n".join(lines)

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """
        将秒数转换为 SRT 时间格式 HH:MM:SS,mmm。

        Args:
            seconds: 浮点秒数

        Returns:
            SRT 时间字符串，如 "00:01:23,456"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
