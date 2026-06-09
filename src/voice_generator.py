"""
模块 3: Voice Generator（配音生成器 — Voice Profile System）

职责：
- 根据 scene.mood 自动调整语速
- 按场景逐个生成 TTS 片段 → scene_1.mp3, scene_2.mp3, ...
- FFmpeg 合并所有片段 → voice.mp3
- 支持 voice profiles (config/voices.yaml)
"""

import asyncio
import subprocess
from pathlib import Path

import edge_tts

from src.config import TEMP_DIR, VoiceProfile
from src.utils import ensure_dir


# ── Edge TTS Voice IDs ─────────────────────────────────

VOICE_FEMALE = "zh-CN-XiaoxiaoNeural"   # 女声 — 活泼清晰
VOICE_MALE = "zh-CN-YunxiNeural"        # 男声 — 沉稳自然

VOICE_LABELS = {
    VOICE_FEMALE: "female",
    VOICE_MALE: "male",
}

# ── Mood Adjustments ───────────────────────────────────

# 每种 mood 对基础 rate 的增量（百分比偏移）
# 基础 rate 来自 voice profile，mood 在此基础上加减
MOOD_RATE_ADJUSTMENTS: dict[str, str] = {
    "开场吸引":   "+5%",   # 开场稍快，抓注意力
    "活力刺激":   "+10%",  # 活力场景语速加快
    "轻松惬意":   "-5%",   # 轻松场景放慢
    "神秘探索":   "-10%",  # 神秘感 → 最慢语速
    "温馨感人":   "-5%",   # 温馨放慢
    "结尾号召":   "+5%",   # 结尾号召稍快
}

# ── FFmpeg Path ────────────────────────────────────────

_FFMPEG_BIN = str(Path(
    "C:/Users/aarinsim/AppData/Local/Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1.1-full_build/bin/ffmpeg.exe"
))


# ── Generator ──────────────────────────────────────────

class VoiceGenerator:
    """
    配音生成器。使用 Microsoft Edge TTS（免费，本地运行）。

    新流程（per-scene TTS）：
      1. 对每个 scene 单独生成 TTS → scene_1.mp3, scene_2.mp3, ...
      2. 根据 scene.mood 自动调整语速（在 voice profile 基础上）
      3. FFmpeg concat 合并所有片段 → voice.mp3

    Attributes:
        profile: VoiceProfile 实例（voice, rate, pitch, volume）
        per_scene: 是否按场景生成独立 TTS（默认 True）
        output_dir: 音频输出目录
    """

    def __init__(
        self,
        tts_config=None,
        profile: VoiceProfile | None = None,
        output_dir: Path | None = None,
        per_scene: bool = True,
    ):
        """
        Args:
            tts_config: TTSConfig 实例（向后兼容，优先级低于 profile）
            profile: VoiceProfile 实例（优先使用）
            output_dir: 音频输出目录，默认 TEMP_DIR
            per_scene: 是否按场景生成独立 TTS 片段
        """
        self.per_scene = per_scene
        self.output_dir = output_dir or TEMP_DIR
        ensure_dir(self.output_dir)

        # 优先使用 profile，否则从 tts_config 构造
        if profile:
            self.profile = profile
        elif tts_config:
            self.profile = VoiceProfile(
                name="legacy",
                voice=tts_config.voice,
                rate=tts_config.rate,
                pitch=getattr(tts_config, 'pitch', '+0Hz'),
                volume=getattr(tts_config, 'volume', '+0%'),
            )
        else:
            self.profile = VoiceProfile(
                name="default",
                voice=VOICE_FEMALE,
                rate="+10%",
                pitch="+0Hz",
                volume="+0%",
            )

    # ── Public API ─────────────────────────────────────

    def generate(self, script) -> Path:
        """
        根据脚本生成配音。

        Args:
            script: Script 对象（scenes 列表，每个 scene 有 text 和 mood）

        Returns:
            voice.mp3 的文件路径

        Raises:
            ValueError: 脚本文本为空
            RuntimeError: TTS 生成失败
            FileNotFoundError: 输出文件未成功生成
        """
        texts = self._collect_scene_texts(script)
        if not texts:
            raise ValueError("脚本文本为空，无法生成配音")

        if self.per_scene:
            return self._generate_per_scene(script.scenes)
        else:
            return self._generate_merged(script)

    # ── Per-Scene Generation ───────────────────────────

    def _generate_per_scene(self, scenes: list) -> Path:
        """
        按场景逐个生成 TTS 片段，然后合并。

        流程:
          1. 对每个 scene 调用 Edge TTS → scene_{id}.mp3
          2. 根据 scene.mood 调整语速
          3. FFmpeg concat 合并所有片段 → voice.mp3
        """
        scene_paths = []
        for scene in scenes:
            text = scene.text.strip()
            if not text:
                continue

            scene_path = self.output_dir / f"scene_{scene.id}.mp3"
            mood = getattr(scene, "mood", "")

            # 根据 mood 调整 rate
            rate = self._adjust_rate(self.profile.rate, mood)

            try:
                asyncio.run(self._generate_tts(
                    text=text,
                    voice=self.profile.voice,
                    rate=rate,
                    pitch=self.profile.pitch,
                    volume=self.profile.volume,
                    output_path=scene_path,
                ))
            except Exception as e:
                raise RuntimeError(
                    f"场景 {scene.id} TTS 生成失败: {e}"
                ) from e

            if not scene_path.exists() or scene_path.stat().st_size < 500:
                raise RuntimeError(
                    f"场景 {scene.id} TTS 输出异常: {scene_path}"
                )

            scene_paths.append(scene_path)

        if not scene_paths:
            raise RuntimeError("所有场景 TTS 生成均为空")

        # 合并所有片段
        output_path = self.output_dir / "voice.mp3"
        self._concat_mp3(scene_paths, output_path)

        # 校验
        size_kb = output_path.stat().st_size / 1024
        if size_kb < 0.5:
            raise RuntimeError(f"配音文件异常小 ({size_kb:.1f} KB)")

        n = len(scene_paths)
        print(f"  [VoiceGenerator] [OK] 配音生成: {output_path} "
              f"({size_kb:.1f} KB, {n} 场景)")
        return output_path

    # ── Legacy Merged Generation ───────────────────────

    def _generate_merged(self, script) -> Path:
        """一次生成完整配音（向后兼容旧版行为）。"""
        text = self._join_script_text(script)
        output_path = self.output_dir / "voice.mp3"

        try:
            asyncio.run(self._generate_tts(
                text=text,
                voice=self.profile.voice,
                rate=self.profile.rate,
                pitch=self.profile.pitch,
                volume=self.profile.volume,
                output_path=output_path,
            ))
        except Exception as e:
            raise RuntimeError(f"Edge TTS 配音生成失败: {e}") from e

        if not output_path.exists():
            raise FileNotFoundError(f"配音文件未生成: {output_path}")

        size_kb = output_path.stat().st_size / 1024
        if size_kb < 0.5:
            raise RuntimeError(f"配音文件异常小 ({size_kb:.1f} KB)")

        print(f"  [VoiceGenerator] [OK] 配音生成: {output_path} ({size_kb:.1f} KB)")
        return output_path

    # ── TTS Core ───────────────────────────────────────

    async def _generate_tts(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        output_path: Path,
    ) -> None:
        """异步调用 Edge TTS 生成 MP3。"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(str(output_path))

    # ── Audio Merge ────────────────────────────────────

    def _concat_mp3(self, input_paths: list[Path], output_path: Path) -> None:
        """
        使用 FFmpeg concat demuxer 合并多个 MP3 文件。

        Args:
            input_paths: 输入 MP3 文件路径列表
            output_path: 输出文件路径
        """
        if len(input_paths) == 1:
            # 只有一个片段，直接复制
            import shutil
            shutil.copy2(input_paths[0], output_path)
            return

        # 写入 concat 列表
        concat_file = self.output_dir / "concat_voice_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in input_paths:
                f.write(f"file '{p.resolve().as_posix()}'\n")

        cmd = [
            _FFMPEG_BIN, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg 合并配音失败: {result.stderr.strip()[-300:]}"
            )

    # ── Rate Adjustment ─────────────────────────────────

    def _adjust_rate(self, base_rate: str, mood: str) -> str:
        """
        根据 scene.mood 调整语速。

        规则：
          - 如果 mood 有定义调整值，在基础 rate 上叠加
          - 如果 mood 未定义，返回基础 rate
          - 合成一个有效的 rate 字符串（如 "+15%" 或 "-5%"）

        Args:
            base_rate: voice profile 的基础语速（如 "+10%"）
            mood: scene.mood（如 "开场吸引"）

        Returns:
            调整后的语速字符串
        """
        if not mood or mood not in MOOD_RATE_ADJUSTMENTS:
            return base_rate

        # 解析基础 rate
        base_val = int(base_rate.replace("%", "").replace("+", ""))
        adj_str = MOOD_RATE_ADJUSTMENTS[mood]
        adj_val = int(adj_str.replace("%", "").replace("+", ""))

        # 叠加
        new_val = base_val + adj_val
        new_val = max(-50, min(100, new_val))  # 限制在 Edge TTS 有效范围内

        if new_val >= 0:
            return f"+{new_val}%"
        else:
            return f"{new_val}%"

    # ── Text Utilities ─────────────────────────────────

    def _collect_scene_texts(self, script) -> list[str]:
        """收集所有非空场景文本。"""
        texts = []
        for scene in script.scenes:
            t = scene.text.strip()
            if t:
                texts.append(t)
        return texts

    def _join_script_text(self, script) -> str:
        """将所有场景文本拼接为完整旁白（向后兼容）。"""
        texts = self._collect_scene_texts(script)
        if not texts:
            return ""
        return "。".join(texts) + "。"

    # ── Class Methods ──────────────────────────────────

    @classmethod
    def get_available_voices(cls) -> list[dict]:
        """返回可用音色列表。"""
        return [
            {"id": VOICE_FEMALE, "label": "female", "name": "晓晓 (女声)"},
            {"id": VOICE_MALE, "label": "male", "name": "云希 (男声)"},
        ]
