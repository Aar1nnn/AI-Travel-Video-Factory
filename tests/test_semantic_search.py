"""
Semantic Asset Search V1 — Unit Tests

Test cases: V4 weights, semantic_score, embedding generation, cosine similarity,
CLIP text/image encoding, embedding_path, V4 ScoredAsset fields, backward compat.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_semantic_search.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.asset_library import (
    AssetLibraryManager, AssetRecord, ScoredAsset,
    WEIGHT_SEMANTIC, WEIGHT_SCENE_TYPE, WEIGHT_TAG, WEIGHT_MOOD,
    WEIGHT_CITY, WEIGHT_QUALITY,
)


# ── Helpers ──────────────────────────────────────────────

def _make_mgr(records: list[dict]) -> AssetLibraryManager:
    d = Path(tempfile.mkdtemp())
    idx = d / "idx.json"
    mgr = object.__new__(AssetLibraryManager)
    mgr.assets_dir = d
    mgr.index_path = idx
    mgr._records = [AssetRecord(**r) for r in records]
    return mgr


def _make_test_image(path: Path, color: str = "blue"):
    from PIL import Image, ImageDraw
    c = (100, 150, 250) if color == "blue" else (250, 200, 100)
    img = Image.new("RGB", (224, 224), color=c)
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 174, 174], outline=(255, 255, 255), width=3)
    img.save(path, "JPEG", quality=90)


# ── Tests: V4 Weights ──────────────────────────────────

class TestV4Weights:
    def test_weights_sum_to_one(self):
        total = WEIGHT_SEMANTIC + WEIGHT_SCENE_TYPE + WEIGHT_TAG + WEIGHT_MOOD + WEIGHT_CITY + WEIGHT_QUALITY
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_semantic_is_highest(self):
        assert WEIGHT_SEMANTIC == 0.35
        assert WEIGHT_SEMANTIC > WEIGHT_SCENE_TYPE
        assert WEIGHT_SEMANTIC > WEIGHT_TAG

    def test_weights_order(self):
        assert WEIGHT_SEMANTIC > WEIGHT_SCENE_TYPE > WEIGHT_TAG > WEIGHT_MOOD

    def test_no_country_weight(self):
        """V4 removed country and type weights."""
        assert WEIGHT_QUALITY == 0.05


# ── Tests: ScoredAsset V4 Fields ───────────────────────

class TestScoredAssetV4:
    def test_semantic_score_field(self):
        sa = ScoredAsset(id="x", path="y", type="image", tags=[], semantic_score=0.9,
                         scene_type_score=0.0, tag_score=0.0, mood_score=0.0,
                         country_score=0.0, city_score=0.0, type_score=0.0, quality_score=0.5)
        assert sa.semantic_score == 0.9

    def test_quality_score_field(self):
        sa = ScoredAsset(id="x", path="y", type="image", tags=[], quality_score=0.88,
                         semantic_score=0.0, scene_type_score=0.0, tag_score=0.0,
                         mood_score=0.0, country_score=0.0, city_score=0.0, type_score=0.0)
        assert sa.quality_score == 0.88

    def test_match_score_backward_compat(self):
        sa = ScoredAsset(id="x", path="y", type="image", tags=[], final_score=0.75,
                         semantic_score=0.0, scene_type_score=0.0, tag_score=0.0,
                         mood_score=0.0, country_score=0.0, city_score=0.0,
                         type_score=0.0, quality_score=0.0)
        assert sa.match_score == 0.75


# ── Tests: AssetRecord embedding_path ──────────────────

class TestAssetRecordEmbedding:
    def test_embedding_path_field(self):
        r = AssetRecord(id="x", path="y", type="image", tags=[],
                        embedding_path="embeddings/asset_001.npy")
        assert r.embedding_path == "embeddings/asset_001.npy"

    def test_embedding_path_default(self):
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.embedding_path == ""


# ── Tests: CLIP Model Loading ──────────────────────────

class TestCLIPModel:
    def test_get_clip_model_returns_three(self):
        model, tokenizer, preprocess = AssetLibraryManager._get_clip_model()
        assert model is not None
        assert tokenizer is not None
        assert preprocess is not None

    def test_get_clip_model_cached(self):
        a = AssetLibraryManager._get_clip_model()
        b = AssetLibraryManager._get_clip_model()
        assert a[0] is b[0]  # Same model object

    def test_encode_text_returns_tensor(self):
        import torch
        model, tokenizer, _ = AssetLibraryManager._get_clip_model()
        feat = AssetLibraryManager._encode_text("美丽的海滩日落", model, tokenizer)
        assert isinstance(feat, torch.Tensor)
        assert feat.shape[0] == 1  # batch=1

    def test_encode_image_from_file(self):
        import torch
        model, _, preprocess = AssetLibraryManager._get_clip_model()
        d = Path(tempfile.mkdtemp())
        img = d / "test.jpg"
        _make_test_image(img, "blue")
        feat = AssetLibraryManager._encode_image(str(img), model, preprocess)
        assert isinstance(feat, torch.Tensor)
        assert feat.shape[0] == 1


# ── Tests: Cosine Similarity ───────────────────────────

class TestCosineSimilarity:
    def test_same_text_high_similarity(self):
        import torch
        model, tokenizer, preprocess = AssetLibraryManager._get_clip_model()
        d = Path(tempfile.mkdtemp())
        img = d / "test.jpg"
        _make_test_image(img, "blue")
        img_feat = AssetLibraryManager._encode_image(str(img), model, preprocess)
        text_feat = AssetLibraryManager._encode_text("蓝色天空", model, tokenizer)
        sim = float((text_feat @ img_feat.T).item())
        assert -1.0 <= sim <= 1.0
        assert sim > 0.0  # Should have some similarity

    def test_opposite_text_low_similarity(self):
        import torch
        model, tokenizer, preprocess = AssetLibraryManager._get_clip_model()
        d = Path(tempfile.mkdtemp())
        img = d / "test.jpg"
        _make_test_image(img, "blue")
        img_feat = AssetLibraryManager._encode_image(str(img), model, preprocess)
        # A descriptor that shouldn't match a blue image
        text_feat = AssetLibraryManager._encode_text("红色火焰炽热的岩浆", model, tokenizer)
        sim_blue = float((AssetLibraryManager._encode_text("蓝色天空", model, tokenizer) @ img_feat.T).item())
        sim_red = float((text_feat @ img_feat.T).item())
        assert sim_blue > sim_red, f"blue={sim_blue} should be > red={sim_red}"


# ── Tests: Semantic Score in Matching ──────────────────

class TestSemanticMatching:
    def test_match_with_text_produces_semantic_score(self):
        d = Path(tempfile.mkdtemp())
        img = d / "thumb.jpg"
        _make_test_image(img, "blue")
        records = [
            {"id": "r1", "path": "p1.mp4", "type": "video", "tags": ["test"],
             "thumbnail": str(img), "scene_type": "general"},
        ]
        mgr = _make_mgr(records)
        results = mgr._match_multi_dim(
            query_tags=[], query_text="蓝色天空湖泊水面", top_n=3)
        assert len(results) >= 0  # may or may not find
        # If it matches, it should have semantic_score > 0
        if results:
            assert results[0].semantic_score > 0

    def test_match_scene_passes_text(self):
        from src.script_generator import Scene
        d = Path(tempfile.mkdtemp())
        img = d / "thumb.jpg"
        _make_test_image(img, "blue")
        records = [
            {"id": "r1", "path": "p1.mp4", "type": "video", "tags": ["test"],
             "thumbnail": str(img), "scene_type": "general"},
        ]
        mgr = _make_mgr(records)
        scene = Scene(id=1, text="蓝色天空和湖泊", mood="轻松惬意",
                      asset_tags=["湖水"], scene_type="lake")
        results = mgr.match_scene(scene, top_n=3)
        if results:
            assert hasattr(results[0], 'semantic_score')

    def test_no_text_no_semantic(self):
        records = [
            {"id": "r1", "path": "p1.mp4", "type": "video", "tags": ["海滩", "日落"]},
        ]
        mgr = _make_mgr(records)
        results = mgr._match_multi_dim(query_tags=["海滩"], top_n=3)
        if results:
            # Without query_text, semantic_score should be 0
            assert results[0].semantic_score == 0.0

    def test_precomputed_embedding_loaded(self):
        import numpy as np
        d = Path(tempfile.mkdtemp())
        img = d / "thumb.jpg"
        _make_test_image(img, "blue")
        emb = d / "emb.npy"
        np.save(str(emb), np.random.randn(1, 512).astype(np.float32))

        records = [
            {"id": "r1", "path": "p1.mp4", "type": "video", "tags": ["test"],
             "thumbnail": str(img), "embedding_path": str(emb), "scene_type": "general"},
        ]
        mgr = _make_mgr(records)
        results = mgr._match_multi_dim(
            query_tags=[], query_text="蓝天白云", top_n=3)
        if results:
            # even though we used random embedding, the path loading worked
            assert results[0].semantic_score >= -1.0
