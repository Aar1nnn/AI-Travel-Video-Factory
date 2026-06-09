"""
Asset Library Manager — Unit Tests

Test cases: exact match, partial match, no match, top-N, adjacent dedup,
match_for_scenes, exclude, empty query, reload.

Usage:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    .venv/Scripts/python.exe -m pytest tests/test_asset_library.py -v
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.asset_library import (
    AssetLibraryManager,
    AssetRecord,
    MatchedAsset,
)
from src.config import ASSETS_DIR, ASSETS_INDEX


# ── Fixtures ──────────────────────────────────────────

def _make_manager() -> AssetLibraryManager:
    """Create an AssetLibraryManager using the real assets/index.json."""
    return AssetLibraryManager(ASSETS_DIR, ASSETS_INDEX)


# Preload tags from real index to avoid encoding issues in source
def _get_sample_tags():
    """Extract a known set of tags from the real index for testing."""
    mgr = _make_manager()
    records = mgr.get_all_records()

    # asset_002 tags matched with beach/sabah queries
    tags_a002 = None
    # asset_005 tags matched with food queries
    tags_a005 = None
    # tags that don't exist
    fake_tags = None

    for r in records:
        if r.id == "asset_002":
            tags_a002 = list(r.tags)
        if r.id == "asset_005":
            tags_a005 = list(r.tags)

    # Pick 3 overlapping tags from asset_002 for strong query
    strong_query = tags_a002[:3] if tags_a002 else []

    # Pick 2 tags from asset_005 for food query
    food_query = tags_a005[:2] if tags_a005 else []

    # Use the first tag from asset_001 and first from asset_002 for partial
    r1 = records[0]
    r2 = records[1] if len(records) > 1 else records[0]
    partial_query = [r1.tags[0], r2.tags[0]]

    return {
        "strong_query": strong_query,
        "food_query": food_query,
        "partial_query": partial_query,
        "fake_query": ["nonexistent_tag_xyz"],
    }


# ── Test Cases ────────────────────────────────────────

def test_exact_match():
    """Query 3 tags from asset_002 → tag_score 1.0, top result is asset_002."""
    mgr = _make_manager()
    tags = _get_sample_tags()
    results = mgr.match(tags["strong_query"], top_n=5)

    assert len(results) >= 1, "Should find at least 1 matching asset"
    top = results[0]
    assert top.tag_score == 1.0, f"Expected tag_score 1.0, got {top.tag_score}"
    assert top.id == "asset_002"


def test_partial_match():
    """Query one tag from asset_001 + one from asset_002 → both tag_score 0.5."""
    mgr = _make_manager()
    tags = _get_sample_tags()
    results = mgr.match(tags["partial_query"], top_n=5)

    assert len(results) >= 1, "Should find at least 1 matching asset"
    top = results[0]
    assert top.tag_score == 0.5
    assert top.id in ("asset_001", "asset_002")


def test_no_match():
    """Query non-existent tag → empty result (V4: general scene_type alone no longer matches)."""
    mgr = _make_manager()
    tags = _get_sample_tags()
    results = mgr.match(tags["fake_query"], top_n=5)
    # V4: with no tags, no text, and general scene_type, nothing triggers.
    # This is a deliberate V4 behavior change from V3.
    assert len(results) == 0, (
        f"Expected 0 results for fake query, got {len(results)}. "
        "V4 only matches when tags, text, or non-general scene_type is present."
    )


def test_top_n():
    """Query → at most top_n results, sorted by final_score desc."""
    mgr = _make_manager()
    tags = _get_sample_tags()
    results = mgr.match(tags["strong_query"], top_n=2)

    assert len(results) <= 2
    assert results[0].final_score >= results[-1].final_score


def test_adjacent_dedup():
    """Scene 1 consumes best asset → scene 2 must not include it."""
    mgr = _make_manager()
    tags = _get_sample_tags()

    scene1 = mgr.match(tags["strong_query"], top_n=3)
    used = {a.id for a in scene1}

    scene2 = mgr.match(tags["strong_query"], top_n=3, exclude_ids=used)

    scene2_ids = {a.id for a in scene2}
    assert "asset_002" not in scene2_ids, (
        f"asset_002 reappeared! scene1 used={used}, scene2={scene2_ids}"
    )


def test_match_for_scenes():
    """Batch match: 2 scenes same query → best asset excluded from scene 2."""
    mgr = _make_manager()
    tags = _get_sample_tags()

    class MockScene:
        def __init__(self, sid, tags_arg):
            self.id = sid
            self.asset_tags = tags_arg

    scenes = [
        MockScene(1, tags["strong_query"]),
        MockScene(2, tags["strong_query"]),  # same tags, best asset excluded
    ]

    results = mgr.match_for_scenes(scenes, top_n=3)

    assert len(results) == 2

    # Scene 1 should have matches
    assert len(results[0]["matched_assets"]) >= 1
    assert results[0]["matched_assets"][0].final_score > 0

    # Scene 1 top-1 must not appear in Scene 2
    top1_id = results[0]["matched_assets"][0].id
    scene2_ids = {a.id for a in results[1]["matched_assets"]}
    assert top1_id not in scene2_ids, (
        f"Scene 1 top asset {top1_id} leaked into scene 2: {scene2_ids}"
    )


def test_match_for_scenes_food():
    """Scene with food tags should get matches (no dedup interference)."""
    mgr = _make_manager()
    tags = _get_sample_tags()

    class MockScene:
        def __init__(self, sid, tags_arg):
            self.id = sid
            self.asset_tags = tags_arg

    # Isolated food scene — no prior dedup
    results = mgr.match_for_scenes(
        [MockScene(1, tags["food_query"])],
        top_n=3,
    )

    assert len(results) == 1
    assert len(results[0]["matched_assets"]) >= 1
    assert results[0]["matched_assets"][0].id == "asset_005"


def test_exclude_empty():
    """exclude_ids=None → no crash; exclude_ids=set → filter applied."""
    mgr = _make_manager()
    tags = _get_sample_tags()

    results_none = mgr.match(tags["strong_query"], top_n=5, exclude_ids=None)
    assert len(results_none) >= 1

    with_exclude = mgr.match(tags["strong_query"], top_n=5, exclude_ids={"asset_002"})
    without_exclude = mgr.match(tags["strong_query"], top_n=5)

    assert "asset_002" in {a.id for a in without_exclude}
    assert "asset_002" not in {a.id for a in with_exclude}


def test_empty_query_tags():
    """Empty query → empty result."""
    mgr = _make_manager()
    results = mgr.match([], top_n=5)
    assert len(results) == 0


def test_reload():
    """reload() should not change count with unchanged index.json."""
    mgr = _make_manager()
    before = len(mgr.get_all_records())
    assert before == 7

    mgr.reload()
    after = len(mgr.get_all_records())
    assert before == after


# ── Main ───────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Asset Library Manager — Unit Tests")
    print("=" * 60)

    tests = [
        ("Exact match (score 1.0)", test_exact_match),
        ("Partial match (score 0.5)", test_partial_match),
        ("No match (empty result)", test_no_match),
        ("Top-N ordering", test_top_n),
        ("Adjacent scene dedup", test_adjacent_dedup),
        ("Batch match_for_scenes", test_match_for_scenes),
        ("Food scene isolated", test_match_for_scenes_food),
        ("Exclude param behavior", test_exclude_empty),
        ("Empty query tags", test_empty_query_tags),
        ("Reload index", test_reload),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)
