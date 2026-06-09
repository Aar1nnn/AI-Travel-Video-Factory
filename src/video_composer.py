"""
模块 5: Video Composer（视频合成器 — V3）

V3:
- BGM: find_bgm() now emits warning if no real music found. Returns (path, name).
- Subtitle: ASS format with TikTok style, burned into final video.
- Asset dedup: compose() accepts new signature with dedup support.
"""

import json
import subprocess
import random
import shutil
from pathlib import Path

from pydantic import BaseModel

from src.config import ASSETS_DIR, TEMP_DIR, BGM_DIR, VideoConfig, AudioConfig
from src.utils import ensure_dir


# ── FFmpeg path ───────────────────────────────────────

_FFMPEG_BASE = Path(
    "C:/Users/aarinsim/AppData/Local/Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1.1-full_build/bin"
)

FFMPEG_BIN = str(_FFMPEG_BASE / "ffmpeg.exe")
FFPROBE_BIN = str(_FFMPEG_BASE / "ffprobe.exe")


def _check_ffmpeg():
    if not Path(FFMPEG_BIN).exists():
        raise RuntimeError(f"FFmpeg 未找到: {FFMPEG_BIN}")
    if not Path(FFPROBE_BIN).exists():
        raise RuntimeError(f"FFprobe 未找到: {FFPROBE_BIN}")


# ── Data Models ────────────────────────────────────────

class CompositionResult(BaseModel):
    video_path: Path
    duration: float
    scene_count: int
    asset_count: int
    resolution: str = "1080x1920"


# ── Composer ───────────────────────────────────────────

class VideoComposer:
    """V3: ASS subtitle burn-in + real BGM + asset dedup."""

    def __init__(
        self,
        video_config: VideoConfig | None = None,
        audio_config: AudioConfig | None = None,
        output_dir: Path | None = None,
        temp_dir: Path | None = None,
    ):
        self.video_config = video_config or VideoConfig()
        self.audio_config = audio_config or AudioConfig()
        self.output_dir = output_dir or TEMP_DIR
        self.temp_dir = temp_dir or TEMP_DIR
        ensure_dir(self.output_dir)
        ensure_dir(self.temp_dir)

    # ── Public API ─────────────────────────────────────

    def compose(
        self,
        script_with_assets: dict,
        voice_path: Path,
        subtitle_path: Path | None = None,
        bgm_path: Path | None = None,
    ) -> CompositionResult:
        _check_ffmpeg()

        if not voice_path.exists():
            raise FileNotFoundError(f"配音文件不存在: {voice_path}")

        scenes = script_with_assets.get("scenes", [])
        if not scenes:
            raise ValueError("场景列表为空")

        voice_duration = self._get_audio_duration(voice_path)
        scene_durations = self._calculate_scene_durations(scenes, voice_duration)

        # Process assets → clips (with dedup tracking)
        clip_paths = []
        total_assets = 0
        used_asset_ids = set()
        duplicate_count = 0

        for scene in scenes:
            sid = scene["id"]
            assets = scene.get("assets", [])
            if not assets:
                raise ValueError(f"场景 {sid} 没有素材")
            scene_dur = scene_durations[sid]
            asset_dur = scene_dur / len(assets)
            for i, asset in enumerate(assets):
                asset_path = self._resolve_asset_path(asset["path"])
                if not asset_path.exists():
                    raise FileNotFoundError(f"素材文件不存在: {asset_path}")
                # Extract asset_id from path
                aid = Path(asset["path"]).stem
                if aid in used_asset_ids:
                    duplicate_count += 1
                used_asset_ids.add(aid)
                clip_path = self._process_asset(asset_path, asset["type"], asset_dur, i)
                clip_paths.append(clip_path)
                total_assets += 1

        # Concat with crossfade transitions
        concat_video = self._concat_with_crossfade(clip_paths, scene_durations)

        # Merge voice + optional BGM + burn subtitles
        output_path = self.output_dir / "composed_video.mp4"
        self._final_render(concat_video, voice_path, subtitle_path, bgm_path, output_path)

        return CompositionResult(
            video_path=output_path,
            duration=voice_duration,
            scene_count=len(scenes),
            asset_count=total_assets,
        )

    # ── Private: Audio ─────────────────────────────────

    def _get_audio_duration(self, audio_path: Path) -> float:
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        cmd = [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
               "-of", "json", str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {result.stderr.strip()}")
        return float(json.loads(result.stdout)["format"]["duration"])

    # ── Private: Timing ────────────────────────────────

    def _calculate_scene_durations(self, scenes: list[dict], total_dur: float) -> dict[int, float]:
        total_chars = sum(len(s.get("text", "")) for s in scenes)
        if total_chars == 0:
            raise ValueError("所有场景文本总字数为 0，无法分配时长")
        return {s["id"]: total_dur * len(s.get("text", "")) / total_chars for s in scenes}

    # ── Private: Asset Processing ──────────────────────

    def _resolve_asset_path(self, relative_path: str) -> Path:
        return (ASSETS_DIR / relative_path).resolve()

    def _process_asset(self, asset_path: Path, asset_type: str, duration: float, index: int) -> Path:
        suffix = asset_path.suffix.lower()
        if asset_type == "image" or suffix in (".jpg", ".jpeg", ".png", ".webp"):
            return self._image_to_clip(asset_path, duration, index)
        else:
            return self._video_to_clip(asset_path, duration, index)

    def _image_to_clip(self, image_path: Path, duration: float, index: int) -> Path:
        output = self.temp_dir / f"clip_img_{index:04d}.mp4"
        w, h, fps = self.video_config.width, self.video_config.height, self.video_config.fps
        cmd = [FFMPEG_BIN, "-y", "-loop", "1", "-i", str(image_path),
               "-t", str(duration),
               "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                      f"fade=t=in:d=0.3,fade=t=out:d=0.3:st={duration-0.3}",
               "-r", str(fps), "-pix_fmt", "yuv420p", str(output)]
        self._run_ffmpeg(cmd, f"图片转视频: {image_path.name}")
        return output

    def _video_to_clip(self, video_path: Path, duration: float, index: int) -> Path:
        output = self.temp_dir / f"clip_vid_{index:04d}.mp4"
        w, h, fps = self.video_config.width, self.video_config.height, self.video_config.fps
        dur_safe = max(duration, 0.6)
        cmd = [FFMPEG_BIN, "-y", "-i", str(video_path),
               "-t", str(duration),
               "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                      f"fade=t=in:d=0.3,fade=t=out:d=0.3:st={dur_safe-0.3}",
               "-r", str(fps), "-pix_fmt", "yuv420p", "-an", str(output)]
        self._run_ffmpeg(cmd, f"视频裁剪: {video_path.name}")
        return output

    # ── Concat with Crossfade ──────────────────────────

    def _concat_with_crossfade(self, clip_paths: list[Path], scene_durations: dict) -> Path:
        if len(clip_paths) == 1:
            return clip_paths[0]

        output = self.temp_dir / "concat_video.mp4"
        concat_file = self.temp_dir / "concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{p.resolve().as_posix()}'\n")

        cmd = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
               "-i", str(concat_file), "-c", "copy", str(output)]
        self._run_ffmpeg(cmd, "片段拼接")
        return output

    # ── Final Render: ASS Subtitle + BGM + Voice ───────

    def _final_render(
        self, video_path: Path, voice_path: Path,
        subtitle_path: Path | None, bgm_path: Path | None,
        output_path: Path,
    ) -> None:
        has_subtitle = subtitle_path and subtitle_path.exists()
        has_bgm = bgm_path and bgm_path.exists()

        audio_inputs = ["-i", str(video_path), "-i", str(voice_path)]
        audio_map = ["-map", "0:v:0", "-map", "1:a:0"]
        filter_complex = ""

        if has_bgm:
            audio_inputs.extend(["-i", str(bgm_path)])
            voice_dur = self._get_audio_duration(voice_path)
            filter_complex += (
                f"[2:a]volume={self.audio_config.bgm_volume},"
                f"afade=t=in:d=1.0,afade=t=out:d=2.0:st={voice_dur-2}[bgm];"
                f"[1:a][bgm]amix=inputs=2:duration=first[amix]"
            )
            audio_map = ["-map", "0:v:0", "-map", "[amix]"]

        if has_subtitle:
            ass_path = self.temp_dir / "subtitles.ass"
            self._srt_to_ass(subtitle_path, ass_path)
            # FFmpeg 8.x subtitles filter — the whole string after = is the path
            # Use the file directly with drawtext from the ASS style? No.
            # Burn via a 2-step approach: hardcode with ffmpeg drawtext from ASS.
            # Actually, the simplest cross-platform way:
            # Encode the ASS with proper escaping using libass wrapper
            ass_str = str(ass_path.resolve()).replace("\\", "/")
            # Escape colons in path
            ass_escaped = ass_str.replace("\\:", "\\\\:").replace(":", "\\:")
            vf_sub = f"subtitles='{ass_escaped}'"

            if filter_complex:
                filter_complex += ";[0:v]" + vf_sub + "[vout]"
                audio_map = ["-map", "[vout]", "-map", "[amix]"]
            else:
                vf_part = vf_sub
                audio_inputs = ["-i", str(video_path), "-i", str(voice_path)]
                audio_map = ["-map", "0:v:0", "-map", "1:a:0"]
                cmd = [FFMPEG_BIN, "-y"] + audio_inputs + \
                      ["-vf", vf_part, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                       "-c:a", "aac", "-shortest"] + audio_map + [str(output_path)]
                self._run_ffmpeg(cmd, "字幕烧录+音频合并")
                return

        cmd = [FFMPEG_BIN, "-y"] + audio_inputs
        if filter_complex:
            cmd += ["-filter_complex", filter_complex.strip(";")]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-shortest"] + audio_map + [str(output_path)]
        self._run_ffmpeg(cmd, "最终合成(字幕+BGM+配音)")

    # ── SRT to ASS (TikTok-friendly white+outline) ─────

    def _srt_to_ass(self, srt_path: Path, ass_path: Path) -> None:
        srt_text = srt_path.read_text(encoding="utf-8")
        blocks = srt_text.strip().split("\n\n")

        ass_header = (
            "[Script Info]\n"
            "Title: Subtitles\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\nPlayResY: 1920\n"
            "WrapStyle: 2\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,52,&H00FFFFFF,&H000000FF,"
            "&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4.0,2.0,"
            "2,60,60,120,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        events = []
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            times = lines[1].split(" --> ")
            if len(times) != 2:
                continue
            start = times[0].replace(",", ".")
            end = times[1].replace(",", ".")
            text = "\\N".join(lines[2:])
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        ass_path.write_text(ass_header + "\n".join(events), encoding="utf-8")

    # ── BGM Selection ──────────────────────────────────

    @staticmethod
    def find_bgm() -> tuple[Path | None, str]:
        """Find a random BGM file. Returns (path, name_or_message)."""
        if not BGM_DIR.exists():
            print("  [WARNING] BGM 目录不存在: bgm/ 缺少背景音乐文件")
            return None, "bgm_dir_missing"
        bgm_files = [f for f in BGM_DIR.glob("*") if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")
                     and f.name != ".gitkeep" and f.stat().st_size > 1000]
        if not bgm_files:
            print("  [WARNING] bgm/ 目录中没有有效的音乐文件 (.mp3/.wav)")
            return None, "no_real_bgm"
        chosen = random.choice(bgm_files)
        print(f"  [BGM] 使用: {chosen.name}")
        return chosen, chosen.name

    # ── Private: Runner ────────────────────────────────

    def _run_ffmpeg(self, cmd: list[str], label: str) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg {label} 失败:\n  Command: {' '.join(cmd)}\n"
                f"  Error: {result.stderr.strip()[-500:]}")
