"""
模块: Auto Tagger（AI 自动标签系统 — V1）

职责：
- 读取 assets/thumbnails/*.jpg 缩略图
- 使用 CLIP (ViT-B-32) 模型分析画面内容
- 自动标注 scene_type + tags + confidence
- 写回 index.json

技术栈:
- open_clip_torch (CLIP ViT-B-32, laion2b_s34b_b79k)
- torch (CPU inference)
- PIL (image loading)

不调用任何付费 API。完全离线运行。
"""

import json
from pathlib import Path

from src.asset_library import AssetRecord, SceneType
from src.config import (
    ASSETS_DIR, ASSETS_INDEX, ASSETS_THUMBNAILS_DIR,
)


# ── Pre-defined Tag Vocabulary ───────────────────────

# Scene type descriptions (for zero-shot classification)
SCENE_TYPE_LABELS: dict[str, str] = {
    "airport":    "机场航站楼，飞机，出发大厅",
    "hotel":      "酒店房间，大堂，泳池",
    "beach":      "海滩，沙滩，海浪",
    "island":     "海岛，小岛，岛屿风光",
    "lake":       "湖泊，湖水，湖面",
    "mountain":   "高山，雪山，山峰",
    "city":       "城市街道，高楼，城市天际线",
    "food":       "食物，美食，餐厅",
    "market":     "市场，夜市，集市摊位",
    "temple":     "寺庙，神社，宗教建筑",
    "sunset":     "日落，夕阳，晚霞，黄昏",
    "night":      "夜景，霓虹灯，夜晚街道",
    "wildlife":   "动物，鸟类，野生动物",
    "shopping":   "商场，购物中心，商店",
    "transport":  "火车，地铁，交通出行",
    "landscape":  "自然风光，山川河流，草原",
}

# Location tags (中文)
LOCATION_TAGS_CN: list[str] = [
    "云南", "大理", "丽江", "洱海", "玉龙雪山", "蓝月谷", "昆明", "香格里拉",
    "东京", "浅草寺", "东京塔", "涩谷", "秋叶原",
    "沙巴", "亚庇", "丹绒亚路", "马努干岛",
    "古城", "雪山", "湖泊", "森林", "草原", "公路",
]

# Scene content tags (中文)
CONTENT_TAGS_CN: list[str] = [
    "航拍", "俯瞰", "全景", "日落", "夕阳", "黄昏", "夜景", "霓虹",
    "海滩", "沙滩", "海浪", "海岛", "湖景", "云海", "日出",
    "古城", "街道", "建筑", "寺庙", "美食", "夜市", "市场",
    "河流", "公路", "动物", "花朵", "星空",
    "情侣", "旅行", "度假", "背包", "vlog",
    "浪漫", "自然", "山景", "水面", "倒影", "绿色", "蓝天",
]

# All tags combined for zero-shot matching
ALL_TAGS_CN: list[str] = LOCATION_TAGS_CN + CONTENT_TAGS_CN

# Map scene_type labels to their key for zero-shot
_SCENE_TYPE_KEYS = list(SCENE_TYPE_LABELS.keys())
_SCENE_TYPE_PROMPTS = list(SCENE_TYPE_LABELS.values())

# Confidence threshold — lowered for better recall on CPU
MIN_CONFIDENCE = 0.10

# Max tags per asset
MAX_TAGS = 8


# ── Auto Tagger ──────────────────────────────────────

class AutoTagger:
    """
    AI 自动标签系统。

    使用 CLIP ViT-B-32 对缩略图进行零样本分类:
      1. scene_type → 在 16 个 scene_type 中选择最佳匹配
      2. tags        → 在预定义标签词库中选择 top-K 匹配标签
      3. confidence  → 取 scene_type 的 softmax 概率

    Attributes:
        model: CLIP model
        preprocess: CLIP image preprocessing
        tokenizer: CLIP text tokenizer
        device: "cpu" or "cuda"
    """

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        """
        Args:
            model_name: CLIP model variant
            pretrained: pretrained weights name
        """
        self.model_name = model_name
        self.pretrained = pretrained
        self._model = None
        self._preprocess = None
        self._tokenizer = None

    # ── Lazy Init ────────────────────────────────────

    @property
    def model(self):
        if self._model is None:
            self._init_model()
        return self._model

    @property
    def preprocess(self):
        if self._preprocess is None:
            self._init_model()
        return self._preprocess

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._init_model()
        return self._tokenizer

    def _init_model(self) -> None:
        """懒加载 CLIP 模型（首次调用时加载）。"""
        import open_clip
        import torch
        print(f"  [AutoTagger] Loading CLIP model: {self.model_name} ({self.pretrained})...")
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=self.pretrained,
        )
        tokenizer = open_clip.get_tokenizer(self.model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = model.to(self.device).eval()
        self._preprocess = preprocess
        self._tokenizer = tokenizer
        print(f"  [AutoTagger] Model loaded on {self.device}")

    # ── Public API ───────────────────────────────────

    def tag_asset(self, thumbnail_path: Path) -> dict:
        """
        对单个缩略图进行 CLIP 分类。

        Args:
            thumbnail_path: 缩略图路径

        Returns:
            {"scene_type": "lake", "tags": ["云南","洱海","湖泊"], "confidence": 0.82}

        Raises:
            FileNotFoundError: 缩略图不存在
        """
        if not thumbnail_path.exists():
            raise FileNotFoundError(f"缩略图不存在: {thumbnail_path}")

        # 1. Scene type classification
        scene_type, st_confidence = self._classify_scene_type(thumbnail_path)

        # 2. Tag matching
        tags, tag_confidences = self._match_tags(thumbnail_path)

        # 3. Combine: scene_type as first tag equivalent, then other tags
        # Use scene_type confidence as overall confidence
        confidence = round(st_confidence, 4)

        return {
            "scene_type": scene_type,
            "tags": tags[:MAX_TAGS],
            "confidence": confidence,
        }

    def tag_all(self) -> list[dict]:
        """
        对 index.json 中所有有缩略图的素材进行标注。

        Returns:
            更新后的 AssetRecord 列表（仅返回有缩略图的记录）

        Side effect:
            更新 index.json
        """
        from src.asset_library import AssetLibraryManager
        mgr = AssetLibraryManager(ASSETS_DIR, ASSETS_INDEX)
        records = mgr.get_all_records()
        tagged_count = 0

        for record in records:
            if not record.thumbnail:
                continue

            thumb_path = ASSETS_DIR / record.thumbnail
            if not thumb_path.exists():
                continue

            try:
                result = self.tag_asset(thumb_path)
            except Exception as e:
                print(f"  [AutoTagger] ERROR {record.id}: {e}")
                continue

            # Update record
            mgr.set_scene_type(record.id, result["scene_type"])
            # Clear existing tags and set new ones
            existing = set(record.tags)
            for t in result["tags"]:
                if t not in existing:
                    try:
                        mgr.add_tags(record.id, [t])
                    except Exception:
                        pass
                    existing.add(t)

            # Update confidence
            for r in mgr._records:
                if r.id == record.id:
                    r.confidence = result["confidence"]
                    break

            tagged_count += 1
            print(f"  {record.id}: scene_type={result['scene_type']} "
                  f"tags={result['tags'][:5]} conf={result['confidence']:.2f}")

        mgr._save()
        print(f"  [AutoTagger] 完成: {tagged_count} 素材已标注")
        return tagged_count

    # ── CLIP Classification ──────────────────────────

    def _classify_scene_type(self, image_path: Path) -> tuple[str, float]:
        """
        用 CLIP 零样本分类确定 scene_type。

        在 16 个 scene_type 中计算图像-文本相似度，
        取最高相似度的类型。

        Returns:
            (scene_type_key, confidence)
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        texts = [f"一张{desc}的照片" for desc in _SCENE_TYPE_PROMPTS]
        text_tokens = self.tokenizer(texts).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_tokens)

            # Normalize
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            # Cosine similarity
            similarity = (image_features @ text_features.T).squeeze(0)
            probs = similarity.softmax(dim=0)

        best_idx = int(probs.argmax().item())
        best_type = _SCENE_TYPE_KEYS[best_idx]
        confidence = float(probs[best_idx].item())

        return best_type, confidence

    def _match_tags(self, image_path: Path) -> tuple[list[str], list[float]]:
        """
        用 CLIP 在预定义标签词库中匹配最相关的标签。

        计算每个标签与图片的相似度，取 top-k。

        Returns:
            (tags_list, confidence_list)
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        texts = [f"{tag}" for tag in ALL_TAGS_CN]
        text_tokens = self.tokenizer(texts).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_tokens)

            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            similarity = (image_features @ text_features.T).squeeze(0)

        # Get top scoring tags above threshold
        scores = similarity.cpu().tolist()
        pairs = sorted(zip(ALL_TAGS_CN, scores), key=lambda x: -x[1])

        tags = [tag for tag, score in pairs if score >= MIN_CONFIDENCE]
        confs = [score for tag, score in pairs if score >= MIN_CONFIDENCE]

        # Ensure at least 1 tag
        if not tags:
            tags = [pairs[0][0]]
            confs = [pairs[0][1]]

        return tags, confs
