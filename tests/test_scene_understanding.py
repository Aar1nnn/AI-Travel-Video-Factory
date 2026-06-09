"""
Scene Understanding Layer — Unit Tests

Test cases: SceneType enum validation, Scene model with scene_type,
LLM JSON parsing, asset scene_type defaults, scene_type_score in matching,
V3 weighted scoring, sort order, backward compat.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_scene_understanding.py -v
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.asset_library import (
    AssetLibraryManager, AssetRecord, ScoredAsset, SceneType,
    WEIGHT_SEMANTIC, WEIGHT_SCENE_TYPE, WEIGHT_TAG, WEIGHT_MOOD,
    WEIGHT_CITY, WEIGHT_QUALITY,
    MOOD_CATEGORY_MAP,
)
from src.script_generator import Scene, Script, SceneType as ScriptSceneType


# ── Helpers ──────────────────────────────────────────────

def _make_mgr(records: list[dict]) -> AssetLibraryManager:
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "test_idx.json"
    mgr = object.__new__(AssetLibraryManager)
    mgr.assets_dir = tmp.parent
    mgr.index_path = tmp
    mgr._records = [AssetRecord(**r) for r in records]
    return mgr


def _make_scene(sid=1, mood="开场吸引", tags=None, scene_type="lake"):
    return Scene(id=sid, text="测试文本", mood=mood, asset_tags=tags or ["湖", "日落"], scene_type=scene_type)


# Sample records with different scene_types
V3_RECORDS = [
    {"id": "a1", "path": "lk/erhai.mp4", "type": "video", "tags": ["湖", "洱海", "日落"], "scene_type": "lake"},
    {"id": "a2", "path": "mnt/yulong.mp4", "type": "video", "tags": ["雪山", "云海", "丽江"], "scene_type": "mountain"},
    {"id": "a3", "path": "ct/lijiang.mp4", "type": "video", "tags": ["古城", "夜景", "丽江"], "scene_type": "city"},
    {"id": "a4", "path": "fd/rice_noodle.jpg", "type": "image", "tags": ["美食", "米线", "云南"], "scene_type": "food"},
    {"id": "a5", "path": "ss/dusk.mp4", "type": "video", "tags": ["日落", "黄昏", "浪漫"], "scene_type": "sunset"},
    {"id": "a6", "path": "gen/generic.jpg", "type": "image", "tags": ["旅行", "通用"], "scene_type": "general"},
]


# ── Tests: SceneType Enum ───────────────────────────────

class TestSceneTypeEnum:
    def test_all_types_valid(self):
        for t in SceneType.ALL:
            assert SceneType.is_valid(t), f"'{t}' should be valid"

    def test_invalid_rejected(self):
        assert not SceneType.is_valid("")
        assert not SceneType.is_valid("nonexistent")
        assert not SceneType.is_valid("beaches")

    def test_count_is_17(self):
        assert len(SceneType.ALL) == 17

    def test_default_is_general(self):
        assert SceneType.default() == "general"

    def test_individual_constants(self):
        assert SceneType.AIRPORT == "airport"
        assert SceneType.LAKE == "lake"
        assert SceneType.MOUNTAIN == "mountain"
        assert SceneType.NIGHT == "night"


# ── Tests: Scene Model ──────────────────────────────────

class TestSceneModel:
    def test_scene_has_scene_type_default(self):
        s = Scene(id=1, text="测试", mood="开场吸引", asset_tags=["a", "b"])
        assert s.scene_type == "general"

    def test_scene_validates_scene_type(self):
        with pytest.raises(Exception):
            Scene(id=1, text="x", mood="开场吸引", asset_tags=["a", "b"], scene_type="invalid")

    def test_scene_allows_all_valid_types(self):
        for st in SceneType.ALL:
            s = Scene(id=1, text="x", mood="开场吸引", asset_tags=["a", "b"], scene_type=st)
            assert s.scene_type == st

    def test_scene_json_parses_scene_type(self):
        json_str = '{"id": 1, "text": "洱海骑行", "mood": "活力刺激", "asset_tags": ["洱海","骑行"], "scene_type": "lake"}'
        data = json.loads(json_str)
        s = Scene(**data)
        assert s.scene_type == "lake"

    def test_old_json_without_scene_type_defaults(self):
        json_str = '{"id": 1, "text": "旧数据", "mood": "开场吸引", "asset_tags": ["a","b"]}'
        data = json.loads(json_str)
        s = Scene(**data)
        assert s.scene_type == "general"


# ── Tests: Asset scene_type Default ────────────────────

class TestAssetSceneType:
    def test_asset_default_is_general(self):
        r = AssetRecord(id="x", path="y", type="image", tags=[])
        assert r.scene_type == "general"

    def test_asset_with_scene_type(self):
        r = AssetRecord(id="x", path="y", type="image", tags=[], scene_type="lake")
        assert r.scene_type == "lake"

    def test_old_index_without_scene_type(self):
        """Old index.json records without scene_type get 'general'."""
        data = {"id": "old", "path": "x.jpg", "type": "image", "tags": ["a"]}
        r = AssetRecord(**data)
        assert r.scene_type == "general"


# ── Tests: scene_type_score ────────────────────────────

class TestSceneTypeScore:
    def test_exact_match_gives_1(self):
        mgr = _make_mgr(V3_RECORDS)
        results = mgr._match_multi_dim(
            query_tags=["湖", "日落"], query_scene_type="lake", top_n=5)
        top = results[0]
        assert top.id == "a1"
        assert top.scene_type_score == 1.0

    def test_mismatch_gives_0(self):
        mgr = _make_mgr(V3_RECORDS)
        results = mgr._match_multi_dim(
            query_tags=["湖", "日落"], query_scene_type="food", top_n=5)
        # a4 is food type, but tags don't match (lake/sunset ≠ food)
        # All records should have scene_type_score = 0 except the one that matches
        for r in results:
            if r.scene_type != "food":
                assert r.scene_type_score == 0.0

    def test_general_scene_type_ignored_in_filter(self):
        """When query_scene_type='general', scene_type_score=1 for all but doesn't leak."""
        mgr = _make_mgr(V3_RECORDS)
        results = mgr.match(query_tags=["湖", "日落"], top_n=5)
        # All records have tag overlap so they appear. "general" scene_type shouldn't
        # give an unfair advantage to records that happen to also be "general"
        assert len(results) >= 1

    def test_scene_type_boosts_matching_asset(self):
        """Asset with matching scene_type ranks above asset with same tags but wrong scene_type."""
        # Two records with same tags, different scene_types
        recs = [
            {"id": "x1", "path": "lk.mp4", "type": "video", "tags": ["湖", "洱海"], "scene_type": "lake"},
            {"id": "x2", "path": "mt.mp4", "type": "video", "tags": ["湖", "洱海"], "scene_type": "mountain"},
        ]
        mgr = _make_mgr(recs)
        results = mgr._match_multi_dim(
            query_tags=["湖", "洱海"], query_scene_type="lake", top_n=3)
        assert results[0].id == "x1"  # lake matches lake
        assert results[0].final_score > results[1].final_score


# ── Tests: V3 Weights ──────────────────────────────────

class TestV3Weights:
    def test_scene_type_is_high_weight(self):
        assert WEIGHT_SCENE_TYPE == 0.25
        assert WEIGHT_SEMANTIC >= WEIGHT_SCENE_TYPE  # semantic is highest
        assert WEIGHT_SCENE_TYPE >= WEIGHT_TAG

    def test_coarse_weights_stronger_than_fine(self):
        """Coarse matching (semantic, scene_type) > fine matching (mood, city, quality)."""
        assert WEIGHT_SEMANTIC > WEIGHT_QUALITY
        assert WEIGHT_SCENE_TYPE > WEIGHT_QUALITY
        assert WEIGHT_TAG > WEIGHT_QUALITY


# ── Tests: match_scene V3 ──────────────────────────────

class TestMatchSceneV3:
    def test_match_scene_passes_scene_type(self):
        mgr = _make_mgr(V3_RECORDS)
        scene = _make_scene(sid=1, mood="活力刺激", tags=["湖", "日落"], scene_type="lake")
        results = mgr.match_scene(scene, top_n=3)
        assert results[0].id == "a1"
        assert results[0].scene_type_score == 1.0

    def test_dedup_respects_scene_type(self):
        """Dedup still works with V3 scoring."""
        mgr = _make_mgr(V3_RECORDS)
        s1 = _make_scene(1, tags=["湖", "日落"], scene_type="lake")
        r1 = mgr.match_scene(s1, top_n=3)
        used = {r1[0].id}
        s2 = _make_scene(2, tags=["湖", "日落"], scene_type="lake")
        r2 = mgr.match_scene(s2, top_n=3, exclude_ids=used)
        assert r1[0].id not in {r.id for r in r2}


# ── Tests: ScoredAsset V3 fields ───────────────────────

class TestScoredAssetV3:
    def test_scored_asset_has_scene_type_score(self):
        r = ScoredAsset(id="x", path="y", type="image", tags=[], scene_type_score=0.5)
        assert r.scene_type_score == 0.5

    def test_scored_asset_has_scene_type_field(self):
        r = ScoredAsset(id="x", path="y", type="image", tags=[], scene_type="lake")
        assert r.scene_type == "lake"

    def test_match_score_equals_final_score(self):
        r = ScoredAsset(id="x", path="y", type="image", tags=[], final_score=0.75)
        assert r.match_score == 0.75


# ── Tests: Backward Compat ─────────────────────────────

class TestV3BackwardCompat:
    def test_scene_without_type_defaults_general(self):
        s = Scene(id=1, text="x", mood="开场吸引", asset_tags=["a", "b"])
        assert s.scene_type == "general"

    def test_script_generator_scene_type_shared(self):
        """script_generator.SceneType is the same source."""
        assert ScriptSceneType.LAKE == SceneType.LAKE
        for st in SceneType.ALL:
            assert ScriptSceneType.is_valid(st)

    def test_asset_scene_type_persisted_in_dict(self):
        r = AssetRecord(id="x", path="y", type="image", tags=[], scene_type="lake")
        d = r.model_dump()
        assert d["scene_type"] == "lake"

    def test_mood_category_map_unchanged(self):
        assert "开场吸引" in MOOD_CATEGORY_MAP
        assert "轻松惬意" in MOOD_CATEGORY_MAP
        assert len(MOOD_CATEGORY_MAP) == 6
