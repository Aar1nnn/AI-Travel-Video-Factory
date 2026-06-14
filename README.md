# AI Travel Video Factory

输入旅游主题，自动生成带脚本、配音、字幕、BGM 的竖屏旅游短视频。

> **本项目仅用于作品集展示，未经许可不得商用。**

## Demo 运行

```bash
# 单条视频
python main.py "云南7天6晚情侣游" --voice travel_female

# 批量生成质量验证
python main.py --batch-demo 20

# Streamlit Dashboard (推荐)
streamlit run app.py
# 或双击: run_dashboard.bat
```

## Streamlit Dashboard

```bash
streamlit run app.py
```

Dashboard 包含三个页面：

| 页面 | 功能 |
|------|------|
| 🎬 视频生成工作台 | 输入主题 → 生成视频 → KPI 仪表板 → 下载 |
| ✂️ 长视频切片工作台 | 上传长视频 → 镜头检测 → 切片 → 缩略图 |
| 🗂️ 素材库浏览器 | 浏览/筛选/检查素材库，标签云，风险标记 |

## 核心功能

- LLM 生成口语化短视频脚本 (DeepSeek) + 强Hook策略
- 自动分镜 (scene_type + mood + 标签)
- 智能素材匹配 (CLIP语义搜索 V4 + 多维度打分 + 去重)
- Per-scene Edge TTS 配音 (支持 mood 调整语速)
- Whisper 语音识别 → SRT → ASS 字幕烧录 (TikTok 风格)
- 真实 BGM 接入 (随机选择, 音量淡入淡出, 自动过滤静默)
- FFmpeg 渲染 (1080×1920 竖屏, H.264+AAC, fade transition)
- 自动化素材处理 (PySceneDetect 镜头检测 + 分割 + 缩略图)
- CLIP Auto-Tagger (零样本场景分类 + 标签生成)
- Quality Scorer (7 维度 100 分制)
- Batch Demo (批量生成 + quality_report.json)

## 技术架构

```
用户输入 (旅游主题)
  → Script Generator (DeepSeek LLM + Strong Hook Prompt)
  → Asset Matcher (CLIP semantic V4 + scene_type + tag + mood + dedup)
  → Voice Generator (Edge TTS per-scene + mood adjust)
  → Subtitle Generator (Whisper → SRT → ASS burn-in)
  → Video Composer (FFmpeg: crop+scale, concat, BGM, subtitle)
  → Quality Scorer (7-dimension 100-pt scoring)
  → output/ (视频 + 元数据 + 质量报告)
```

## Pipeline 流程

```
[1/6] Script Generator    → script.json
[2/6] Asset Matching      → script_with_assets.json (dedup enforced)
[3/6] Voice Generator     → voice.mp3 (per-scene TTS → merged)
[4/6] Subtitle Generator  → subtitles.srt
[5/6] Video Composer      → composed_video.mp4 (BGM + ASS + fade)
[6/6] Exporter            → {topic}_{date}.mp4 + metadata
[7/7] Quality Scorer      → quality_report.json (100分制)
```

## Batch 20 质量验证 (2026-06-09)

| 指标 | 数值 |
|------|------|
| 成功率 | 20/20 (100%) |
| 平均分 | 85.1/100 |
| recommended | 20/20 (100%) |
| 平均重复素材 | 2.2 |
| 静默BGM | 0/20 (已过滤) |
| 字幕烧录 | 20/20 |
| Hook 强度 | "避坑" "别再" "省钱" |

### Top 3

| # | 视频 | 评分 | 时长 | 大小 |
|---|------|------|------|------|
| 1 | 大理洱海一日游 | 90 | 27s | 11.2 MB |
| 2 | 云南避坑指南 | 89 | 36s | 9.5 MB |
| 3 | 丽江古城打卡攻略 | 88 | 23s | 7.8 MB |

## 技术栈

- LLM: DeepSeek API
- 图像理解: CLIP ViT-B-32 (open_clip_torch)
- TTS: Microsoft Edge TTS
- ASR: Whisper base
- 视频: FFmpeg 8.1.1
- 镜头检测: PySceneDetect
- 语言: Python 3.14

## 当前限制

- 素材库仅含云南4K航拍，缺美食/人文/夜景等素材类型
- 当前字幕基于 Whisper base，中文转写偶尔出现繁体字和时间轴偏移；后续计划接入 WhisperX 进行强制对齐和简体化处理
- Quality Scorer 为启发式规则，后续计划引入 LLM 自动化评分
- 当前提供 Streamlit 本地 Demo UI，暂未提供完整 SaaS Web 前端

## 项目结构

```
├── src/                     # 13 个模块
├── assets/                  # 本地素材库 (raw/ + processed/ + thumbnails/)
├── bgm/                     # BGM 音乐库
├── prompts/                 # LLM Prompt 模板
├── config/                  # 配置文件
├── tests/                   # 测试 (200+)
├── docs/                    # 文档 (17篇)
├── experiments/             # 实验 (6个)
├── output/                  # 输出目录
│   ├── temp/                # 临时文件
│   └── portfolio/           # 作品集
├── main.py                  # CLI 入口
├── app.py                   # Streamlit Demo UI
└── README.md
```

## 许可

本项目仅用于作品集展示，未经许可不得商用。
