"""
模块 2: Asset Library Manager（素材库管理器 — Smart Matching V3）

职责：
- 读取 assets/index.json
- 多维度智能匹配（scene_type + tag + mood + country + city + type）
- 相邻场景素材去重
- 扫描素材目录并自动生成索引（--scan-assets）
- 素材覆盖率分析（--asset-report）
"""

import json
import os
import subprocess
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from src.utils import load_json, save_json


# ── SceneType Enum ───────────────────────────────────

class SceneType:
    """标准化场景类型 — 素材与场景匹配的通用语言。"""
    AIRPORT    = "airport"
    HOTEL      = "hotel"
    BEACH      = "beach"
    ISLAND     = "island"
    LAKE       = "lake"
    MOUNTAIN   = "mountain"
    CITY       = "city"
    FOOD       = "food"
    MARKET     = "market"
    TEMPLE     = "temple"
    SUNSET     = "sunset"
    NIGHT      = "night"
    WILDLIFE   = "wildlife"
    SHOPPING   = "shopping"
    TRANSPORT  = "transport"
    LANDSCAPE  = "landscape"
    GENERAL    = "general"

    ALL = frozenset({
        AIRPORT, HOTEL, BEACH, ISLAND, LAKE, MOUNTAIN, CITY,
        FOOD, MARKET, TEMPLE, SUNSET, NIGHT, WILDLIFE, SHOPPING,
        TRANSPORT, LANDSCAPE, GENERAL,
    })

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.ALL

    @classmethod
    def default(cls) -> str:
        return cls.GENERAL


# ── Data Models ────────────────────────────────────────

class AssetRecord(BaseModel):
    """单条素材记录"""
    id: str
    path: str
    type: str
    tags: list[str] = []
    country: str = ""
    city: str = ""
    category: str = ""
    scene_type: str = "general"
    moods: list[str] = []
    duration: float | None = None
    resolution: str = ""
    orientation: str = ""
    file_size_kb: int = 0
    source: str = ""
    license_: str = ""
    thumbnail: str = ""                   # thumbnails/asset_xxx.jpg
    source_video: str = ""                # raw/yunnan_sunset.mp4
    start_time: float | None = None       # 在原视频中的起始时间（秒）
    end_time: float | None = None         # 在原视频中的结束时间（秒）
    confidence: float | None = None       # AI auto-tagger 置信度 (0.0~1.0)
    quality_score: float | None = None    # 素材质量评分 (0.0~1.0)
    scene_summary: str = ""               # 场景内容简述（多帧 CLIP 生成）
    embedding_path: str = ""              # embeddings/asset_xxx.npy


class ScoredAsset(BaseModel):
    """V4 匹配结果 — 多维度评分明细"""
    id: str
    path: str
    type: str
    tags: list[str]
    country: str = ""
    city: str = ""
    category: str = ""
    scene_type: str = "general"
    moods: list[str] = []
    duration: float | None = None
    final_score: float = 0.0
    semantic_score: float = 0.0
    scene_type_score: float = 0.0
    tag_score: float = 0.0
    mood_score: float = 0.0
    country_score: float = 0.0
    city_score: float = 0.0
    type_score: float = 0.0
    quality_score: float = 0.0

    @property
    def match_score(self) -> float:
        return self.final_score


MatchedAsset = ScoredAsset


# ── Constants ──────────────────────────────────────────

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}

# ── Scoring Weights (V4) ──────────────────────────────

WEIGHT_SEMANTIC    = 0.35
WEIGHT_SCENE_TYPE  = 0.25
WEIGHT_TAG         = 0.15
WEIGHT_MOOD        = 0.10
WEIGHT_CITY        = 0.10
WEIGHT_QUALITY     = 0.05

# Backward compat aliases (V3 tests import these)
WEIGHT_COUNTRY = 0.0
WEIGHT_TYPE    = 0.0

# ── Mood → Preferred Categories ────────────────────────

MOOD_CATEGORY_MAP: dict[str, list[str]] = {
    "开场吸引": ["aerial", "landscape", "panorama"],
    "轻松惬意": ["beach", "hotel", "sunset", "landscape"],
    "活力刺激": ["activity", "food", "urban", "night"],
    "神秘探索": ["wildlife", "cultural", "landscape"],
    "温馨感人": ["sunset", "night", "cultural", "hotel"],
    "结尾号召": ["sunset", "aerial", "landscape", "urban"],
}

_CATEGORY_KEYWORDS = {
    "aerial":     ["俯瞰", "航拍", "aerial", "drone"],
    "landscape":  ["风景", "山", "海", "湖", "河", "森林", "草原", "沙漠", "雪山"],
    "urban":      ["城市", "街道", "建筑", "广场", "天际线", "十字路口"],
    "food":       ["美食", "海鲜", "夜市", "料理", "餐厅", "刺身", "拉面", "丼"],
    "cultural":   ["寺庙", "神社", "和服", "传统", "民俗", "博物馆", "城堡"],
    "hotel":      ["酒店", "民宿", "泳池", "住宿", "大堂"],
    "transport":  ["机场", "飞机", "火车", "地铁", "出租", "码头"],
    "activity":   ["浮潜", "骑行", "滑雪", "登山", "冲浪", "登山", "徒步"],
    "wildlife":   ["动物", "花", "鸟", "猴", "萤火虫", "樱花", "红叶", "枫叶"],
    "sunset":     ["日落", "黄昏", "夕阳", "日出", "朝霞", "晚霞"],
    "night":      ["夜景", "霓虹", "灯光", "夜生活", "酒吧", "夜市"],
    "beach":      ["海滩", "沙滩", "海岛", "海岸", "玻璃海"],
    "panorama":   ["全景", "地标", "天际线"],
}

_CITY_KEYWORDS = {
    "sabah": ["沙巴", "亚庇"], "kuala-lumpur": ["吉隆坡"],
    "tokyo": ["东京"], "osaka": ["大阪"], "kyoto": ["京都"],
    "yunnan": ["云南"], "lijiang": ["丽江"], "dali": ["大理"], "kunming": ["昆明"],
    "bangkok": ["曼谷"], "chiang-mai": ["清迈"],
}

_COUNTRY_KEYWORDS = {
    "malaysia": ["马来西亚", "沙巴", "吉隆坡", "槟城", "兰卡威"],
    "china":    ["中国", "云南", "丽江", "大理", "昆明", "北京", "上海"],
    "japan":    ["日本", "东京", "大阪", "京都", "北海道", "冲绳"],
    "thailand": ["泰国", "曼谷", "清迈", "普吉", "苏梅"],
    "indonesia":["印尼", "巴厘岛", "龙目岛"],
}


# ── Manager ────────────────────────────────────────────

class AssetLibraryManager:
    """
    V4 scoring: 0.35×semantic + 0.25×scene_type + 0.15×tag + 0.10×mood + 0.10×city + 0.05×quality
    """

    weight_semantic    = WEIGHT_SEMANTIC
    weight_scene_type  = WEIGHT_SCENE_TYPE
    weight_tag         = WEIGHT_TAG
    weight_mood        = WEIGHT_MOOD
    weight_city        = WEIGHT_CITY
    weight_quality     = WEIGHT_QUALITY

    def __init__(self, assets_dir: Path, index_path: Path):
        self.assets_dir = assets_dir
        self.index_path = index_path
        self._records: list[AssetRecord] = []
        self._load_index()

    def _load_index(self) -> None:
        if self.index_path.exists():
            data = load_json(self.index_path)
            self._records = [AssetRecord(**item) for item in data]
        else:
            self._records = []

    def reload(self) -> None:
        self._load_index()

    def get_all_records(self) -> list[AssetRecord]:
        return list(self._records)

    # ── V3 Smart Matching ──────────────────────────────

    def match_scene(self, scene, top_n: int = 5, exclude_ids: set[str] | None = None) -> list[ScoredAsset]:
        asset_tags = getattr(scene, "asset_tags", [])
        mood = getattr(scene, "mood", "")
        topic = getattr(scene, "topic", "")
        scene_type = getattr(scene, "scene_type", "general")
        scene_text = getattr(scene, "text", "")
        return self._match_multi_dim(
            query_tags=asset_tags, query_mood=mood, query_topic=topic,
            query_scene_type=scene_type, query_text=scene_text,
            top_n=top_n, exclude_ids=exclude_ids,
        )

    def match_for_script(self, script, top_n: int = 5) -> list[dict]:
        results = []
        used_ids: set[str] = set()
        for scene in getattr(script, "scenes", []):
            matched = self.match_scene(scene=scene, top_n=top_n, exclude_ids=used_ids)
            if matched:
                used_ids.add(matched[0].id)
            results.append({
                "scene_id": getattr(scene, "id", -1),
                "asset_tags": getattr(scene, "asset_tags", []),
                "matched_assets": matched,
            })
        return results

    # ── VQ1: Per-Unit Asset Matching ────────────────────

    def match_for_voice_units(self, voice_units: list, top_n: int = 5) -> list:
        """
        VQ1: 每个 VoiceUnit 匹配一个素材。

        Args:
            voice_units: VoiceUnit 列表（已有 text/scene_type/asset_tags）
            top_n: 候选素材数

        Returns:
            更新后的 voice_units（填充 selected_asset_id/path/type）
        """
        used_asset_ids: set[str] = set()
        used_source_ids: list[str] = []
        updated = []

        for unit in voice_units:
            # Query the matching engine
            results = self._match_multi_dim(
                query_tags=unit.asset_tags,
                query_mood=unit.mood,
                query_scene_type=unit.scene_type,
                query_text=unit.text,
                top_n=top_n,
            )

            # Pick first non-duplicate asset
            chosen = None
            fallback = None

            for r in results:
                if r.id in used_asset_ids:
                    continue
                # Source video diversity: prefer non-consecutive source
                svid = getattr(r, 'source_video', '') or getattr(r, 'source_video_id', '') or ''
                if used_source_ids and used_source_ids[-1] == svid:
                    # Try next unless all remaining are same source
                    continue
                chosen = r
                break

            if not chosen:
                # Pick first result regardless — at least it's a match
                if results:
                    chosen = results[0]
                    unit.risk_flags.append("duplicate_asset_forced")
                else:
                    # Fallback
                    from src.config import ASSETS_DIR
                    fallback_path = ASSETS_DIR / "general" / "travel_compass.jpg"
                    if fallback_path.exists():
                        unit.selected_asset_id = "fallback"
                        unit.selected_asset_path = "general/travel_compass.jpg"
                        unit.selected_asset_type = "image"
                        unit.is_fallback = True
                        unit.risk_flags.append("no_match_fallback")
                        updated.append(unit)
                        continue

            if chosen:
                unit.selected_asset_id = chosen.id
                unit.selected_asset_path = chosen.path
                unit.selected_asset_type = chosen.type
                used_asset_ids.add(chosen.id)
                svid = getattr(chosen, 'source_video', '') or getattr(chosen, 'source_video_id', '') or ''
                if svid:
                    used_source_ids.append(svid)

            updated.append(unit)

        # Log dedup stats
        fallback_count = sum(1 for u in updated if u.is_fallback)
        if fallback_count > 0:
            print(f"  [AssetMatcher] VQ1: {len(updated)} units, {fallback_count} fallbacks")

        return updated

    # ── Multi-Dimension Scoring Engine (V3) ────────────

    def _match_multi_dim(
        self, query_tags: list[str], query_mood: str = "", query_topic: str = "",
        query_scene_type: str = "general", query_text: str = "", top_n: int = 5,
        exclude_ids: set[str] | None = None,
    ) -> list[ScoredAsset]:
        exclude_ids = exclude_ids or set()
        query_set = set(query_tags)
        preferred_cats = MOOD_CATEGORY_MAP.get(query_mood, [])
        topic_country, topic_city = self._extract_location_from_topic(query_topic)
        scored: list[ScoredAsset] = []

        # Lazy-load CLIP model once for semantic scoring
        clip_model = None
        clip_tokenizer = None
        clip_preprocess = None
        query_text_feat = None
        if query_text:
            try:
                clip_model, clip_tokenizer, clip_preprocess = self._get_clip_model()
                query_text_feat = self._encode_text(query_text, clip_model, clip_tokenizer)
            except Exception:
                pass

        for record in self._records:
            if record.id in exclude_ids:
                continue
            record_tags = set(record.tags)

            # 0. Semantic score (CLIP cosine similarity) — HIGHEST WEIGHT
            semantic_score = 0.0
            if query_text_feat is not None and clip_model is not None:
                semantic_score = self._compute_semantic_score(
                    record, query_text_feat, clip_model, clip_preprocess)

            # 1. Scene Type score
            scene_type_score = 1.0 if (query_scene_type and record.scene_type == query_scene_type) else 0.0

            # 2. Tag score
            tag_score = len(query_set & record_tags) / len(query_set) if query_tags else 0.0

            # 3. Mood score
            mood_score = 0.0
            if query_mood and preferred_cats:
                if record.moods and query_mood in record.moods:
                    mood_score = 1.0
                elif record.category and record.category in preferred_cats:
                    mood_score = 0.6
                else:
                    for cat in preferred_cats:
                        if record_tags & set(_CATEGORY_KEYWORDS.get(cat, [])):
                            mood_score = 0.3; break

            # 4. City score
            city_score = 0.0
            if topic_city:
                if record.city and record.city.lower() == topic_city.lower():
                    city_score = 1.0
                elif record_tags & set(_CITY_KEYWORDS.get(topic_city.lower(), [topic_city])):
                    city_score = 0.5

            # 5. Quality score (from asset or default)
            quality_score = (record.quality_score or 0.5) if record.quality_score else 0.5

            final = round(
                self.weight_semantic    * semantic_score
                + self.weight_scene_type * scene_type_score
                + self.weight_tag        * tag_score
                + self.weight_mood       * mood_score
                + self.weight_city       * city_score
                + self.weight_quality    * quality_score, 4)

            # Include if any match signal exists
            # V4: also require either tag or non-general scene_type
            has_real_match = (tag_score > 0 or semantic_score > 0.15
                              or (scene_type_score > 0 and query_scene_type != "general"))
            has_broad = (not query_tags and not query_text) and final > 0.03
            if has_real_match or has_broad:
                scored.append(ScoredAsset(
                    id=record.id, path=record.path, type=record.type,
                    tags=record.tags, country=record.country, city=record.city,
                    category=record.category, scene_type=record.scene_type,
                    moods=record.moods, duration=record.duration, final_score=final,
                    semantic_score=round(semantic_score, 4),
                    scene_type_score=round(scene_type_score, 4),
                    tag_score=round(tag_score, 4), mood_score=round(mood_score, 4),
                    country_score=0.0, city_score=round(city_score, 4),
                    type_score=0.0, quality_score=round(quality_score, 4),
                ))

        scored.sort(key=lambda x: x.final_score, reverse=True)
        return scored[:top_n]

    # ── Semantic Search (V4) ───────────────────────────

    _clip_cache = None

    @staticmethod
    def _get_clip_model():
        """Lazy-load and cache CLIP model."""
        if AssetLibraryManager._clip_cache is not None:
            return AssetLibraryManager._clip_cache
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k")
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()
        AssetLibraryManager._clip_cache = (model, tokenizer, preprocess)
        return AssetLibraryManager._clip_cache

    @staticmethod
    def _encode_text(text: str, model, tokenizer):
        import torch
        tokens = tokenizer([text])
        with torch.no_grad():
            feat = model.encode_text(tokens)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat

    @staticmethod
    def _encode_image(image_path: str, model, preprocess):
        import torch
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        img_tensor = preprocess(img).unsqueeze(0)
        with torch.no_grad():
            feat = model.encode_image(img_tensor)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat

    @staticmethod
    def _compute_semantic_score(record, query_text_feat, model, preprocess) -> float:
        """Compute cosine similarity between scene text and asset thumbnail."""
        import numpy as np
        import torch
        # Try loading precomputed embedding from disk
        emb_path = None
        if getattr(record, 'embedding_path', '') and Path(getattr(record, 'embedding_path', '')).exists():
            emb_path = Path(record.embedding_path)
        elif hasattr(record, 'thumbnail') and record.thumbnail:
            # Look for .npy alongside thumbnail
            thumb = Path("assets") / record.thumbnail
            candidate = thumb.with_suffix(".npy")
            # Also check embeddings dir
            alt = Path("assets/embeddings") / (record.id + ".npy")
            if alt.exists():
                emb_path = alt
            elif candidate.exists():
                emb_path = candidate

        if emb_path:
            try:
                img_feat = torch.from_numpy(np.load(str(emb_path)))
                return float((query_text_feat @ img_feat.T).item())
            except Exception:
                pass

        # Fallback: compute from thumbnail
        if hasattr(record, 'thumbnail') and record.thumbnail:
            thumb = Path("assets") / record.thumbnail
            if thumb.exists():
                try:
                    img_feat = AssetLibraryManager._encode_image(str(thumb), model, preprocess)
                    return float((query_text_feat @ img_feat.T).item())
                except Exception:
                    pass
        return 0.0

    # ── Legacy V1 Match ────────────────────────────────

    def match(self, query_tags: list[str], top_n: int = 5, exclude_ids: set[str] | None = None) -> list[ScoredAsset]:
        if not query_tags:
            return []
        return self._match_multi_dim(query_tags=query_tags, top_n=top_n, exclude_ids=exclude_ids)

    def match_for_scenes(self, scenes: list, top_n: int = 5) -> list[dict]:
        results = []
        used_ids: set[str] = set()
        for scene in scenes:
            matched = self.match_scene(scene=scene, top_n=top_n, exclude_ids=used_ids)
            if matched:
                used_ids.add(matched[0].id)
            results.append({
                "scene_id": getattr(scene, "id", -1),
                "asset_tags": getattr(scene, "asset_tags", []),
                "matched_assets": matched,
            })
        return results

    def _extract_location_from_topic(self, topic: str) -> tuple[str, str]:
        if not topic:
            return "", ""
        topic_lower = topic.lower()
        country = ""
        for ctr, kws in _COUNTRY_KEYWORDS.items():
            for kw in kws:
                if kw in topic_lower:
                    country = ctr; break
            if country:
                break
        city = ""
        for ct, kws in _CITY_KEYWORDS.items():
            for kw in kws:
                if kw in topic_lower:
                    city = ct; break
            if city:
                break
        return country, city

    # ── Scan ───────────────────────────────────────────

    def scan_and_generate_index(self) -> list[AssetRecord]:
        old_records: dict[str, AssetRecord] = {}
        if self.index_path.exists():
            try:
                for item in load_json(self.index_path):
                    old_records[item["path"]] = AssetRecord(**item)
            except Exception:
                pass
        new_records = []
        for idx, rel_path in enumerate(sorted(self._find_media_files()), 1):
            abs_path = self.assets_dir / rel_path
            country, city, category = self._infer_location(rel_path)
            file_type = "video" if rel_path.suffix.lower() in VIDEO_EXTS else "image"
            duration, resolution = (None, "")
            orientation = ""
            if file_type == "video":
                duration, resolution = self._probe_video(abs_path)
            else:
                resolution = self._probe_image(abs_path)
            if resolution:
                w, h = [int(x) for x in resolution.split("x")]
                orientation = "vertical" if h > w else "horizontal"
            file_size_kb = abs_path.stat().st_size // 1024
            old = old_records.get(str(rel_path).replace("\\", "/"))
            tags = old.tags if old and old.tags else []
            moods = old.moods if old and old.moods else []
            scene_type = old.scene_type if old and old.scene_type != "general" else "general"
            source = old.source if old and old.source else ""
            license_ = old.license_ if old and old.license_ else ""
            record = AssetRecord(
                id=f"asset_{idx:03d}", path=str(rel_path).replace("\\", "/"),
                type=file_type, tags=tags, country=country, city=city,
                category=category, scene_type=scene_type, moods=moods,
                duration=duration, resolution=resolution, orientation=orientation,
                file_size_kb=file_size_kb, source=source, license_=license_,
            )
            new_records.append(record)
        self._records = new_records
        self._save()
        return new_records

    def generate_report(self) -> dict:
        records = self._records
        if not records:
            return {"error": "素材库为空"}
        videos = [r for r in records if r.type == "video"]
        images = [r for r in records if r.type == "image"]
        tag_counter = Counter(); cat_counter = Counter(); ctr_counter = Counter()
        st_counter = Counter(); mood_counter = Counter(); res_counter = Counter()
        for r in records:
            tag_counter.update(r.tags)
            if r.category: cat_counter[r.category] += 1
            if r.country: ctr_counter[r.country] += 1
            if r.scene_type: st_counter[r.scene_type] += 1
            if r.resolution: res_counter[r.resolution] += 1
            mood_counter.update(r.moods)
        return {
            "summary": {
                "total": len(records), "videos": len(videos), "images": len(images),
                "total_video_duration_sec": round(sum(r.duration or 0 for r in videos), 1),
                "total_size_kb": sum(r.file_size_kb for r in records),
            },
            "by_category": dict(cat_counter.most_common()),
            "by_country": dict(ctr_counter.most_common()),
            "by_scene_type": dict(st_counter.most_common()),
            "by_resolution": dict(res_counter.most_common()),
            "by_moods": dict(mood_counter.most_common()),
            "top_tags": tag_counter.most_common(20),
            "total_unique_tags": len(tag_counter),
            "untagged": len([r for r in records if not r.tags]),
            "unmooded": len([r for r in records if not r.moods]),
        }

    # ── Tag Management ─────────────────────────────────

    def add_tags(self, asset_id: str, tags: list[str]) -> None:
        for r in self._records:
            if r.id == asset_id:
                existing = set(r.tags)
                for t in tags:
                    t = t.strip()
                    if t and t not in existing:
                        r.tags.append(t); existing.add(t)
                self._save(); return
        raise ValueError(f"素材 {asset_id} 不存在")

    def remove_tags(self, asset_id: str, tags: list[str]) -> None:
        for r in self._records:
            if r.id == asset_id:
                r.tags = [t for t in r.tags if t not in tags]
                self._save(); return
        raise ValueError(f"素材 {asset_id} 不存在")

    def set_moods(self, asset_id: str, moods: list[str]) -> None:
        for r in self._records:
            if r.id == asset_id:
                r.moods = [m.strip() for m in moods if m.strip()]
                self._save(); return
        raise ValueError(f"素材 {asset_id} 不存在")

    def set_scene_type(self, asset_id: str, scene_type: str) -> None:
        if not SceneType.is_valid(scene_type):
            raise ValueError(f"无效 scene_type: {scene_type}")
        for r in self._records:
            if r.id == asset_id:
                r.scene_type = scene_type
                self._save(); return
        raise ValueError(f"素材 {asset_id} 不存在")

    def list_assets(self) -> list[dict]:
        return [{
            "id": r.id, "path": r.path, "type": r.type, "tags": r.tags,
            "category": r.category, "country": r.country, "city": r.city,
            "scene_type": r.scene_type, "moods": r.moods, "duration": r.duration,
        } for r in self._records]

    # ── Private ────────────────────────────────────────

    def _find_media_files(self) -> list[Path]:
        files = []
        for root, dirs, filenames in os.walk(self.assets_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in filenames:
                if fname.startswith(".") or fname.startswith("_") or fname in ("index.json", ".gitkeep"):
                    continue
                if Path(fname).suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
                    files.append(Path(root) / fname)
        return [f.relative_to(self.assets_dir) for f in files]

    def _probe_video(self, abs_path: Path) -> tuple[float | None, str]:
        ff = self._find_ffprobe()
        if not ff:
            return None, ""
        try:
            proc = subprocess.run(
                [ff, "-v", "error", "-show_entries", "format=duration", "-show_entries", "stream=width,height", "-of", "json", str(abs_path)],
                capture_output=True, text=True, timeout=15)
            if proc.returncode != 0: return None, ""
            data = json.loads(proc.stdout)
            dur = round(float(data["format"]["duration"]), 1) if "format" in data and "duration" in data["format"] else None
            res = ""
            for s in data.get("streams", []):
                if "width" in s and "height" in s:
                    res = f"{s['width']}x{s['height']}"; break
            return dur, res
        except Exception:
            return None, ""

    def _probe_image(self, abs_path: Path) -> str:
        try:
            if abs_path.suffix.lower() in (".jpg", ".jpeg"): return self._probe_jpeg(abs_path)
            if abs_path.suffix.lower() == ".png": return self._probe_png(abs_path)
        except Exception: pass
        return ""

    def _probe_jpeg(self, path: Path) -> str:
        with open(path, "rb") as f:
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF: break
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    f.read(3); h = int.from_bytes(f.read(2), "big"); w = int.from_bytes(f.read(2), "big")
                    return f"{w}x{h}"
                f.read(int.from_bytes(f.read(2), "big") - 2)
        return ""

    def _probe_png(self, path: Path) -> str:
        with open(path, "rb") as f:
            f.read(16); w = int.from_bytes(f.read(4), "big"); h = int.from_bytes(f.read(4), "big")
            return f"{w}x{h}"

    def _infer_location(self, rel_path: Path) -> tuple[str, str, str]:
        parts = rel_path.parts; country = ""; city = ""; category = ""
        for part in parts[:-1]:
            pl = part.lower().replace("_", "-")
            for ck, kws in _CATEGORY_KEYWORDS.items():
                if pl == ck or pl in kws: category = ck; break
            else:
                if pl in _COUNTRY_KEYWORDS or pl in ["malaysia","china","japan","thailand","indonesia","vietnam","korea","singapore","taiwan","australia","new-zealand","france","italy","spain","uk","usa","canada"]:
                    country = pl
                elif pl in _CITY_KEYWORDS or pl in ["sabah","kuala-lumpur","tokyo","osaka","kyoto","yunnan","lijiang"]:
                    city = pl
                elif not category and pl != "general":
                    city = pl
        if not category:
            fname = rel_path.stem.lower()
            for ck, kws in _CATEGORY_KEYWORDS.items():
                for kw in kws:
                    if kw in fname: category = ck; break
                if category: break
        return country, city, category

    def _find_ffprobe(self) -> str | None:
        import shutil as _shutil
        path = _shutil.which("ffprobe")
        if path:
            return path
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if (Path(p) / "ffprobe.exe").exists(): return str(Path(p) / "ffprobe.exe")
        return None

    def _save(self) -> None:
        save_json([r.model_dump() for r in self._records], self.index_path)
