# AI Travel Video Factory — V3 变更报告

**日期**: 2026-06-09
**版本**: V3 (ASS + BGM + Batch Demo)
**前一版本**: V2 (subtitle burn-in, BGM test)

---

## 1. 修改文件清单

| 文件 | 变更类型 | 具体改动 |
|------|----------|----------|
| `src/video_composer.py` | **重写** | V2→V3: ASS字幕烧录格式, BGM真实文件支持, 素材去重跟踪 |
| `src/pipeline.py` | **修改** | BGM选择返回tuple, metadata新增unique/duplicate/bgm/subtitle_burned_in字段, 输出script和used_assets到output |
| `main.py` | **新增参数** | 新增 `--batch-demo N` 命令 |
| `bgm/` | **内容变更** | 新增真实BGM: leberch-travel, the_mountain-travel |
| `output/quality_report.json` | **新增输出** | 批量生成质量报告 |
| `tests/test_video_composer.py` | **修复** | 适配V3 API变更 |
| `experiments/whisperx_test/` | **新增实验** | WhisperX/faster-whisper评估 |

### 未修改的文件
- `src/asset_library.py` (V4 scoring engine untouched)
- `src/asset_processor.py` (V2 processor untouched)
- `src/auto_tagger.py` (V1 tagger untouched)
- `src/script_generator.py`
- `src/voice_generator.py`
- `src/subtitle_generator.py`
- `src/exporter.py`
- `src/config.py`

---

## 2. 新增 CLI 参数

```bash
# 批量生成 N 条视频并输出质量报告
python main.py --batch-demo 20

# 输出 → output/quality_report.json + output/temp/{topic}_{date}.mp4
```

保留已有参数:
- `python main.py "主题" --voice travel_female`
- `python main.py --demo`
- `python main.py --scan-assets`, `--auto-tag`, `--process-assets`

---

## 3. 新增输出字段 (metadata.json / quality_report.json)

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `used_assets` | list | pipeline | 使用的素材路径列表 |
| `unique_asset_count` | int | pipeline | 去重后的唯一素材数 |
| `duplicate_asset_count` | int | pipeline | 重复使用的素材数 |
| `bgm_file` | str | pipeline | 使用的BGM文件名, 无则为"no_real_bgm" |
| `subtitle_burned_in` | bool | pipeline | 是否内嵌ASS字幕 |
| `file_size_mb` | float | batch_demo | 视频文件大小(MB) |
| `generation_status` | str | batch_demo | "ok" / "failed" |
| `error_message` | str/null | batch_demo | 失败原因 |
| `video_path` | str | batch_demo | 视频文件路径 |

---

## 4. 当前运行方式

### 单条视频
```bash
cd d:/AI-Workspace/projects/ai-travel-video-factory
.venv/Scripts/python.exe main.py "云南7天6晚情侣游" --voice travel_female
```

### 批量视频
```bash
.venv/Scripts/python.exe main.py --batch-demo 20
```

### 输出位置
```
output/temp/{topic}_{date}.mp4       # 最终视频
output/temp/{topic}_{date}.json      # 元数据
output/temp/{topic}_{date}.srt       # 字幕文件
output/temp/{topic}_{date}_script.json       # 脚本
output/temp/{topic}_{date}_used_assets.json # 素材使用记录
output/quality_report.json           # 批量质量报告
```

---

## 5. V3 已具备能力

1. ✅ 文案生成 (DeepSeek LLM)
2. ✅ 分镜生成 (scene_type + mood + tags)
3. ✅ 素材匹配 (V4 semantic + scene_type + tag)
4. ✅ 素材去重统计 (duplicate_asset_count)
5. ✅ 配音生成 (Edge TTS + mood调整)
6. ✅ 字幕生成 (Whisper base → SRT → ASS)
7. ✅ ASS字幕烧录 (FFmpeg subtitles filter, TikTok样式)
8. ✅ BGM真实文件接入 (5首, 随机选择, volume 0.15, fade)
9. ✅ 基础转场 (fade in/out on each clip)
10. ✅ 批量生成 (--batch-demo N)
11. ✅ 质量报告 (quality_report.json)
12. ✅ 竖屏输出 (1080×1920, H.264 + AAC)

---

## 6. V3 已知风险

| 风险 | 严重度 | 说明 |
|------|--------|------|
| ASS字幕FFmpeg路径 | 低 | 单引号包裹路径, 当前可工作但不够鲁棒 |
| 素材库标签覆盖率 | 高 | 61%为general, 大量场景fallback |
| 字幕繁体问题 | 中 | Whisper model输出繁体, 需繁简转换 |
| 测试index.json不一致 | 低 | test用7条, 生产用46条, 需手动切换 |
| 非git仓库 | 中 | 无法回滚, 无法打tag |
| batch_demo无LLM重试上限 | 低 | 单条失败会继续, 但无明显速率限制 |

---

## 7. 主项目核心改动 vs 实验目录改动

### 主项目核心改动 (src/)
- `src/video_composer.py` — 字幕+ BGM+去重
- `src/pipeline.py` — metadata字段
- `main.py` — --batch-demo 命令
- `tests/test_video_composer.py` — 适配V3

### 实验目录改动 (experiments/)
- `experiments/whisperx_test/` — WhisperX评估, 不影响主项目
