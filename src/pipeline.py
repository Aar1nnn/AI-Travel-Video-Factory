"""
Pipeline Orchestrator（编排器 — 完整 MVP）

按顺序串联 6 个模块，传递中间产物。

执行顺序：
    Step 1: Script Generator       → script.json
    Step 2: Asset Library Manager  → script_with_assets.json
    Step 3: Voice Generator        → voice.mp3
    Step 4: Subtitle Generator     → subtitles.srt
    Step 5: Video Composer         → composed_video.mp4
    Step 6: Exporter               → output/{topic}_{date}.mp4
                                   → output/{topic}_{date}.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.config import (
    AppConfig, ASSETS_DIR, ASSETS_INDEX, OUTPUT_DIR, PROMPTS_DIR, TEMP_DIR,
)
from src.script_generator import ScriptGenerator, Script
from src.asset_library import AssetLibraryManager, MatchedAsset, ScoredAsset
from src.voice_generator import VoiceGenerator
from src.subtitle_generator import SubtitleGenerator
from src.video_composer import VideoComposer, CompositionResult
from src.exporter import Exporter, ExportResult
from src.quality_scorer import QualityScorer
from src.utils import save_json, ensure_dir

logger = logging.getLogger(__name__)

# Fallback asset path — used when no real assets match a scene's tags.
# Must point to an asset file that actually exists on disk.
_FALLBACK_ASSET_PATH = "general/travel_compass.jpg"
_FALLBACK_ASSET_TYPE = "image"


# ── Data Models ──────────────────────────────────────────

class PipelineResult(BaseModel):
    """Pipeline 执行结果"""
    script_path: Path
    script_with_assets_path: Path
    voice_path: Path
    subtitle_path: Path
    composed_video_path: Path
    final_video_path: Path
    metadata_path: Path
    duration: float
    scene_count: int
    asset_count: int
    file_size_mb: float
    resolution: str = "1080x1920"


# ── Orchestrator ─────────────────────────────────────────

class Pipeline:
    """
    视频生成编排器（完整 MVP）。

    串联 ScriptGenerator + AssetLibraryManager + VoiceGenerator
        + SubtitleGenerator + VideoComposer + Exporter。

    Attributes:
        config: AppConfig 全局配置
        script_gen: ScriptGenerator 实例
        asset_mgr: AssetLibraryManager 实例
        voice_gen: VoiceGenerator 实例
        subtitle_gen: SubtitleGenerator 实例
        composer: VideoComposer 实例
        exporter: Exporter 实例
        output_dir: 输出目录
    """

    def __init__(self, config: AppConfig, output_dir: Path | None = None, voice_profile: str | None = None):
        """
        Args:
            config: AppConfig 全局配置实例
            output_dir: 最终输出目录（默认 output/）
            voice_profile: voice profile 名称（如 "travel_female"），
                           优先级高于 config.tts。为 None 时使用 config.tts。
        """
        self.config = config
        self.output_dir = output_dir or OUTPUT_DIR
        ensure_dir(self.output_dir)
        ensure_dir(TEMP_DIR)

        # Step 1: Script Generator
        prompt_path = PROMPTS_DIR / "script_generation.txt"
        self.script_gen = ScriptGenerator(
            llm_config=config.llm,
            prompt_template_path=prompt_path,
        )

        # Step 2: Asset Library Manager
        self.asset_mgr = AssetLibraryManager(
            assets_dir=ASSETS_DIR,
            index_path=ASSETS_INDEX,
        )

        # Step 3: Voice Generator (with optional voice profile)
        profile = None
        if voice_profile:
            from src.config import get_voice_profile
            profile = get_voice_profile(voice_profile)
            if profile is None:
                print(f"  [Pipeline] WARNING voice profile '{voice_profile}' 不存在，使用默认")
        self.voice_gen = VoiceGenerator(
            tts_config=config.tts,
            profile=profile,
            output_dir=TEMP_DIR,
        )

        # Step 4: Subtitle Generator
        self.subtitle_gen = SubtitleGenerator(
            whisper_config=config.whisper,
            output_dir=TEMP_DIR,
        )

        # Step 5: Video Composer
        self.composer = VideoComposer(
            video_config=config.video,
            audio_config=config.audio,
            output_dir=TEMP_DIR,
            temp_dir=TEMP_DIR,
        )

        # Step 6: Exporter
        self.exporter = Exporter(
            output_dir=self.output_dir,
            temp_dir=TEMP_DIR,
            cleanup=False,  # Keep temp files for debugging
        )

    # ── Public API ───────────────────────────────────────

    def run(self, topic: str, style: str = "快节奏") -> PipelineResult:
        """
        执行完整管线。

        Args:
            topic: 旅游主题，如 "沙巴5天4晚旅游攻略"
            style: 视频风格，"快节奏" / "舒缓" / "文艺"

        Returns:
            PipelineResult 包含所有输出路径和元数据

        Raises:
            RuntimeError: 任何模块执行失败
        """
        print(f"\n{'─'*50}")
        print(f"  Pipeline: {topic} ({style})")
        print(f"{'─'*50}")

        # Step 1: Script Generator
        print("\n  [1/6] 生成脚本...")
        script = self.script_gen.generate(topic, style)
        script_dict = script.model_dump()
        script_path = TEMP_DIR / "script.json"
        save_json(script_dict, script_path)
        print(f"  [1/6] [OK] script.json")

        # Step 2: Asset Library Manager
        print("\n  [2/6] 匹配素材...")
        match_results = self.asset_mgr.match_for_scenes(script.scenes, top_n=3)
        script_with_assets = self._build_script_with_assets(script_dict, match_results)
        script_with_assets = self._filter_missing_assets(script_with_assets)
        # V4: Enforce unique asset_id per video
        script_with_assets, dedup_log = self._dedup_assets(script_with_assets)
        sawa_path = TEMP_DIR / "script_with_assets.json"
        save_json(script_with_assets, sawa_path)
        print(f"  [2/6] [OK] script_with_assets.json")

        # Step 3: Voice Generator
        print("\n  [3/6] 生成配音...")
        voice_path = self.voice_gen.generate(script)

        # Step 4: Subtitle Generator
        print("\n  [4/6] 生成字幕...")
        subtitle_path = self.subtitle_gen.generate(voice_path)

        # Step 5: Video Composer
        print("\n  [5/6] 合成视频...")
        bgm_path, bgm_name = VideoComposer.find_bgm()
        comp_result = self.composer.compose(
            script_with_assets, voice_path,
            subtitle_path=subtitle_path,
            bgm_path=bgm_path,
        )
        print(f"  [5/6] [OK] composed_video.mp4")

        # Step 6: Exporter
        print("\n  [6/6] 导出...")
        # Gather dedup and diversity info
        all_asset_ids = []
        all_source_ids = []
        all_scene_types = set()
        fallback_count = 0
        for s in script_with_assets["scenes"]:
            for a in s.get("assets", []):
                aid = a.get("id", "unknown")
                svid = a.get("source_video_id", "unknown")
                st = a.get("scene_type", "general")
                all_asset_ids.append(aid)
                if svid != "fallback":
                    all_source_ids.append(svid)
                if a.get("was_duplicate_asset") or a.get("duplicate_reason", ""):
                    fallback_count += 1
                all_scene_types.add(st)

        unique_ids = set(all_asset_ids)
        unique_source_ids = set(all_source_ids)
        duplicate_count = len(all_asset_ids) - len(unique_ids)
        dup_source_count = len(all_source_ids) - len(unique_source_ids)

        metadata = {
            "topic": topic,
            "style": style,
            "title": script.title,
            "duration": round(comp_result.duration, 1),
            "resolution": comp_result.resolution,
            "scene_count": comp_result.scene_count,
            "asset_count": comp_result.asset_count,
            "created_at": datetime.now().isoformat(),
            "used_assets": list(set(
                a["path"] for s in script_with_assets["scenes"]
                for a in s.get("assets", [])
            )),
            "unique_asset_count": len(unique_ids),
            "duplicate_asset_count": duplicate_count,
            "unique_source_video_count": len(unique_source_ids),
            "duplicate_source_video_count": dup_source_count,
            "scene_type_diversity": len(all_scene_types),
            "fallback_count": fallback_count,
            "bgm_file": bgm_name,
            "subtitle_burned_in": True,
        }
        # ── V4: Quality Scoring ──────────────────────────
        print("\n  [7/7] 质量评分...")
        try:
            scorer = QualityScorer()
            quality_report = scorer.score(metadata, script_dict)
            # Write quality report alongside metadata
            date_str = datetime.now().strftime("%Y%m%d")
            safe_topic = self.exporter._sanitize_filename(topic)
            quality_path = self.output_dir / f"{safe_topic}_{date_str}_quality.json"
            quality_path.write_text(
                quality_report.model_dump_json(indent=2), encoding="utf-8")
            # Update metadata dict with quality fields BEFORE export (so it goes into .json)
            metadata["quality_score"] = quality_report.content_score.total_score
            metadata["publish_recommendation"] = quality_report.content_score.publish_recommendation
            metadata["risk_flags"] = quality_report.risk_flags
            metadata["improvement_suggestions"] = quality_report.improvement_suggestions
            print(f"  [7/7] 评分: {quality_report.content_score.total_score}/100 "
                  f"({quality_report.content_score.publish_recommendation})")
        except Exception as e:
            metadata["quality_scorer_status"] = "failed"
            metadata["quality_scorer_error"] = str(e)[:200]
            print(f"  [7/7] Quality Scorer 评分失败: {e}")

        # Now export with quality metadata included
        export_result = self.exporter.export(
            composed_video_path=comp_result.video_path,
            topic=topic,
            metadata=metadata,
        )

        # Also copy subtitles to output
        date_str = datetime.now().strftime("%Y%m%d")
        safe_topic = self.exporter._sanitize_filename(topic)
        final_subtitle = self.output_dir / f"{safe_topic}_{date_str}.srt"
        import shutil
        shutil.copy2(subtitle_path, final_subtitle)

        # V2: also copy script and script_with_assets to output
        shutil.copy2(script_path, self.output_dir / f"{safe_topic}_{date_str}_script.json")
        shutil.copy2(sawa_path, self.output_dir / f"{safe_topic}_{date_str}_used_assets.json")

        # ── Summary ──────────────────────────────────────
        print(f"\n{'─'*50}")
        print(f"  Pipeline 完成!")
        print(f"  主题: {topic}")
        print(f"  场景: {comp_result.scene_count}")
        print(f"  素材: {comp_result.asset_count}")
        print(f"  时长: {comp_result.duration:.1f}s")
        print(f"  分辨率: {comp_result.resolution}")
        print(f"  文件大小: {export_result.file_size_mb} MB")
        print(f"{'─'*50}\n")

        return PipelineResult(
            script_path=script_path,
            script_with_assets_path=sawa_path,
            voice_path=voice_path,
            subtitle_path=subtitle_path,
            composed_video_path=comp_result.video_path,
            final_video_path=export_result.video_path,
            metadata_path=export_result.metadata_path,
            duration=comp_result.duration,
            scene_count=comp_result.scene_count,
            asset_count=comp_result.asset_count,
            file_size_mb=export_result.file_size_mb,
            resolution=comp_result.resolution,
        )

    # ── Private: Data Conversion ──────────────────────────

    def _build_script_with_assets(
        self,
        script_dict: dict,
        match_results: list[dict],
    ) -> dict:
        """将 Script + 匹配结果转换为 VideoComposer 所需的输入格式。

        V2 兼容：match_result["matched_assets"] 可能是 ScoredAsset（有 .path/.type）
        或 MatchedAsset（也有 .path/.type）。
        """
        match_map: dict[int, list] = {}
        for result in match_results:
            sid = result["scene_id"]
            match_map[sid] = result.get("matched_assets", [])

        scenes_with_assets = []

        for scene in script_dict["scenes"]:
            sid = scene["id"]
            matched = match_map.get(sid, [])

            if not matched:
                msg = (
                    f"场景 {sid} 没有匹配到任何素材，"
                    f"使用 fallback 素材。查询标签: {scene.get('asset_tags', [])}"
                )
                logger.warning(msg)
                print(f"  [Pipeline] WARNING {msg}")
                matched = [
                    ScoredAsset(
                        id="fallback",
                        path=_FALLBACK_ASSET_PATH,
                        type=_FALLBACK_ASSET_TYPE,
                        tags=["fallback"],
                        moods=[],
                        final_score=0.0,
                    )
                ]

            assets = [
                {"path": ma.path, "type": ma.type,
                 "id": getattr(ma, "id", "unknown"),
                 "source_video_id": self._extract_source_video_id(ma),
                 "scene_type": getattr(ma, "scene_type", "general"),
                 "match_score": getattr(ma, "final_score", 0.0) or getattr(ma, "match_score", 0.0),
                 "was_duplicate_asset": False,
                 "was_duplicate_source": False,
                 "duplicate_reason": "",
                 }
                for ma in matched
            ]

            scenes_with_assets.append({
                "id": sid,
                "text": scene["text"],
                "assets": assets,
            })

        return {
            "title": script_dict["title"],
            "scenes": scenes_with_assets,
        }

    def _filter_missing_assets(self, script_with_assets: dict) -> dict:
        """
        Remove assets whose files don't exist on disk from each scene.
        Scenes with zero valid assets get the fallback asset.
        """
        cleaned_scenes = []
        total_dropped = 0

        for scene in script_with_assets["scenes"]:
            valid_assets = []
            for asset in scene["assets"]:
                abs_path = (ASSETS_DIR / asset["path"]).resolve()
                if abs_path.exists():
                    valid_assets.append(asset)
                else:
                    total_dropped += 1

            if not valid_assets:
                valid_assets = [
                    {"path": _FALLBACK_ASSET_PATH, "type": _FALLBACK_ASSET_TYPE,
                     "id": "fallback", "source_video_id": "fallback",
                     "scene_type": "general", "match_score": 0.0,
                     "was_duplicate_asset": False, "was_duplicate_source": False, "duplicate_reason": ""}
                ]

            cleaned_scenes.append({
                "id": scene["id"],
                "text": scene["text"],
                "assets": valid_assets,
            })

        if total_dropped > 0:
            print(f"  [Pipeline] 过滤掉 {total_dropped} 个不存在的素材文件")

        return {
            "title": script_with_assets["title"],
            "scenes": cleaned_scenes,
        }

    def _dedup_assets(self, script_with_assets: dict) -> tuple[dict, list[dict]]:
        """
        V5: Enforce unique asset_id + source_video_id per video.

        Rules:
        - Same asset_id: NEVER allowed in same video. Use top2/top3/fallback.
        - Same source_video_id: max 1 (ideal) or 2 (if insufficient). Never consecutive.
        - Consecutive scene_type: discouraged (warn but don't hard-fail).
        """
        scenes = script_with_assets.get("scenes", [])
        used_asset_ids: set[str] = set()
        used_source_ids: list[str] = []  # ordered list for consecutive check
        last_scene_type: str = ""
        deduped_scenes = []
        dedup_log = []
        total_replacements = 0
        source_cooldown = True  # enforce source_video_id not consecutive

        for scene in scenes:
            assets = scene.get("assets", [])
            this_scene_type = scene.get("scene_type", "general")
            new_assets = []

            for asset in assets:
                asset_id = asset.get("id", "unknown")
                source_vid = asset.get("source_video_id", "unknown")
                asset_path = asset.get("path", "")

                # Rule 1: asset_id must be unique
                if asset_id in used_asset_ids:
                    # Try next candidate in same scene's asset list
                    replacements = [a for a in assets if a.get("id") not in used_asset_ids]
                    if not replacements:
                        # All candidates exhausted → fallback
                        fb = {"path": _FALLBACK_ASSET_PATH, "type": _FALLBACK_ASSET_TYPE,
                              "id": "fallback", "source_video_id": "fallback",
                              "scene_type": "general", "match_score": 0.0,
                              "was_duplicate_asset": True, "was_duplicate_source": False,
                              "duplicate_reason": "all_candidates_duplicate"}
                        new_assets.append(fb)
                        dedup_log.append({"scene_id": scene["id"], "asset_id": asset_id,
                                         "source_video_id": source_vid, "reason": "all_candidates_duplicate"})
                        total_replacements += 1
                    else:
                        # Pick best available replacement
                        replacement = replacements[0]
                        # Check source_video_id constraint
                        if source_cooldown and source_vid in used_source_ids:
                            # Prefer replacement with different source
                            alt_replacements = [a for a in replacements if a.get("source_video_id") not in used_source_ids]
                            if alt_replacements:
                                replacement = alt_replacements[0]
                        replacement["was_duplicate_asset"] = True
                        replacement["duplicate_reason"] = "asset_id_already_used"
                        new_assets.append(replacement)
                        used_asset_ids.add(replacement.get("id", ""))
                        used_source_ids.append(replacement.get("source_video_id", ""))
                        dedup_log.append({"scene_id": scene["id"], "asset_id": asset_id,
                                         "source_video_id": source_vid,
                                         "replacement_id": replacement.get("id"),
                                         "reason": "asset_id_already_used"})
                        total_replacements += 1
                    continue

                # Rule 2: source_video_id diversity
                source_count = used_source_ids.count(source_vid) if source_vid != "fallback" else 0
                if source_cooldown and used_source_ids and used_source_ids[-1] == source_vid:
                    # Same source as previous scene → try to swap
                    replacements = [a for a in assets if a.get("id") != asset_id and a.get("source_video_id") != source_vid and a.get("id") not in used_asset_ids]
                    if replacements:
                        replacement = replacements[0]
                        replacement["was_duplicate_source"] = True
                        replacement["duplicate_reason"] = "consecutive_source_video_id"
                        new_assets.append(replacement)
                        used_asset_ids.add(replacement.get("id", ""))
                        used_source_ids.append(replacement.get("source_video_id", ""))
                        dedup_log.append({"scene_id": scene["id"], "asset_id": asset_id,
                                         "source_video_id": source_vid,
                                         "replacement_id": replacement.get("id"),
                                         "reason": "consecutive_source_video_id"})
                        total_replacements += 1
                        continue
                    # else: can't avoid, allow it but log
                    dedup_log.append({"scene_id": scene["id"], "asset_id": asset_id,
                                     "source_video_id": source_vid, "reason": "consecutive_source_unavoidable"})

                # Rule 3: scene_type consecutive check (soft)
                if this_scene_type == last_scene_type and this_scene_type != "general":
                    # Try to pick a different-scene_type asset
                    replacements = [a for a in assets if a.get("scene_type") != this_scene_type and a.get("id") not in used_asset_ids]
                    if replacements:
                        replacement = replacements[0]
                        replacement["duplicate_reason"] = "consecutive_scene_type"
                        new_assets.append(replacement)
                        used_asset_ids.add(replacement.get("id", ""))
                        used_source_ids.append(replacement.get("source_video_id", ""))
                        dedup_log.append({"scene_id": scene["id"], "asset_id": asset_id,
                                         "reason": "consecutive_scene_type",
                                         "replacement_id": replacement.get("id")})
                        total_replacements += 1
                        continue

                # Asset is clean
                new_assets.append(asset)
                used_asset_ids.add(asset_id)
                used_source_ids.append(source_vid)

            last_scene_type = this_scene_type
            deduped_scenes.append(dict(scene, assets=new_assets))

        if total_replacements > 0:
            print(f"  [Pipeline] 素材去重: {total_replacements} 个冲突已解决")

        return {"title": script_with_assets["title"], "scenes": deduped_scenes}, dedup_log

    @staticmethod
    def _extract_source_video_id(ma) -> str:
        """Extract source_video_id from asset record or path."""
        sv = getattr(ma, "source_video", "") or getattr(ma, "source_video_id", "")
        if sv:
            return str(Path(sv).stem)
        path = getattr(ma, "path", "")
        # Infer from path: "processed/yunnan_001_clip_03.mp4" → "yunnan_001"
        stem = Path(path).stem
        # Clip off trailing _clip_NN
        parts = stem.rsplit("_", 2)
        if len(parts) >= 3 and parts[-2] == "clip":
            return "_".join(parts[:-2])
        return stem
