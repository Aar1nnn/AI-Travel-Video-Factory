#!/usr/bin/env python3
"""Batch video generation script — generates 20 test videos for quality assessment."""
import sys, io, os, json, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import init_config
from src.pipeline import Pipeline

TOPICS = [
    "云南7天6晚情侣游",
    "云南自由行攻略",
    "云南毕业旅行",
    "云南亲子游",
    "云南蜜月旅行",
    "大理自由行",
    "丽江自由行",
    "洱海骑行攻略",
    "玉龙雪山攻略",
    "云南避坑指南",
    "云南包车攻略",
    "云南美食攻略",
    "云南摄影攻略",
    "云南小众玩法",
    "云南徒步路线",
    "大理洱海一日游",
    "丽江古城打卡攻略",
    "香格里拉自由行",
    "昆明周边游",
    "云南自驾游路线",
]

RESULTS_FILE = Path("output/batch_results.json")
config = init_config()
pipeline = Pipeline(config, output_dir=Path("output/temp"))

results = []
for i, topic in enumerate(TOPICS, 1):
    print(f"\n{'='*60}")
    print(f"  [{i}/20] {topic}")
    print(f"{'='*60}")
    try:
        result = pipeline.run(topic, style="快节奏")
        rec = {
            "index": i,
            "topic": topic,
            "duration": result.duration,
            "scene_count": result.scene_count,
            "asset_count": result.asset_count,
            "file_size_mb": result.file_size_mb,
            "status": "OK",
        }
        print(f"  [OK] {result.duration:.1f}s, {result.scene_count} scenes, {result.asset_count} assets")
    except Exception as e:
        rec = {"index": i, "topic": topic, "status": "FAILED", "error": str(e)}
        print(f"  [FAIL] {e}")
    results.append(rec)
    time.sleep(2)  # Rate limit

Path("output").mkdir(exist_ok=True)
json.dump(results, open(RESULTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nResults saved to {RESULTS_FILE}")
print(f"Success: {sum(1 for r in results if r['status']=='OK')}/{len(results)}")
