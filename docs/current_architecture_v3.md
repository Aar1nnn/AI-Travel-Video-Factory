# AI Travel Video Factory — V3 当前架构

**日期**: 2026-06-09

---

## 1. 入口

**文件**: `main.py`

```
python main.py "云南7天6晚情侣游" --voice travel_female
```

### main.py 逻辑

```
parse_args()
  ├── --scan-assets     → AssetLibraryManager.scan_and_generate_index()
  ├── --asset-report    → AssetLibraryManager.generate_report()
  ├── --auto-tag        → AutoTagger.tag_all()
  ├── --process-assets  → AssetProcessor.process_all()
  ├── --demo            → Pipeline.run() × 3
  ├── --batch-demo N    → Pipeline.run() × N → quality_report.json
  ├── --tag/--add/--remove → AssetLibraryManager tag management
  └── <topic>           → Pipeline.run(topic, style) → final video
```

---

## 2. Pipeline 执行顺序

**文件**: `src/pipeline.py` — `Pipeline.run(topic, style)`

```
Step 1: Script Generator
  输入: topic, style
  输出: script.json (Script object)
  文件: src/script_generator.py

Step 2: Asset Library Manager
  输入: script.scenes
  输出: script_with_assets.json (scenes + matched assets)
  文件: src/asset_library.py

Step 3: Voice Generator
  输入: script.scenes
  输出: voice.mp3 (per-scene TTS → FFmpeg concat)
  文件: src/voice_generator.py

Step 4: Subtitle Generator
  输入: voice.mp3
  输出: subtitles.srt
  文件: src/subtitle_generator.py

Step 5: Video Composer V3
  输入: script_with_assets + voice.mp3 + subtitles.srt + BGM
  输出: composed_video.mp4 (with ASS burn-in + BGM + fade)
  文件: src/video_composer.py

Step 6: Exporter
  输入: composed_video.mp4 + metadata
  输出:  {topic}_{date}.mp4, .json, .srt, _script.json, _used_assets.json
  文件: src/exporter.py
```

---

## 3. 各模块输入输出

| 模块 | 输入 | 输出 | 文件 |
|------|------|------|------|
| Script Generator | topic, style | Script(scenes, title) | script.json |
| Asset Library | Script.scenes | [{scene_id, matched_assets}] | script_with_assets.json |
| Voice Generator | Script.scenes | voice.mp3 | voice.mp3 |
| Subtitle Generator | voice.mp3 | subtitles.srt | subtitles.srt |
| Video Composer V3 | scene_assets + voice + srt + bgm | composed_video.mp4 | composed_video.mp4 |
| Exporter | composed_video + metadata | {topic}_{date}.mp4 + .json + .srt | output/temp/ |

---

## 4. 中间文件 (output/temp/)

```
output/temp/
├── script.json                    # Step 1 输出
├── script_with_assets.json        # Step 2 输出
├── scene_1.mp3 ~ scene_6.mp3      # Step 3 per-scene TTS fragments
├── voice.mp3                      # Step 3 final merged voice
├── concat_voice_list.txt          # Step 3 FFmpeg concat list
├── clip_vid_0000.mp4 ~ ...        # Step 5 per-asset processed clips
├── clip_img_0000.mp4 ~ ...        # Step 5 image-to-video clips
├── concat_list.txt                # Step 5 clip concat list
├── concat_video.mp4               # Step 5 pre-final video
├── subtitles.srt                  # Step 4 output
├── subtitles.ass                  # Step 5 generated from SRT
├── composed_video.mp4             # Step 5 final assembled
├── {topic}_{date}.mp4             # Step 6 exported final
├── {topic}_{date}.json            # Step 6 metadata
├── {topic}_{date}.srt             # Step 6 subtitle copy
├── {topic}_{date}_script.json     # Step 6 script copy
└── {topic}_{date}_used_assets.json # Step 6 asset usage copy
```

---

## 5. Video Composer V3 职责

**文件**: `src/video_composer.py`

### compose()
1. ffprobe voice.mp3 → duration
2. 按字数比例分配 scene_duration
3. 处理每个asset: image→clip, video→clip (1080×1920 crop + fade in/out)
4. concat clips → concat_video.mp4
5. _final_render():
   - BGM: [bgm]volume=0.15, afade=in:1.0:out:2.0
   - Voice + BGM: amix=inputs=2:duration=first
   - Subtitle: SRT→ASS→subtitles filter→burn into video
   - Output: composed_video.mp4 (H.264 + AAC)

### 字幕流程
```
subtitles.srt
  → _srt_to_ass() 
  → TikTok-style: Arial 48pt, white, black outline 4px, bottom center
  → FFmpeg subtitles='path/to/subtitles.ass' filter
  → burned into video frame
```

### BGM流程
```
VideoComposer.find_bgm()
  → scan bgm/*.mp3,*.wav
  → if found: random.choice(), print "[BGM] 使用: xxx.mp3"
  → if not found: print "[WARNING] no real BGM", return bgm_name="no_real_bgm"
  → _final_render: bgm volume=0.15, fade in 1s, fade out 2s
```

### 素材去重
```
compose():
  used_asset_ids = set()
  for each asset:
    aid = Path(asset["path"]).stem
    if aid in used_asset_ids → duplicate_count++
    used_asset_ids.add(aid)
  → metadata.duplicate_asset_count, metadata.unique_asset_count
```

---

## 6. quality_report.json 生成流程

```
main.py --batch-demo N
  ├── 读取 topics 列表 (top N)
  ├── for each topic:
  │   ├── Pipeline.run(topic)
  │   ├── 成功: generation_status="ok", 读取metadata字段
  │   └── 失败: generation_status="failed", error_message
  └── write quality_report.json (list of entries)
```

---

## 7. 当前风险点

| # | 风险 | 位置 | 影响 |
|---|------|------|------|
| 1 | ASS字幕路径转义 | video_composer.py:231 | FFmpeg Windows路径解析可能在不同环境失败 |
| 2 | 61%素材为general scene_type | index.json | 匹配质量差, 大量fallback |
| 3 | 非git仓库 | 整个项目 | 无法回滚, 无法打tag, 无版本历史 |
| 4 | 字幕繁体 | subtitle_generator.py | 输出繁体中文, 影响观看体验 |
| 5 | 测试用index.json不一致 | tests/ vs assets/ | test用7条, 生产用46条, 需手动切换 |
| 6 | batch_demo无速率限制 | main.py | 连续调用DeepSeek API可能触发限流 |
| 7 | BGM都是静默/测试文件 | bgm/ | 真实旅游配乐不足 |

---

## 8. 最容易被破坏的地方

1. **video_composer.py `_final_render()`** — 字幕路径 + BGM filter_complex 高度耦合
2. **pipeline.py `_build_script_with_assets()`** — MatchedAsset/ScoredAsset 转型安全
3. **asset_library.py `_match_multi_dim()`** — V4权重调整影响所有匹配
4. **main.py `--batch-demo`** — 依赖 Pipeline.run() 的 metadata 字段格式
