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

# ── FFmpeg Path (auto-detect) ──────────────────────────

import shutil as _shutil
_FFMPEG_BIN = _shutil.which("ffmpeg")
_FFPROBE_BIN = _shutil.which("ffprobe")
if not _FFMPEG_BIN:
    raise RuntimeError(
        "FFmpeg not found. Please install FFmpeg and add it to PATH.\n"
        "  Windows: winget install Gyan.FFmpeg\n"
        "  macOS:   brew install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg"
    )


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

    def _generate_tts_sync(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        output_path: Path,
    ) -> None:
        """同步包装器，供 generate_for_voice_units 使用。Mock-friendly。"""
        asyncio.run(self._generate_tts(
            text=text, voice=voice, rate=rate,
            pitch=pitch, volume=volume, output_path=output_path,
        ))

    # ── Audio Merge ────────────────────────────────────

    def _concat_mp3(self, input_paths: list[Path], output_path: Path) -> None:
        """
        使用 FFmpeg concat demuxer 合并多个 MP3 文件。
        如果只有一个文件或 FFmpeg 不可用，直接复制。
        """
        if len(input_paths) == 1:
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

    # ── VQ1: Per-Unit TTS ──────────────────────────────

    def generate_for_voice_units(
        self,
        voice_units: list,
        pause_ms: int = 100,
    ) -> tuple[Path, list]:
        """
        VQ1: 每个 VoiceUnit 独立生成 TTS → 合并 voice.mp3。

        流程:
          1. 每个 unit.clean_text → Edge TTS → unit_{id}.mp3
          2. 用 ffprobe 读取每个 unit mp3 真实 duration
          3. 按 pause_ms 计算累计 start_time / end_time
          4. concat 所有 unit mp3 → voice.mp3

        Args:
            voice_units: VoiceUnit 列表（已有 clean_text）
            pause_ms: unit 间静音间隔（毫秒）

        Returns:
            (voice.mp3 路径, 更新后的 voice_units)
        """
        import json as _json

        unit_paths = []
        updated_units = list(voice_units)

        # Step 1: Generate per-unit TTS
        for unit in updated_units:
            text = unit.clean_text
            if not text or not text.strip():
                continue
            unit_path = self.output_dir / f"unit_{unit.unit_id}.mp3"
            # Check if file already exists (test pre-created) or generate
            if not unit_path.exists() or unit_path.stat().st_size < 500:
                try:
                    self._generate_tts_sync(
                        text=text,
                        voice=self.profile.voice,
                        rate=self.profile.rate,
                        pitch=self.profile.pitch,
                        volume=self.profile.volume,
                        output_path=unit_path,
                    )
                except Exception as e:
                    raise RuntimeError(
                        f"Unit {unit.unit_id} TTS 生成失败: {e}"
                    ) from e

            if not unit_path.exists() or unit_path.stat().st_size < 500:
                raise RuntimeError(f"Unit {unit.unit_id} TTS 输出异常: {unit_path}")
            unit_paths.append((unit, unit_path))

        # Step 2: Probe durations and compute timeline
        cumulative = 0.0
        timeline_units = []
        pause_sec = pause_ms / 1000.0

        for unit, path in unit_paths:
            dur = self._get_mp3_duration(path) or 1.0
            unit.start_time = round(cumulative, 3)
            unit.end_time = round(cumulative + dur, 3)
            unit.duration = round(dur, 3)
            cumulative = unit.end_time + pause_sec
            timeline_units.append(unit)

        # Gather all valid paths
        all_paths = []
        for unit, path in unit_paths:
            # Re-read path in case it changed
            p = self.output_dir / f"unit_{unit.unit_id}.mp3"
            if p.exists():
                all_paths.append(p)

        # Step 3: Concat
        if not all_paths:
            raise RuntimeError("没有生成任何 unit TTS 片段")

        output_path = self.output_dir / "voice.mp3"
        self._concat_mp3(all_paths, output_path)

        # Validate
        size_kb = output_path.stat().st_size / 1024
        if size_kb < 0.5:
            raise RuntimeError(f"配音文件异常小 ({size_kb:.1f} KB)")

        print(f"  [VoiceGenerator] VQ1 配音生成: {output_path} "
              f"({size_kb:.1f} KB, {len(timeline_units)} units)")
        return output_path, timeline_units

    def _get_mp3_duration(self, mp3_path: Path) -> float | None:
        """用 ffprobe 读取 mp3 时长。"""
        import json as _json
        cmd = [
            _FFPROBE_BIN, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(mp3_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        try:
            data = _json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return None

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
