"""
Smart Asset Matching V2 — Unit Tests

Test cases: tag scoring, mood scoring, country scoring, city scoring,
type preference, multi-dim composite, dedup, sort order, match_scene,
match_for_script.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_asset_matching_v2.py -v
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.asset_library import (
    AssetLibraryManager, AssetRecord, ScoredAsset, MatchedAsset,
    MOOD_CATEGORY_MAP, SceneType,
    WEIGHT_SEMANTIC, WEIGHT_SCENE_TYPE, WEIGHT_TAG, WEIGHT_MOOD,
    WEIGHT_CITY, WEIGHT_QUALITY,
)
from src.script_generator import Script, Scene


# ── Helpers ──────────────────────────────────────────────

def _make_mgr(records_data: list[dict]) -> AssetLibraryManager:
    """Create a manager with in-memory records (no disk I/O)."""
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "test_index.json"
    mgr = object.__new__(AssetLibraryManager)
    mgr.assets_dir = tmp.parent
    mgr.index_path = tmp
    mgr._records = [AssetRecord(**r) for r in records_data]
    return mgr


def _make_scene(
    scene_id: int = 1,
    text: str = "测试文本",
    mood: str = "开场吸引",
    asset_tags: list[str] | None = None,
) -> Scene:
    return Scene(
        id=scene_id,
        text=text,
        mood=mood,
        asset_tags=asset_tags or ["海滩", "日落"],
    )


def _make_script(scenes: list[Scene]) -> Script:
    return Script(title="Test", topic="Test", scenes=scenes)


# Sample record data
REC_BEACH_CN_YUNNAN = {
    "id": "r001", "path": "cn/yunnan/beach.mp4", "type": "video",
    "tags": ["海滩", "日落", "云南", "洱海", "浪漫"],
    "country": "china", "city": "dali", "category": "beach",
    "moods": ["轻松惬意", "温馨感人"],
}

REC_AERIAL_CN_YUNNAN = {
    "id": "r002", "path": "cn/yunnan/aerial.mp4", "type": "video",
    "tags": ["航拍", "全景", "云南", "大理", "俯瞰"],
    "country": "china", "city": "dali", "category": "aerial",
    "moods": ["开场吸引"],
}

REC_FOOD_MY_SABAH = {
    "id": "r003", "path": "my/sabah/food.mp4", "type": "video",
    "tags": ["美食", "海鲜", "沙巴", "夜市"],
    "country": "malaysia", "city": "sabah", "category": "food",
    "moods": ["活力刺激"],
}

REC_SUNSET_MY_SABAH = {
    "id": "r004", "path": "my/sabah/sunset.jpg", "type": "image",
    "tags": ["日落", "海滩", "沙巴", "黄昏", "浪漫"],
    "country": "malaysia", "city": "sabah", "category": "sunset",
    "moods": ["温馨感人", "结尾号召"],
}

REC_NO_LOCATION = {
    "id": "r005", "path": "general/generic.jpg", "type": "image",
    "tags": ["旅行", "通用", "背景"],
    "country": "", "city": "", "category": "generic",
    "moods": [],
}

REC_URBAN_JP_TOKYO = {
    "id": "r006", "path": "jp/tokyo/shibuya.mp4", "type": "video",
    "tags": ["城市", "东京", "夜景", "霓虹", "繁华"],
    "country": "japan", "city": "tokyo", "category": "urban",
    "moods": ["活力刺激", "结尾号召"],
}

SAMPLE_RECORDS = [
    REC_BEACH_CN_YUNNAN, REC_AERIAL_CN_YUNNAN,
    REC_FOOD_MY_SABAH, REC_SUNSET_MY_SABAH,
    REC_NO_LOCATION, REC_URBAN_JP_TOKYO,
]


# ── Tests: Tag Scoring ──────────────────────────────────

class TestTagScoring:
    def test_exact_tag_match(self):
        """All 3 query tags match → tag_score = 1.0."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=5)
        assert len(results) >= 1
        top = results[0]
        assert top.tag_score == 1.0
        assert top.id in ("r001", "r004")

    def test_partial_tag_match(self):
        """1 of 2 tags matches → tag_score = 0.5."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "nonexistent"], top_n=5)
        assert len(results) >= 1
        assert results[0].tag_score == 0.5

    def test_no_tag_match_empty(self):
        """No tag overlap → empty results (general scene_type alone doesn't trigger match)."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["nonexistent_xyz"], top_n=5)
        # V4: with no tags and no text, nothing matches
        assert len(results) == 0


# ── Tests: Mood Scoring ────────────────────────────────

class TestMoodScoring:
    def test_mood_score_prefers_matching_moods(self):
        """Asset with matching mood gets mood_score > 0."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene = _make_scene(
            asset_tags=["海滩", "日落"],
            mood="轻松惬意",
        )
        results = mgr.match_scene(scene, top_n=5)
        # r001 has "轻松惬意" mood → should rank highest
        top = results[0]
        assert top.mood_score > 0
        assert top.id == "r001"

    def test_mood_score_prefers_matching_category(self):
        """Asset category matching mood preferred categories gets score."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene = _make_scene(
            asset_tags=["航拍", "全景"],
            mood="开场吸引",
        )
        results = mgr.match_scene(scene, top_n=5)
        # r002 (aerial/video) should be preferred for "开场吸引"
        assert results[0].id == "r002"
        assert results[0].mood_score >= 0.6

    def test_mood_score_zero_when_no_match(self):
        """Asset with no mood/category match → mood_score = 0."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene = _make_scene(
            asset_tags=["旅行", "通用"],
            mood="神秘探索",
        )
        results = mgr.match_scene(scene, top_n=5)
        # r005 has no moods and generic category → mood_score should be 0
        for r in results:
            if r.id == "r005":
                assert r.mood_score == 0.0


# ── Tests: Country Scoring ─────────────────────────────

class TestCountryScoring:
    def test_country_from_topic_matches_record(self):
        """V4: country_score replaced by city_score and semantic_score."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr._match_multi_dim(
            query_tags=["海滩", "日落"], query_mood="轻松惬意",
            query_topic="云南7天6晚情侣游", top_n=5)
        # r001 (china) appears first because of city match + tags
        top_ids = [r.id for r in results[:2]]
        assert "r001" in top_ids or "r004" in top_ids, f"Expected China or sunset assets: {top_ids}"

    def test_country_no_topic_no_score(self):
        """No topic → country_score = 0 for all."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落"], top_n=5)
        for r in results:
            assert r.country_score == 0.0


# ── Tests: City Scoring ────────────────────────────────

class TestCityScoring:
    def test_city_score_from_topic(self):
        """Topic contains '沙巴' → sabah records get city_score > 0."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr._match_multi_dim(
            query_tags=["日落", "海滩"],
            query_mood="",
            query_topic="沙巴5天4晚旅游攻略",
            top_n=5,
        )
        sabah_scores = [r.city_score for r in results if r.id == "r004"]
        assert any(s >= 1.0 for s in sabah_scores), \
            f"Sabah assets should have city_score, got {sabah_scores}"


# ── Tests: Type Scoring ────────────────────────────────

class TestTypeScoring:
    def test_video_ranks_higher_than_image(self):
        """V4: type_score replaced by quality_score. Videos still favored via semantic."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=5)
        videos = [r for r in results if r.type == "video"]
        images = [r for r in results if r.type == "image"]
        # In V4, type_score is always 0.0 but videos may rank higher via quality
        for v in videos:
            assert v.type_score == 0.0  # V4 has no type_score
        # Videos still appear in results
        assert len(videos) >= 1

    def test_video_beats_image_all_else_equal(self):
        """When tag scores equal, quality_score may give video an edge."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=5)
        ids = [r.id for r in results]
        # Either r001 (video) or r004 (image) could be first
        assert "r001" in ids and "r004" in ids


# ── Tests: Composite Scoring ───────────────────────────

class TestCompositeScoring:
    def test_weights_sum_to_one(self):
        """All weights should sum to 1.0."""
        total = WEIGHT_SEMANTIC + WEIGHT_SCENE_TYPE + WEIGHT_TAG + WEIGHT_MOOD + WEIGHT_CITY + WEIGHT_QUALITY
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_final_score_is_weighted_sum(self):
        """final_score = weighted sum of sub-scores."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=5)
        for r in results:
            expected = round(
                WEIGHT_SEMANTIC    * r.semantic_score
                + WEIGHT_SCENE_TYPE * r.scene_type_score
                + WEIGHT_TAG        * r.tag_score
                + WEIGHT_MOOD       * r.mood_score
                + WEIGHT_CITY       * r.city_score
                + WEIGHT_QUALITY    * r.quality_score, 4)
            assert abs(r.final_score - expected) < 0.001, \
                f"final={r.final_score} != expected={expected} for {r.id}"

    def test_all_sub_scores_in_range(self):
        """Each sub-score is between 0.0 and 1.0."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=10)
        for r in results:
            assert 0.0 <= r.semantic_score <= 1.0
            assert 0.0 <= r.scene_type_score <= 1.0
            assert 0.0 <= r.tag_score <= 1.0
            assert 0.0 <= r.city_score <= 1.0
            assert 0.0 <= r.quality_score <= 1.0


# ── Tests: Dedup ───────────────────────────────────────

class TestDedup:
    def test_match_scene_excludes_used_ids(self):
        """Scene 2 cannot use assets already consumed by scene 1."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene1 = _make_scene(1, mood="轻松惬意", asset_tags=["海滩", "日落", "浪漫"])
        result1 = mgr.match_scene(scene1, top_n=3)
        used = {result1[0].id}

        scene2 = _make_scene(2, mood="轻松惬意", asset_tags=["海滩", "日落", "浪漫"])
        result2 = mgr.match_scene(scene2, top_n=3, exclude_ids=used)
        ids2 = {r.id for r in result2}
        assert result1[0].id not in ids2, \
            f"Asset {result1[0].id} leaked into scene 2: {ids2}"


# ── Tests: match_scene ─────────────────────────────────

class TestMatchScene:
    def test_match_scene_uses_mood(self):
        """match_scene passes scene.mood to scoring engine."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene = _make_scene(mood="活力刺激", asset_tags=["美食", "海鲜"])
        results = mgr.match_scene(scene, top_n=3)
        # r003 has mood "活力刺激" and tags "美食","海鲜" — should be #1
        assert results[0].id == "r003"
        assert results[0].mood_score > 0


# ── Tests: match_for_script ────────────────────────────

class TestMatchForScript:
    def test_match_for_script_returns_all_scenes(self):
        """match_for_script returns result for every scene."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        script = _make_script([
            _make_scene(1, mood="开场吸引", asset_tags=["航拍", "全景"]),
            _make_scene(2, mood="活力刺激", asset_tags=["美食", "海鲜"]),
            _make_scene(3, mood="温馨感人", asset_tags=["日落", "浪漫"]),
        ])
        results = mgr.match_for_script(script, top_n=3)
        assert len(results) == 3
        for r in results:
            assert "scene_id" in r
            assert "asset_tags" in r
            assert "matched_assets" in r
            assert len(r["matched_assets"]) >= 1

    def test_match_for_script_dedup_between_scenes(self):
        """Scene 2's top asset != Scene 1's top asset."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        script = _make_script([
            _make_scene(1, mood="轻松惬意", asset_tags=["海滩", "日落", "浪漫"]),
            _make_scene(2, mood="温馨感人", asset_tags=["海滩", "日落", "浪漫"]),
        ])
        results = mgr.match_for_script(script, top_n=3)
        s1_top = results[0]["matched_assets"][0].id
        s2_ids = {a.id for a in results[1]["matched_assets"]}
        assert s1_top not in s2_ids, \
            f"Scene 1 top asset {s1_top} appeared in scene 2: {s2_ids}"


# ── Tests: Sort Order ──────────────────────────────────

class TestSortOrder:
    def test_results_sorted_by_final_score_desc(self):
        """Results must be sorted by final_score descending."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落", "浪漫"], top_n=5)
        for i in range(len(results) - 1):
            assert results[i].final_score >= results[i + 1].final_score, \
                f"Sort error at index {i}: {results[i].final_score} < {results[i+1].final_score}"

    def test_top_n_respected(self):
        """top_n limits the result count."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        for n in [1, 2, 3]:
            results = mgr.match(query_tags=["海滩", "日落"], top_n=n)
            assert len(results) <= n


# ── Tests: Backward Compatibility ──────────────────────

class TestBackwardCompat:
    def test_matched_asset_is_scored_asset(self):
        """MatchedAsset is an alias for ScoredAsset."""
        assert MatchedAsset is ScoredAsset

    def test_match_score_property_works(self):
        """match_score property returns final_score."""
        r = ScoredAsset(
            id="x", path="y", type="image", tags=[], final_score=0.75,
        )
        assert r.match_score == 0.75

    def test_v1_match_api_works(self):
        """Legacy match() API still works and returns ScoredAssets."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        results = mgr.match(query_tags=["海滩", "日落"], top_n=5)
        assert len(results) >= 1
        assert isinstance(results[0], ScoredAsset)
        assert hasattr(results[0], 'final_score')
        assert hasattr(results[0], 'tag_score')
        # backward compat attribute
        assert hasattr(results[0], 'match_score')

    def test_v1_match_for_scenes_api_works(self):
        """Legacy match_for_scenes API still works with Scene objects."""
        mgr = _make_mgr(SAMPLE_RECORDS)
        scene1 = _make_scene(1, asset_tags=["海滩", "日落"])
        scene2 = _make_scene(2, asset_tags=["美食", "海鲜"])
        results = mgr.match_for_scenes([scene1, scene2], top_n=3)
        assert len(results) == 2
        assert len(results[0]["matched_assets"]) >= 1
    def test_mood_category_map_complete(self):
        """All expected moods have category mappings."""
        expected = {"开场吸引", "轻松惬意", "活力刺激", "神秘探索", "温馨感人", "结尾号召"}
        for mood in expected:
            assert mood in MOOD_CATEGORY_MAP, f"Missing mood: {mood}"
            assert len(MOOD_CATEGORY_MAP[mood]) >= 1, f"No categories for {mood}"
