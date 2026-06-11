"""
AI Travel Video Factory — CLI 入口

用法:
    # 生成视频
    python main.py "沙巴5天4晚旅游攻略"

    # 指定风格
    python main.py "东京3天自由行" --style 快节奏

    # 素材管理
    python main.py --scan-assets
    python main.py --tag asset_001 --add "海滩,沙巴"
    python main.py --tag asset_001 --remove "海滩"
    python main.py --list-assets

    # 素材报告
    python main.py --asset-report

    # 指定输出目录
    python main.py "曼谷美食之旅" --output ./my_videos
"""

import argparse
import sys
from pathlib import Path

from src.config import init_config, ASSETS_DIR, ASSETS_INDEX
from src.asset_library import AssetLibraryManager
from src.asset_processor import AssetProcessor
from src.auto_tagger import AutoTagger
from src.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description="AI Travel Video Factory — 输入旅游主题，自动生成竖屏短视频"
    )

    parser.add_argument(
        "topic",
        nargs="?",
        help="旅游主题，如 \"沙巴5天4晚旅游攻略\"",
    )

    parser.add_argument(
        "--style",
        default="快节奏",
        choices=["快节奏", "舒缓", "文艺"],
        help="视频风格（默认：快节奏）",
    )

    parser.add_argument(
        "--output",
        default="./output",
        help="输出目录（默认：./output）",
    )

    # 素材管理子命令
    parser.add_argument(
        "--scan-assets",
        action="store_true",
        help="扫描 assets/ 目录，生成素材索引",
    )

    parser.add_argument(
        "--tag",
        help="素材 ID，配合 --add / --remove 使用",
    )

    parser.add_argument(
        "--add",
        help="添加标签（逗号分隔）",
    )

    parser.add_argument(
        "--remove",
        help="移除标签（逗号分隔）",
    )

    parser.add_argument(
        "--list-assets",
        action="store_true",
        help="列出所有素材",
    )

    parser.add_argument(
        "--asset-report",
        action="store_true",
        help="生成素材覆盖率报告",
    )

    parser.add_argument(
        "--voice",
        default="travel_female",
        choices=["travel_female", "travel_male", "story_female", "story_male", "energetic_female"],
        help="配音音色（默认：travel_female）",
    )

    parser.add_argument(
        "--process-assets",
        action="store_true",
        help="扫描 raw/ 目录，自动切镜头并生成缩略图",
    )

    parser.add_argument(
        "--auto-tag",
        action="store_true",
        help="使用 CLIP 模型自动为素材打标签",
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="生成 3 条不同主题的示范视频用于作品集展示",
    )

    parser.add_argument(
        "--batch-demo",
        type=int,
        default=0,
        metavar="N",
        help="批量生成 N 条不同主题视频，并输出 quality_report.json",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出详细日志",
    )

    args = parser.parse_args()

    # ── 初始化配置 ──────────────────────────────────
    config = init_config()

    # ── 素材管理模式 ────────────────────────────────
    mgr = AssetLibraryManager(assets_dir=ASSETS_DIR, index_path=ASSETS_INDEX)

    if args.scan_assets:
        print("[素材管理] 扫描素材目录...")
        records = mgr.scan_and_generate_index()
        print(f"[素材管理] [OK] 已生成 index.json ({len(records)} 个素材)")
        for r in records:
            tags_str = ", ".join(r.tags) if r.tags else "(无标签)"
            print(f"  {r.id}: {r.path} [{r.type}] "
                  f"{r.resolution} {tags_str}")
        return

    if args.asset_report:
        print("\n" + "=" * 60)
        print("  素材覆盖率报告")
        print("=" * 60 + "\n")
        report = mgr.generate_report()
        if "error" in report:
            print(report["error"])
            return
        s = report["summary"]
        print(f"  总计: {s['total']} 个素材")
        print(f"  视频: {s['videos']} 个 (总时长 {s['total_video_duration_sec']}s)")
        print(f"  图片: {s['images']} 个")
        print(f"  总大小: {s['total_size_kb']:,} KB")
        print(f"\n  按分类:")
        for cat, cnt in report.get("by_category", {}).items():
            bar = "█" * cnt
            print(f"    {cat:15s}: {bar} {cnt}")
        print(f"\n  按国家:")
        for ctr, cnt in report.get("by_country", {}).items():
            print(f"    {ctr:15s}: {cnt}")
        print(f"\n  按分辨率:")
        for res, cnt in report.get("by_resolution", {}).items():
            print(f"    {res:15s}: {cnt}")
        print(f"\n  Top 20 标签:")
        for tag, cnt in report["top_tags"]:
            print(f"    {tag:12s}: {cnt}")
        print(f"\n  唯一标签数: {report['total_unique_tags']}")
        print(f"  无标签素材: {report['untagged']}")
        return

    if args.process_assets:
        print("\n" + "=" * 60)
        print("  Asset Processor — 素材自动切镜头")
        print("=" * 60 + "\n")
        processor = AssetProcessor()
        records = processor.process_all()
        print(f"\n[OK] 处理完成，生成 {len(records)} 个新素材")
        print(f"[OK] index.json 已更新")
        return

    if args.auto_tag:
        print("\n" + "=" * 60)
        print("  Auto Tagger — CLIP 自动标注")
        print("=" * 60 + "\n")
        tagger = AutoTagger()
        count = tagger.tag_all()
        print(f"\n[OK] 标注完成，共更新 {count} 个素材")
        return

    if args.demo:
        print("\n" + "=" * 60)
        print("  Demo Mode — 生成 3 条作品集示范视频")
        print("=" * 60 + "\n")
        topics = [
            "云南7天6晚情侣游",
            "大理洱海骑行攻略",
            "香格里拉自由行",
        ]
        for i, topic in enumerate(topics, 1):
            print(f"\n{'#' * 60}")
            print(f"  Demo [{i}/3]: {topic}")
            print(f"{'#' * 60}")
            pipeline = Pipeline(config, output_dir=Path(args.output) / "temp", voice_profile=args.voice or "travel_female")
            result = pipeline.run(topic, style=args.style)
            print(f"\n[Demo {i}/3 OK] {result.final_video_path}")
        print(f"\n{'=' * 60}")
        print(f"  Demo 完成! 3 条视频已生成")
        print(f"  输出目录: {args.output}/temp/")
        print(f"{'=' * 60}")
        return

    if args.batch_demo > 0:
        import json as _json
        n = args.batch_demo
        print(f"\n{'=' * 60}")
        print(f"  Batch Demo — 批量生成 {n} 条测试视频")
        print(f"{'=' * 60}\n")

        all_topics = [
            "云南7天6晚情侣游", "大理洱海骑行攻略", "香格里拉自由行",
            "云南徒步路线", "丽江古城打卡攻略", "云南美食攻略",
            "玉龙雪山攻略", "云南摄影攻略", "云南小众玩法",
            "云南毕业旅行", "云南蜜月旅行", "大理自由行",
            "丽江自由行", "云南避坑指南", "云南包车攻略",
            "昆明周边游", "云南自驾游路线", "云南亲子游",
            "大理洱海一日游", "云南自由行攻略",
        ]
        topics = all_topics[:n]
        quality_report = []

        for i, topic in enumerate(topics, 1):
            entry = {
                "topic": topic,
                "generation_status": "pending",
                "error_message": None,
                "video_path": None,
                "used_assets_count": 0,
                "duplicate_asset_count": 0,
                "bgm_file": None,
                "subtitle_burned_in": False,
                "duration": 0,
            }
            try:
                print(f"\n[Batch {i}/{n}] {topic}")
                pipeline = Pipeline(config, output_dir=Path(args.output) / "temp", voice_profile=args.voice or "travel_female")
                result = pipeline.run(topic, style=args.style)
                entry["generation_status"] = "ok"
                entry["video_path"] = str(result.final_video_path)
                entry["duration"] = result.duration
                entry["file_size_mb"] = result.file_size_mb
                # Read metadata for detailed info
                try:
                    meta = _json.loads(result.metadata_path.read_text(encoding="utf-8"))
                    entry["used_assets_count"] = meta.get("unique_asset_count", 0)
                    entry["duplicate_asset_count"] = meta.get("duplicate_asset_count", 0)
                    entry["bgm_file"] = meta.get("bgm_file", None)
                    entry["subtitle_burned_in"] = meta.get("subtitle_burned_in", False)
                    # V4: include quality scores
                    if "quality_score" in meta:
                        entry["quality_score"] = meta["quality_score"]
                        entry["publish_recommendation"] = meta.get("publish_recommendation", "unknown")
                        entry["risk_flags"] = meta.get("risk_flags", [])
                        entry["improvement_suggestions"] = meta.get("improvement_suggestions", [])
                except Exception:
                    pass
                print(f"  [OK] {result.final_video_path}")
            except Exception as e:
                entry["generation_status"] = "failed"
                entry["error_message"] = str(e)[:200]
                print(f"  [FAIL] {e}")

            quality_report.append(entry)

        # Save report
        report_path = Path(args.output) / "quality_report.json"
        report_path.write_text(_json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8")
        ok_count = sum(1 for e in quality_report if e["generation_status"] == "ok")
        print(f"\n Batch Demo 完成!")
        print(f"  {ok_count}/{n} 成功")
        print(f"  Report: {report_path}")
        return

    if args.tag:
        if args.add:
            tags = [t.strip() for t in args.add.split(",")]
            mgr.add_tags(args.tag, tags)
            print(f"[素材管理] [OK] 为 {args.tag} 添加标签: {args.add}")
            return
        if args.remove:
            tags = [t.strip() for t in args.remove.split(",")]
            mgr.remove_tags(args.tag, tags)
            print(f"[素材管理] [OK] 从 {args.tag} 移除标签: {args.remove}")
            return

    if args.list_assets:
        assets = mgr.list_assets()
        print(f"\n素材列表 ({len(assets)} 个):\n")
        for a in assets:
            tags_str = ", ".join(a['tags']) if a['tags'] else "(无标签)"
            dur_str = f" {a['duration']}s" if a['duration'] else ""
            print(f"  {a['id']}: {a['path']}")
            print(f"         [{a['type']}] {a.get('category','')} {a.get('country','')} {tags_str}{dur_str}")
        return

    # ── 视频生成模式 ────────────────────────────────
    if not args.topic:
        parser.print_help()
        print("\n错误: 请提供旅游主题，例如: python main.py \"沙巴5天4晚旅游攻略\"")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  AI Travel Video Factory")
    print(f"  主题: {args.topic}")
    print(f"  风格: {args.style}")
    print(f"  音色: {args.voice}")
    print(f"{'='*50}\n")

    pipeline = Pipeline(config, output_dir=Path(args.output) / "temp", voice_profile=args.voice)
    result = pipeline.run(args.topic, args.style)
    print(f"\n[OK] 视频生成完成: {result.final_video_path}")
    print(f"[OK] 字幕: {result.subtitle_path}")
    print(f"[OK] 元数据: {result.metadata_path}")


if __name__ == "__main__":
    main()
