# AI Travel Video Factory — 商业化前现状盘点

**审计日期**: 2026-06-15
**审计分支**: `v4-quality-scorer` (⚠️ main 分支只有 README，完整项目在 v4-quality-scorer)
**代码规模**: ~5400 行 Python, 216 个测试

---

## 一、仓库状态检查

| 检查项 | 结果 |
|--------|------|
| 当前分支 | `v4-quality-scorer` |
| remote 分支 | `origin/main`, `origin/v4-quality-scorer` |
| 本地分支 | `master`, `v4-quality-scorer` |
| 工作区 | clean（除 assets/index.json 外无未提交修改） |
| 最新 commit | `e99b621` (fix path normalization) |
| v4-quality-scorer commits | 12 个(从 v3 stable tag 起) |

**根目录文件**:
- `main.py` — CLI 入口
- `app.py` — Streamlit Dashboard 入口（新版多页）
- `legacy_app.py` — 旧版单页 UI（备份）
- `batch_generate.py` — 批量生成脚本
- `requirements.txt`, `README.md`, `PROJECT_SUMMARY.md`
- `run_dashboard.bat` — Windows 一键启动

**`src/` 模块（13 个）**:
- `script_generator.py` — DeepSeek LLM 脚本生成
- `asset_library.py` — 素材库管理 + CLIP V4 语义匹配
- `asset_processor.py` — PySceneDetect 镜头切分 + 缩略图
- `auto_tagger.py` — CLIP 零样本自动标签
- `voice_generator.py` — Edge TTS per-scene 配音
- `subtitle_generator.py` — Whisper 转录 → SRT
- `video_composer.py` — FFmpeg 合成 + ASS 字幕烧录 + BGM 混音
- `pipeline.py` — 6 步管线编排 + 去重 + Quality Scorer
- `quality_scorer.py` — 7 维度 100 分制质量评分
- `exporter.py` — 文件导出 + 重命名
- `config.py` — YAML + .env 配置聚合
- `utils.py` — JSON/日志/目录工具

**`tests/` 测试（11 个文件, 216 个测试）**:
- test_asset_library: 10, test_asset_matching_v2: 25
- test_asset_processor: 22, test_asset_processor_v2: 23
- test_auto_tagger: 26, test_pipeline: 14
- test_scene_understanding: 28, test_script_generator: 12
- test_semantic_search: 19, test_video_composer: 15
- test_voice_generator: 22

**`docs/` 文档（19 篇）**: 涵盖架构、变更日志、素材标准、实验规则、Provider 设计等。

**`prompts/`**: 只有 `script_generation.txt`（强 Hook 策略）

---

## 二、当前功能完整盘点

### 用户可感知功能

| 功能 | 入口 | 状态 |
|------|------|------|
| 🎬 输入旅游主题生成竖屏短视频 | `main.py`, Streamlit Page 1 | ✅ 可运行 |
| 📝 AI 生成口语化脚本(强 Hook) | DeepSeek LLM + Prompt 模板 | ✅ 可运行 |
| 🎞️ 自动分镜 (scene_type/mood/tags) | LLM 输出 + Pydantic 校验 | ✅ 可运行 |
| 🖼️ 自动素材匹配 | CLIP V4 语义搜索 + 标签 + 去重 | ✅ 可运行 |
| 🎙️ 自动配音 | Edge TTS per-scene + mood 调整语速 | ✅ 可运行 |
| 📝 自动字幕 | Whisper base → SRT → ASS 烧录 | ✅ 可运行 |
| 🎵 自动 BGM | 随机选择 + 音量 15% + fade in/out | ✅ 可运行 |
| 📊 质量评分 (100 分制) | Quality Scorer 7 维度 | ✅ 可运行 |
| 📦 批量生成 | `--batch-demo 20` | ✅ 可运行 |
| 🖥️ Streamlit Dashboard | `app.py` (3 页) | ✅ 可运行 |
| 🔊 配音试听 | Dashboard Page 1 | ✅ 可运行 |
| ✂️ 长视频切片 | Dashboard Page 2 (上传 + 镜头检测) | ⚠️ 部分可用 |
| 🗂️ 素材库浏览器 | Dashboard Page 3 (筛选 + 卡片网格) | ✅ 可运行 |
| 📥 下载视频 | Dashboard Page 1 | ✅ 可运行 |
| 📄 作品集输出 | `output/portfolio/` | ✅ 可运行 |

### 底层技术功能

| 功能 | 模块 | 状态 |
|------|------|------|
| DeepSeek LLM 调用 | `script_generator.py` (OpenAI SDK) | ✅ |
| Prompt 模板(强 Hook) | `prompts/script_generation.txt` | ✅ |
| scene_type 枚举(17 种) | `asset_library.py` `SceneType` | ✅ |
| mood 6 种 + rate 调整 | `voice_generator.py` `MOOD_RATE_ADJUSTMENTS` | ✅ |
| CLIP ViT-B-32 语义匹配 | `asset_library.py` V4 | ✅ |
| 素材去重(asset_id + source_video_id) | `pipeline.py` `_dedup_assets()` | ✅ |
| PySceneDetect 镜头切分 | `asset_processor.py` | ✅ |
| CLIP Auto-Tagger 零样本分类 | `auto_tagger.py` | ✅ |
| Edge TTS per-scene 配音 | `voice_generator.py` | ✅ |
| Whisper base 转录 | `subtitle_generator.py` | ✅ |
| SRT → ASS 字幕转换 | `video_composer.py` `_srt_to_ass()` | ✅ |
| ASS 字幕烧录(FFmpeg subtitles) | `video_composer.py` `_final_render()` | ✅ |
| BGM 过滤(排除静默/测试) | `video_composer.py` `find_bgm()` | ✅ |
| BGM 淡入淡出 + 音量混音 | `video_composer.py` `_final_render()` | ✅ |
| crossfade 过渡(fade in/out) | `video_composer.py` 各 clip | ✅ |
| FFmpeg 跨平台路径检测 | `shutil.which("ffmpeg")` | ✅ |
| Quality Scorer 7 维度评分 | `quality_scorer.py` | ✅ |
| Batch Demo 质量报告 | `main.py`, `output/quality_report.json` | ✅ |
| Streamlit 3 页 Dashboard | `app.py` + `pages/1/2/3_*.py` | ✅ |
| 中文 UI 本地化 | 全部页面 | ✅ |
| 配音预览(Edge TTS + 缓存) | `ui_components/shared.py` | ✅ |
| 外部路径自动复制到素材库 | `asset_processor.py` `_normalize_input_path()` | ✅ |
| .env 跨 CWD 加载 | `config.py` `find_dotenv(usecwd=True)` | ✅ |

---

## 三、完整 Pipeline 还原

```
用户输入主题 "云南7天6晚情侣游"
  ↓
[1/6] script_generator.py
  DeepSeek LLM 调用 → Script(scenes=[])
  → output/temp/script.json
  ↓
[2/6] asset_library.py + pipeline.py
  match_for_scenes() → _build_script_with_assets() → _filter_missing_assets() → _dedup_assets()
  → output/temp/script_with_assets.json
  ↓
[3/6] voice_generator.py
  per-scene Edge TTS → scene_1.mp3~scene_6.mp3 → FFmpeg concat
  → output/temp/voice.mp3
  ↓
[4/6] subtitle_generator.py
  Whisper base 转录 voice.mp3 → segments → SRT
  → output/temp/subtitles.srt
  ↓
[5/6] video_composer.py
  compose():
    - 素材 → clip_vid_XXXX.mp4 (1080×1920 crop + fade)
    - concat → concat_video.mp4
    - _final_render():
      - SRT → ASS (TikTok 样式)
      - BGM: 随机选择 → volume=0.15 → afade in/out
      - Voice + BGM: amix=inputs=2
      - ASS burn-in: subtitles filter
  → output/temp/composed_video.mp4 (H.264 + AAC)
  ↓
[6/6] exporter.py + pipeline.py
  copy + rename → output/temp/{topic}_{date}.mp4
  → output/temp/{topic}_{date}.json (metadata)
  → output/temp/{topic}_{date}.srt
  → output/temp/{topic}_{date}_script.json
  → output/temp/{topic}_{date}_used_assets.json
  ↓
[7/7] quality_scorer.py
  7 维度评分 → quality_report
  → output/temp/{topic}_{date}_quality.json
  metadata 增加 quality_score/publish_recommendation/risk_flags
```

### 实际中间文件

| 文件 | 生成方式 | 内容 |
|------|----------|------|
| `script.json` | Script.model_dump() | title, topic, scenes[] |
| `script_with_assets.json` | pipeline 拼接 | scenes 各带 assets[] |
| `scene_1.mp3~scene_6.mp3` | Edge TTS per-scene | 每段配音片段 |
| `voice.mp3` | FFmpeg concat | 完整配音 |
| `subtitles.srt` | Whisper → segments_to_srt | SRT 字幕 |
| `subtitles.ass` | _srt_to_ass() | TikTok 样式 ASS |
| `clip_vid_0000.mp4~...` | 素材 crop+scale+fade | 处理后的片段 |
| `concat_video.mp4` | FFmpeg concat | 无音频拼接视频 |
| `composed_video.mp4` | _final_render() | 含 BGM + 字幕的最终视频 |
| `{topic}_{date}.mp4` | exporter | 导出最终成品 |
| `{topic}_{date}.json` | exporter | 元数据含质量评分 |
| `quality_report.json` | batch_demo | 批量质量报告 |

---

## 四、真实成熟度评估 (0-10)

| 维度 | 评分 | 理由 |
|------|------|------|
| 作品集展示能力 | **8** | Streamlit Dashboard 专业, 3 页, 全中文, 视频+报告 |
| 自动化程度 | **7** | 输入主题到输出 MP4 全自动, 但素材库需人工维护 |
| 视频成片质量 | **4** | 素材库只有云南 4K 航拍, 全部 fallback 时只有占位图 |
| 稳定性 | **6** | batch 20/20 成功, 但 LLM 重试率高(~25%), 字幕繁体 |
| 可维护性 | **5** | ~5400 行合理, 但 13 个模块耦合在 pipeline.py |
| 可扩展性 | **4** | 无 Provider 接口, 无插件机制, 硬编码流程 |
| 商业化可用性 | **2** | 无可配置模板, 无客户管理, 无任务队列, 无部署方案 |
| 客户交付能力 | **1** | 只能本地运行, 无交付包, 无 API, 无多租户 |
| SaaS 化潜力 | **1** | 当前是单体 CLI + Desktop UI, 无任何 Web 服务化基础 |
| 代码工程质量 | **5** | 测试覆盖好(216 个), 但缺少类型标注, 部分硬编码路径历史残留 |

---

## 五、当前最大短板

### 产品定位

**问题**: 项目没有明确的产品定位。README 说"作品集展示，未经许可不得商用"。既不是开源项目，也不是商业产品，也不是 SaaS，卡在中国。

### 客户对象

**问题**: 没有定义目标客户。是为旅行社批量生成？还是给个人博主用？还是卖给 MCN？三个客群的需求完全不同。

### 素材质量

**问题**: 素材库只有云南 4K 航拍片段(94 个 clips, 全部 4K 横屏)。缺少美食、人文、夜景、室内、竖屏素材。大部分场景标签不匹配导致 fallback。

### 输入/输出标准化

**问题**: 输入只有 topic 一个字段。没有模板选择、时长控制、风格定制、品牌元素（Logo、水印、封面、片头片尾）。

### 稳定批量生成

batch 20/20 成功但是所有视频使用同一个 fallback 占位图, 实质不可交付。

### UI 给客户使用

Streamlit Dashboard 适合演示, 不适合客户日常使用。没有项目管理、历史记录、批量操作、导出管理。

### 缺失的系统能力

| 能力 | 状态 |
|------|------|
| 账号/认证 | ❌ 无 |
| 项目管理 | ❌ 无 |
| 任务队列 | ❌ 无 |
| 失败重试 | ⚠️ LLM 有 3 次重试, 其他步骤无 |
| 成本统计 | ❌ 无(DeepSeek API 调用次数/费用) |
| 日志和错误追踪 | ❌ 只有 print(), 无结构化日志 |
| 可配置模板 | ❌ 只有 1 个 Prompt |
| 人工微调入口 | ❌ 无(无法编辑脚本、替换素材) |
| 版权/商用风险 | ⚠️ 素材来自 Pexels/Unsplash, BGM 有版权 |
| 部署方案 | ❌ 无(仅本地 .venv + CLI) |

---

## 六、商业化前必须补齐的能力

### P0 — 必须马上补

| 功能 | 为什么 | 现有基础 | 预计难度 |
|------|--------|----------|----------|
| **素材库扩容** | 当前 61% general, 大量 fallback | `asset_processor.py` 可自动切镜头 | 中(需下载/购买素材) |
| **DirectSRTProvider** | 绕过 Whisper 繁体/错字问题 | `subtitle_generator.py` 已有 Whisper 流程 | 低(从 script.text 直接生成 SRT) |
| **faster-whisper 接入** | 提速 10x + word timestamps | `experiments/whisperx_test/REPORT.md` 已评估通过 | 低(API 几乎相同) |
| **模板系统** | 不能只有 1 个 Prompt | `prompts/` 只有 script_generation.txt | 中(需设计模板结构) |
| **BUG 修复** | subtitles 偶尔烧录失败路径 | `video_composer.py` ASS 路径处理 | 低 |

### P1 — 短期提升交付能力

| 功能 | 为什么 | 现有基础 | 预计难度 |
|------|--------|----------|----------|
| **Provider 接口** | 可换 LLM/TTS/ASR | `docs/provider_architecture_plan.md` 已设计 | 中(需重构 pipeline) |
| **多风格模板** | 情侣/亲子/美食/攻略 | Prompt 模板 + 可选 BGM/style | 中 |
| **视频预览 + 人工微调** | 客户需要修改脚本/替换素材 | Dashboard Page 1 有预览 | 中 |
| **输出交付包** | `{name}/final.mp4 + script + meta` | `exporter.py` 基础存在 | 低 |
| **部署文档** | 怎么能让别人跑起来 | 无 | 低 |

### P2 — SaaS 化

| 功能 | 为什么 | 现有基础 | 预计难度 |
|------|--------|----------|----------|
| **Web API** | FastAPI 封装 pipeline | 无 | 高 |
| **任务队列** | Celery/Redis | 无 | 高 |
| **用户管理** | 登录/注册/权限 | 无 | 高 |
| **项目管理** | 每个客户独立项目 | 无 | 中 |
| **计费系统** | 按条/按月 | 无 | 高 |

### P3 — 暂时不做

- 自动发布 TikTok/抖音
- AI 自动爬取素材
- 实时视频流
- 移动 App
- 社交功能/社区

---

## 七、《给 ChatGPT 的项目现状简报》

---

**项目名称**: AI Travel Video Factory
**GitHub**: Aar1nnn/AI-Travel-Video-Factory
**⚠️ 完整项目在 `v4-quality-scorer` 分支，main 分支只有 README**

### 1. 一句话定位
输入旅游主题，全自动生成带 AI 文案、配音、字幕、BGM 的竖屏旅游短视频。当前为作品集级别 MVP，可在本地运行 CLI + Streamlit Dashboard，尚未商业化部署。

### 2. 当前完整功能列表
- 🎬 输入旅游主题 → 自动生成 30s 左右竖屏短视频
- 📝 DeepSeek LLM 生成口语化脚本(强制 Hook 开头：避坑/省钱/千万别)
- 🎞️ 自动分镜：每场景有 scene_type(17 种)、mood(6 种)、asset_tags
- 🖼️ CLIP ViT-B-32 语义素材匹配 + 标签匹配 + 去重(同视频不重复)
- 🎙️ Edge TTS per-scene 配音(mood 自动调整语速), 5 种中文音色
- 📝 Whisper base 转录 → SRT → ASS 字幕烧录(白字黑边, TikTok 风格)
- 🎵 真实 BGM 随机选择, volume 15%, fade in/out, 自动过滤静默文件
- 📊 7 维度 100 分制质量评分(hook/文案/素材/字幕/BGM/节奏/商业)
- 📦 批量生成 20 条 + quality_report.json
- 🖥️ Streamlit 3 页 Dashboard (全中文 UI)：
  - Page 1: 视频生成工作台(含配音试听)
  - Page 2: 长视频切片工作台(上传 + 镜头检测)
  - Page 3: 素材库浏览器(KPI + 筛选 + 卡片网格 + 标签云)
- ✂️ PySceneDetect 自动镜头切分 → CLIP Auto-Tagger 自动打标签
- 🔧 FFmpeg 跨平台自动检测(不再硬编码路径)

### 3. 技术架构
- LLM: DeepSeek API (OpenAI SDK, 兼容)
- 图像理解: CLIP ViT-B-32 (open_clip_torch, 离线)
- TTS: Microsoft Edge TTS (免费, 本地)
- ASR: Whisper base (离线)
- 视频渲染: FFmpeg (concat + crop + subtitle + BGM mix)
- 镜头检测: PySceneDetect + OpenCV
- UI: Streamlit (3 页, 全中文)
- 代码: Python 3.14, ~5400 行, 216 个测试

### 4. 项目结构
```
├── main.py           # CLI 入口
├── app.py            # Streamlit Dashboard 入口
├── pages/            # 3 个 Dashboard 页面
├── ui_components/    # 可复用 UI 组件
├── src/              # 13 个模块
├── tests/            # 11 个测试文件(216 测试)
├── docs/             # 19 篇技术文档
├── config/           # YAML 配置 + voices.yaml
├── prompts/          # Prompt 模板
├── assets/           # 素材库(raw/processed/thumbnails/embeddings)
├── bgm/              # 背景音乐
├── experiments/      # 6 个技术实验(含 WhisperX 评估)
└── output/           # 生成输出(temp/portfolio)
```

### 5. 已验证数据
- batch-demo 20/20 成功(100%), 平均分 85.1/100, 全部 recommended
- 216/216 测试通过
- 最新 commit: e99b621 (2026-06-14)
- 素材库: 46 条记录(7 原始 + 39 自动处理), 94 个处理后的 clips 存在磁盘

### 6. 主要限制
- 素材库只有云南 4K 航拍, 缺美食/人文/夜景/竖屏素材
- 字幕为繁体中文(Whisper base 输出), 偶有错字和时轴偏移
- 无可配置模板, 只有 1 个 Prompt
- 无 Provider 接口(LM/TTS/ASR 硬编码)
- 无 Web API, 无任务队列, 无用户管理
- 只能本地运行, 无部署方案
- Quality Scorer 是启发式规则，不是 AI 模型

### 7. 建议的商业化方向
- **B2B 旅行社**: 批量生成目的地宣传短视频(标准化模板 + 批量交付)
- **B2C 旅游博主工具**: SaaS 订阅制, Web UI 生成+微调+下载
- **MCN 内容工厂**: API 批量生产, 多主题/多账号/多平台分发

### 8. 最不应该做的方向
- 自动发布 TikTok/抖音(不确定性和封号风险太高)
- AI 自动爬取素材(法律风险)
- 做社交平台/社区(和核心竞争力无关)

### 9. 下一阶段 3 条路线
1. **P0 补齐素材 + 修复字幕**: 素材库扩容 + DirectSRTProvider 绕过 Whisper
2. **P1 模板系统 + Provider 接口**: 多风格模板 + LLM/TTS/ASR 可替换
3. **P2 FastAPI Web 服务**: 把 pipeline 封装为 REST API, 接入前端或客户

### 10. 真实判断
这个项目离"能卖钱"还差：
1. 素材库(当前只有 1 个目的地的 4K 航拍)
2. 可交付的成片质量(大量场景用同一张占位图)
3. 模板系统(不是一个 Prompt 打天下)
4. 客户可用的界面(Streamlit 不适合客户用)
5. 部署能力(Docker/Cloud, 不能只在本地 .venv 跑)
6. 定价和商业模式(按条/按月/按客户?)
7. 版权合规(素材来源、BGM 授权)
