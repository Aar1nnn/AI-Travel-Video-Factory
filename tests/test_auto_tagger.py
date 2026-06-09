"""
Auto Tagger — Unit Tests

Test cases: module import, label definitions, scene_type classification,
tag matching, tag_asset(), tag_all(), confidence threshold, edge cases.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_auto_tagger.py -v
"""

import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Helpers ──────────────────────────────────────────────

def _make_tagger() -> "AutoTagger":
    from src.auto_tagger import AutoTagger
    return AutoTagger()


def _make_test_image(output_path: Path, text: str = "blue sky") -> Path:
    """Generate a small test image with PIL."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (224, 224), color=(100, 150, 250) if "blue" in text else (50, 100, 50))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 174, 174], outline=(255, 200, 50), width=3)
    img.save(output_path, "JPEG", quality=90)
    return output_path


# ── Tests: Module & Init ────────────────────────────────

class TestInit:
    def test_import(self):
        from src.auto_tagger import AutoTagger
        assert AutoTagger is not None

    def test_init_default_model(self):
        tagger = _make_tagger()
        assert tagger.model_name == "ViT-B-32"
        assert tagger.pretrained == "laion2b_s34b_b79k"

    def test_lazy_init_not_loaded_on_create(self):
        tagger = _make_tagger()
        assert tagger._model is None
        assert tagger._preprocess is None
        assert tagger._tokenizer is None


# ── Tests: Label Definitions ────────────────────────────

class TestLabels:
    def test_scene_type_labels_count(self):
        from src.auto_tagger import SCENE_TYPE_LABELS
        assert len(SCENE_TYPE_LABELS) == 16

    def test_all_scene_type_keys_valid(self):
        from src.auto_tagger import SCENE_TYPE_LABELS, _SCENE_TYPE_KEYS
        from src.asset_library import SceneType
        for k in _SCENE_TYPE_KEYS:
            assert SceneType.is_valid(k), f"'{k}' not in SceneType"

    def test_location_tags_not_empty(self):
        from src.auto_tagger import LOCATION_TAGS_CN
        assert len(LOCATION_TAGS_CN) > 10

    def test_content_tags_not_empty(self):
        from src.auto_tagger import CONTENT_TAGS_CN
        assert len(CONTENT_TAGS_CN) > 15

    def test_all_tags_combined(self):
        from src.auto_tagger import ALL_TAGS_CN, LOCATION_TAGS_CN, CONTENT_TAGS_CN
        assert len(ALL_TAGS_CN) == len(LOCATION_TAGS_CN) + len(CONTENT_TAGS_CN)

    def test_scene_type_prompts_match_keys(self):
        from src.auto_tagger import _SCENE_TYPE_KEYS, _SCENE_TYPE_PROMPTS
        assert len(_SCENE_TYPE_KEYS) == len(_SCENE_TYPE_PROMPTS)

    def test_max_tags_limit(self):
        from src.auto_tagger import MAX_TAGS
        assert MAX_TAGS <= 12  # Reasonable upper bound


# ── Tests: tag_asset() ─────────────────────────────────

class TestTagAsset:
    def test_tag_asset_returns_dict(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "blue sky and lake")
        try:
            result = tagger.tag_asset(img_path)
            assert isinstance(result, dict)
            assert "scene_type" in result
            assert "tags" in result
            assert "confidence" in result
        finally:
            img_path.unlink()

    def test_tag_asset_scene_type_is_valid(self):
        from src.asset_library import SceneType
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "snowy mountain peak")
        try:
            result = tagger.tag_asset(img_path)
            assert SceneType.is_valid(result["scene_type"]), \
                f"Invalid scene_type: {result['scene_type']}"
        finally:
            img_path.unlink()

    def test_tag_asset_has_tags(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "beach sunset waves")
        try:
            result = tagger.tag_asset(img_path)
            assert len(result["tags"]) >= 1, "Should have at least 1 tag"
        finally:
            img_path.unlink()

    def test_tag_asset_tags_not_exceed_max(self):
        from src.auto_tagger import MAX_TAGS
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "colorful night city neon lights")
        try:
            result = tagger.tag_asset(img_path)
            assert len(result["tags"]) <= MAX_TAGS
        finally:
            img_path.unlink()

    def test_tag_asset_confidence_range(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "test")
        try:
            result = tagger.tag_asset(img_path)
            assert 0.0 <= result["confidence"] <= 1.0
        finally:
            img_path.unlink()

    def test_tag_asset_missing_file_raises(self):
        tagger = _make_tagger()
        with pytest.raises(FileNotFoundError):
            tagger.tag_asset(Path("/nonexistent/thumb.jpg"))


# ── Tests: Scene Type Classification ───────────────────

class TestSceneTypeClassification:
    def test_classify_returns_tuple(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "mountain snow peak")
        try:
            st, conf = tagger._classify_scene_type(img_path)
            assert isinstance(st, str)
            assert isinstance(conf, float)
            assert st in ["airport","hotel","beach","island","lake","mountain",
                          "city","food","market","temple","sunset","night",
                          "wildlife","shopping","transport","landscape"]
        finally:
            img_path.unlink()

    def test_classify_blue_image_lake_or_landscape(self):
        """A blue image should classify as lake/beach/landscape."""
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "blue water lake surface")
        try:
            st, conf = tagger._classify_scene_type(img_path)
            assert st in ("lake", "beach", "landscape", "island"), \
                f"Expected water-like scene, got {st}"
        finally:
            img_path.unlink()

    def test_classify_consistency(self):
        """Same image should get same scene_type."""
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "blue")
        try:
            st1, c1 = tagger._classify_scene_type(img_path)
            st2, c2 = tagger._classify_scene_type(img_path)
            assert st1 == st2
            assert abs(c1 - c2) < 0.001
        finally:
            img_path.unlink()


# ── Tests: Tag Matching ────────────────────────────────

class TestTagMatching:
    def test_match_tags_returns_lists(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "sunset beach")
        try:
            tags, confs = tagger._match_tags(img_path)
            assert isinstance(tags, list)
            assert isinstance(confs, list)
            assert len(tags) == len(confs)
            assert len(tags) >= 1
        finally:
            img_path.unlink()

    def test_match_tags_all_string(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "test")
        try:
            tags, _ = tagger._match_tags(img_path)
            for t in tags:
                assert isinstance(t, str)
                assert len(t) > 0
        finally:
            img_path.unlink()

    def test_match_tags_confidences_descending(self):
        tagger = _make_tagger()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "test")
        try:
            _, confs = tagger._match_tags(img_path)
            assert confs == sorted(confs, reverse=True), \
                f"Confidences not descending: {confs}"
        finally:
            img_path.unlink()


# ── Tests: Confidence Field ─────────────────────────────

class TestConfidenceField:
    def test_asset_record_has_confidence(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[], confidence=0.85)
        assert r.confidence == 0.85

    def test_asset_record_confidence_default_none(self):
        from src.asset_library import AssetRecord
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.confidence is None


# ── Tests: Model Reuse ─────────────────────────────────

class TestModelReuse:
    def test_second_call_reuses_model(self):
        tagger = _make_tagger()
        assert tagger._model is None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img_path = Path(f.name)
        _make_test_image(img_path, "test")
        try:
            result1 = tagger.tag_asset(img_path)
            assert tagger._model is not None  # Model loaded
            result2 = tagger.tag_asset(img_path)
            assert result1 == result2  # Deterministic
        finally:
            img_path.unlink()


# ── Tests: Device Detection ────────────────────────────

class TestDevice:
    def test_device_is_cpu_or_cuda(self):
        tagger = _make_tagger()
        tagger._init_model()
        assert tagger.device in ("cpu", "cuda")
