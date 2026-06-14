"""
模块: Asset Processor（素材自动切镜头系统 — V2）

V2新增:
- 多帧缩略图抽取 (25%/50%/75%)
- 质量评分 (resolution + sharpness + duration + orientation)
- 场景摘要生成

V1保留:
- 扫描 assets/raw/ 中的原始视频
- 使用 PySceneDetect 检测镜头切换
- FFmpeg 切割成独立片段 → assets/processed/
- 生成缩略图 → assets/thumbnails/
- 自动写入 index.json
"""

import json
import os
import re
import subprocess
from io import BytesIO
from pathlib import Path

from src.config import (
    ASSETS_DIR, ASSETS_RAW_DIR, ASSETS_PROCESSED_DIR,
    ASSETS_THUMBNAILS_DIR, ASSETS_INDEX,
)
from src.asset_library import AssetRecord, SceneType
from src.utils import ensure_dir


# ── FFmpeg/FFprobe paths (auto-detect) ──────────────────

def _find_ffmpeg() -> str:
    import shutil as _shutil
    path = _shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError("FFmpeg not found. Please install FFmpeg and add it to PATH.")

def _find_ffprobe() -> str:
    import shutil as _shutil
    path = _shutil.which("ffprobe")
    if path:
        return path
    ffmpeg_dir = Path(_find_ffmpeg()).parent
    probe = ffmpeg_dir / ("ffprobe.exe" if Path(_find_ffmpeg()).suffix == ".exe" else "ffprobe")
    if probe.exists():
        return str(probe)
    raise RuntimeError("FFprobe not found. Please install FFmpeg and add it to PATH.")

_FFMPEG_BIN = _find_ffmpeg()
_FFPROBE_BIN = _find_ffprobe()

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}


# ── Processor ──────────────────────────────────────────

class AssetProcessor:
    """
    素材自动处理器。

    流程:
      1. 扫描 assets/raw/ 中的视频文件
      2. PySceneDetect 检测镜头切换点
      3. FFmpeg 按片段切割 → assets/processed/asset_XXX.mp4
      4. FFmpeg 抽取中间帧 → assets/thumbnails/asset_XXX.jpg
      5. 合并已有 index.json，追加新记录

    Attributes:
        raw_dir: 原始素材目录
        processed_dir: 处理后输出目录
        thumbnails_dir: 缩略图输出目录
        index_path: 素材索引路径
        min_scene_duration: 最短镜头时长（秒），过滤过短片段
    """

    def __init__(
        self,
        raw_dir: Path | None = None,
        processed_dir: Path | None = None,
        thumbnails_dir: Path | None = None,
        index_path: Path | None = None,
        min_scene_duration: float = 1.0,
    ):
        self.raw_dir = raw_dir or ASSETS_RAW_DIR
        self.processed_dir = processed_dir or ASSETS_PROCESSED_DIR
        self.thumbnails_dir = thumbnails_dir or ASSETS_THUMBNAILS_DIR
        self.index_path = index_path or ASSETS_INDEX
        self.min_scene_duration = min_scene_duration
        ensure_dir(self.raw_dir)
        ensure_dir(self.processed_dir)
        ensure_dir(self.thumbnails_dir)

    # ── Public API ─────────────────────────────────────

    def process_all(self) -> list[AssetRecord]:
        """
        处理 raw/ 目录下所有视频。

        Returns:
            新生成的 AssetRecord 列表
        """
        videos = self._find_raw_videos()
        if not videos:
            print("[AssetProcessor] raw/ 目录为空，无需处理")
            return []

        all_new = []
        for i, vp in enumerate(videos, 1):
            print(f"\n[{i}/{len(videos)}] Processing: {vp.name}")
            records = self.process_video(vp)
            all_new.extend(records)

        print(f"\n[AssetProcessor] 总计生成 {len(all_new)} 个新素材")
        return all_new

    def process_video(self, raw_path: Path) -> list[AssetRecord]:
        """
        处理单个视频文件。

        自动处理相对路径/绝对路径/外部路径。

        Args:
            raw_path: 视频路径（相对或绝对，可在 ASSETS_DIR 外部）

        Returns:
            生成的 AssetRecord 列表
        """
        import shutil as _shutil

        # ── Path normalization ──────────────────────────
        raw_path = self._normalize_input_path(raw_path)

        if not raw_path.exists():
            raise FileNotFoundError(f"文件不存在: {raw_path}")

        # At this point raw_path is absolute and inside ASSETS_DIR
        assets_root = ASSETS_DIR.resolve()
        rel = raw_path.relative_to(assets_root)

        # Step 1: Detect scenes

        # Step 1: Detect scenes
        scenes = self._detect_scenes(raw_path)
        if not scenes:
            print(f"  No scenes detected, skipping")
            return []

        print(f"  Detected {len(scenes)} scenes")

        # Step 2: Load current index for ID counter
        existing = self._load_existing_ids()

        # Step 3: Process each scene
        new_records = []
        for sid, (start, end) in enumerate(scenes):
            dur = round(end - start, 1)
            if dur < self.min_scene_duration:
                continue

            asset_id = self._next_asset_id(existing + len(new_records))
            clip_name = f"{asset_id}.mp4"
            clip_path = self.processed_dir / clip_name
            rel_clip = Path("processed") / clip_name

            # Cut clip with FFmpeg
            self._cut_clip(raw_path, start, dur, clip_path)

            if not clip_path.exists() or clip_path.stat().st_size < 1000:
                continue

            # Generate thumbnail
            thumb_name = f"{asset_id}.jpg"
            thumb_path = self.thumbnails_dir / thumb_name
            rel_thumb = Path("thumbnails") / thumb_name
            self._extract_thumbnail(clip_path, thumb_path)

            # Probe resolution
            resolution = self._probe_resolution(clip_path)

            record = AssetRecord(
                id=asset_id,
                path=str(rel_clip).replace("\\", "/"),
                type="video",
                tags=[],
                country="",
                city="",
                category="",
                scene_type=SceneType.GENERAL,
                moods=[],
                duration=dur,
                resolution=resolution,
                orientation="horizontal",
                file_size_kb=clip_path.stat().st_size // 1024,
                source="auto-processed",
                license_="",
                thumbnail=str(rel_thumb).replace("\\", "/"),
                source_video=str(rel).replace("\\", "/"),
                start_time=round(start, 1),
                end_time=round(end, 1),
            )
            new_records.append(record)
            print(f"    {asset_id}: {dur:.1f}s [{start:.1f}-{end:.1f}] "
                  f"{resolution}")

        # Step 4: Merge into index.json
        self._merge_index(new_records)

        return new_records

    # ── Scene Detection ────────────────────────────────

    def _detect_scenes(self, video_path: Path) -> list[tuple[float, float]]:
        """
        使用 PySceneDetect ContentDetector 检测镜头切换。

        Returns:
            [(start_time, end_time), ...] 每个片段的时间范围
        """
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector

            video = open_video(str(video_path))
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=27.0))
            scene_manager.detect_scenes(video)

            scene_list = scene_manager.get_scene_list()
            if not scene_list:
                return []

            scenes = []
            for start, end in scene_list:
                s_sec = start.get_seconds()
                e_sec = end.get_seconds()
                scenes.append((round(s_sec, 1), round(e_sec, 1)))

            return scenes
        except ImportError:
            # Fallback: treat entire video as single clip
            dur = self._get_duration(video_path)
            if dur:
                return [(0.0, dur)]
            return []
        except Exception as e:
            print(f"  WARNING: scene detection failed: {e}")
            return []

    # ── FFmpeg: Clip Cutting ───────────────────────────

    def _cut_clip(
        self,
        src: Path,
        start: float,
        duration: float,
        output: Path,
    ) -> None:
        """
        用 FFmpeg 切割视频片段。

        Args:
            src: 源视频路径
            start: 起始时间（秒）
            duration: 片段时长（秒）
            output: 输出路径
        """
        cmd = [
            _FFMPEG_BIN, "-y",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",  # 去除音轨
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    FFmpeg cut failed: {result.stderr.strip()[-200:]}")

    # ── FFmpeg: Thumbnail ──────────────────────────────

    def _extract_thumbnail(self, video_path: Path, output_path: Path) -> None:
        """从视频中间帧抽取缩略图（单帧版本，向后兼容）。"""
        dur = self._get_duration(video_path) or 3.0
        mid = dur / 2.0
        self._extract_frame_at(video_path, mid, output_path)

    def _extract_frame_at(self, video_path: Path, time_sec: float, output_path: Path) -> None:
        """从视频指定时间点抽取帧。"""
        cmd = [
            _FFMPEG_BIN, "-y",
            "-ss", str(time_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    Frame extract failed at {time_sec}s: {result.stderr.strip()[-200:]}")

    def extract_multi_frames(self, video_path: Path, output_dir: Path, asset_id: str) -> list[Path]:
        """V2: 抽取 25%/50%/75% 三帧。"""
        dur = self._get_duration(video_path)
        if not dur or dur < 1.0:
            # Fallback: single midpoint
            p = output_dir / f"{asset_id}_mid.jpg"
            self._extract_thumbnail(video_path, p)
            return [p] if p.exists() else []

        paths = []
        for pct, label in [(0.25, "p25"), (0.50, "p50"), (0.75, "p75")]:
            t = dur * pct
            p = output_dir / f"{asset_id}_{label}.jpg"
            self._extract_frame_at(video_path, t, p)
            if p.exists() and p.stat().st_size > 500:
                paths.append(p)
        return paths

    # ── Probe ──────────────────────────────────────────

    def _probe_resolution(self, video_path: Path) -> str:
        """用 ffprobe 获取分辨率。"""
        try:
            cmd = [
                _FFPROBE_BIN, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return ""
            data = json.loads(result.stdout)
            for s in data.get("streams", []):
                if "width" in s and "height" in s:
                    return f"{s['width']}x{s['height']}"
        except Exception:
            pass
        return ""

    def _get_duration(self, video_path: Path) -> float | None:
        """用 ffprobe 获取视频时长。"""
        try:
            cmd = [
                _FFPROBE_BIN, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return None

    # ── Index Management ───────────────────────────────

    def _load_existing_ids(self) -> int:
        """读取已有 index.json 中的素材数量。"""
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                return len(data)
            except Exception:
                pass
        return 0

    def _next_asset_id(self, existing_count: int) -> str:
        """生成下一个素材 ID。"""
        return f"asset_{existing_count + 1:03d}"

    def _merge_index(self, new_records: list[AssetRecord]) -> None:
        """将新素材记录合并到 index.json。"""
        existing = []
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                existing = [AssetRecord(**item) for item in data]
            except Exception:
                pass

        all_records = existing + new_records
        output = [r.model_dump() for r in all_records]
        self.index_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── File Discovery ─────────────────────────────────

    def _find_raw_videos(self) -> list[Path]:
        """扫描 raw/ 目录下的视频文件。"""
        videos = []
        if not self.raw_dir.exists():
            return videos
        for entry in sorted(self.raw_dir.iterdir()):
            if entry.name.startswith(".") or entry.name == ".gitkeep":
                continue
            if entry.suffix.lower() in VIDEO_EXTS:
                videos.append(entry)
        return videos

    # ── Path Normalization ────────────────────────────

    def _normalize_input_path(self, raw_path: Path) -> Path:
        """
        Normalize any input path to an absolute path inside ASSETS_DIR.

        Handles:
        - Absolute paths inside ASSETS_DIR → no copy needed
        - Relative paths → resolve against PROJECT_ROOT
        - Paths outside ASSETS_DIR → copy into assets/raw/uploads/
        """
        import shutil as _shutil

        raw_path = Path(raw_path)
        assets_root = ASSETS_DIR.resolve()

        # Convert to absolute
        if not raw_path.is_absolute():
            raw_path = (ASSETS_DIR.parent / raw_path).resolve()
        else:
            raw_path = raw_path.resolve()

        # Check if inside assets_root
        try:
            raw_path.relative_to(assets_root)
            return raw_path
        except ValueError:
            pass

        # Outside assets_root → copy into uploads
        uploads_dir = ASSETS_RAW_DIR / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^\w一-鿿\-_\.]", "_", raw_path.name)
        dest = uploads_dir / f"upload_{ts}_{safe_name}"
        dest = dest.resolve()
        _shutil.copy2(raw_path, dest)
        print(f"  [AssetProcessor] 外部文件已复制到: {dest}")
        # Verify it's now inside assets_root
        try:
            dest.relative_to(assets_root)
        except ValueError:
            raise RuntimeError(
                f"无法将文件复制到素材目录内: {dest} 不在 {assets_root} 下"
            )
        return dest

    # ── V2: Quality Scoring ─────────────────────────────

    def compute_quality_score(
        self,
        video_path: Path,
        resolution: str = "",
        duration: float | None = None,
    ) -> float:
        """
        V2: 计算素材质量评分 (0.0 ~ 1.0)。

        维度:
          - 分辨率 (40%): 4K=1.0, 1080p=0.7, 720p=0.4, <720p=0.2
          - 时长   (30%): 3~15s 最佳=1.0, 2~3s 或 15~30s=0.7, 其他=0.4
          - 清晰度 (20%): 基于 JPEG 文件大小估算
          - 竖屏   (10%): 竖屏=1.0, 横屏=0.5
        """
        # Resolution score
        if resolution:
            w_str = resolution.split("x")[0]
            try:
                w = int(w_str)
                if w >= 3840: res_score = 1.0
                elif w >= 1920: res_score = 0.7
                elif w >= 1280: res_score = 0.4
                else: res_score = 0.2
            except ValueError:
                res_score = 0.5
        else:
            res_score = 0.5

        # Duration score
        dur = duration or self._get_duration(video_path) or 5.0
        if 3.0 <= dur <= 15.0:
            dur_score = 1.0
        elif 2.0 <= dur < 3.0 or 15.0 < dur <= 30.0:
            dur_score = 0.7
        else:
            dur_score = 0.4

        # Sharpness (estimated from file size per pixel, rough proxy)
        file_size = video_path.stat().st_size if video_path.exists() else 100000
        kb_per_sec = (file_size / 1024) / max(dur, 0.1)
        if kb_per_sec > 2000: sharp_score = 1.0
        elif kb_per_sec > 1000: sharp_score = 0.8
        elif kb_per_sec > 500: sharp_score = 0.6
        else: sharp_score = 0.4

        # Orientation
        orient_score = 1.0  # neutral, caller can override

        quality = round(
            0.40 * res_score
            + 0.30 * dur_score
            + 0.20 * sharp_score
            + 0.10 * orient_score,
            4,
        )
        return quality

    # ── V2: Multi-frame Tagging ─────────────────────────

    def multi_frame_tag(
        self,
        video_path: Path,
        asset_id: str | None = None,
    ) -> dict:
        """
        V2: 多帧 CLIP 标签融合。

        抽取 25%/50%/75% 三帧 → 分别 CLIP 分类 → 投票融合。

        Returns:
            {
                "scene_type": "lake",
                "tags": ["洱海","湖景","云南"],
                "confidence": 0.82,
                "frame_votes": {"lake": 2, "landscape": 1},
                "scene_summary": "洱海湖景，蓝天白云，宁静自然风光"
            }
        """
        from PIL import Image
        import torch

        # Extract multi frames
        aid = asset_id or video_path.stem
        frames = self.extract_multi_frames(video_path, self.thumbnails_dir, aid)
        if not frames:
            return {"scene_type": "general", "tags": [], "confidence": 0.0,
                    "frame_votes": {}, "scene_summary": ""}

        # Lazy-load AutoTagger for CLIP model
        try:
            from src.auto_tagger import (
                AutoTagger, _SCENE_TYPE_KEYS, _SCENE_TYPE_PROMPTS, ALL_TAGS_CN,
                MAX_TAGS, MIN_CONFIDENCE,
            )
            tagger = AutoTagger()
            tagger._init_model() if tagger._model is None else None
        except Exception as e:
            return {"scene_type": "general", "tags": [], "confidence": 0.0,
                    "frame_votes": {}, "scene_summary": f"CLIP load failed: {e}"}

        # Classify each frame
        st_votes = {}
        all_tag_scores = {}
        all_confidences = []

        for frame_path in frames:
            img = Image.open(frame_path).convert("RGB")
            img_tensor = tagger.preprocess(img).unsqueeze(0).to(tagger.device)

            # scene_type
            st_texts = [f"一张{desc}的照片" for desc in _SCENE_TYPE_PROMPTS]
            st_tokens = tagger.tokenizer(st_texts).to(tagger.device)
            with torch.no_grad():
                imf = tagger.model.encode_image(img_tensor)
                imf /= imf.norm(dim=-1, keepdim=True)
                txf = tagger.model.encode_text(st_tokens)
                txf /= txf.norm(dim=-1, keepdim=True)
                sim = (imf @ txf.T).squeeze(0)
                probs = sim.softmax(dim=0)
            best_idx = int(probs.argmax().item())
            best_st = _SCENE_TYPE_KEYS[best_idx]
            st_votes[best_st] = st_votes.get(best_st, 0) + 1
            all_confidences.append(float(probs[best_idx].item()))

            # tags
            tag_texts = [f"{t}" for t in ALL_TAGS_CN]
            tag_tokens = tagger.tokenizer(tag_texts).to(tagger.device)
            with torch.no_grad():
                txf2 = tagger.model.encode_text(tag_tokens)
                txf2 /= txf2.norm(dim=-1, keepdim=True)
                sim2 = (imf @ txf2.T).squeeze(0)
            for i, t in enumerate(ALL_TAGS_CN):
                s = float(sim2[i].item())
                all_tag_scores[t] = all_tag_scores.get(t, 0.0) + s

        # Vote winner
        top_st = max(st_votes, key=st_votes.get) if st_votes else "general"
        avg_conf = round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else 0.0

        # Average tag scores, pick top
        for t in all_tag_scores:
            all_tag_scores[t] /= len(frames)
        sorted_tags = sorted(all_tag_scores.items(), key=lambda x: -x[1])
        tags = [t for t, s in sorted_tags if s >= MIN_CONFIDENCE][:MAX_TAGS]
        if not tags:
            tags = [sorted_tags[0][0]]

        # Generate scene_summary
        summary = self._generate_summary(top_st, tags)

        return {
            "scene_type": top_st,
            "tags": tags,
            "confidence": avg_conf,
            "frame_votes": st_votes,
            "scene_summary": summary,
        }

    def _generate_summary(self, scene_type: str, tags: list[str]) -> str:
        """V2: 从 scene_type + tags 生成简短中文描述。"""
        type_names = {
            "airport": "机场", "hotel": "酒店", "beach": "海滩",
            "island": "海岛", "lake": "湖泊", "mountain": "山景",
            "city": "城市", "food": "美食", "market": "市场",
            "temple": "寺庙", "sunset": "日落", "night": "夜景",
            "wildlife": "动物", "shopping": "购物", "transport": "交通",
            "landscape": "自然风光",
        }
        st_name = type_names.get(scene_type, scene_type)
        tag_str = "，".join(tags[:4]) if tags else scene_type
        return f"{st_name}场景：{tag_str}"
