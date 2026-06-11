# AI Travel Video Factory — 项目总结

## 项目背景

旅游短视频生产面临三个问题：
1. 手动剪辑耗时 (30-60分钟/条)
2. 素材库管理混乱
3. 内容质量不稳定

## 解决的问题

构建了一条完整的自动化生产线：
**输入旅游主题 → 自动生成脚本 → 匹配素材 → 配音 → 字幕 → BGM → 渲染 → 质量评分**

## 我的实现

### 技术难点

1. **素材语义匹配**: 传统 tag-overlap 命中率仅16%。引入 CLIP ViT-B-32 语义搜索 + 6 维加权打分，命中率提升到83%。

2. **自动化素材处理**: PySceneDetect 将11GB原始视频自动切分为94个独立片段，CLIP Auto-Tagger 自动标注 scene_type 和标签。

3. **TikTok 字幕烧录**: 从 Whisper SRT → ASS → FFmpeg subtitles filter，实现白字黑边底部居中字幕，100%成功率。

4. **质量评估体系**: 设计7维度100分制 Quality Scorer，包含 Hook 强度、素材匹配度、BGM 适配、商业可用性等。

5. **稳定性**: 20条批量生成，100%成功率。去重机制 + BGM过滤 + Prompt优化后，平均分从~70提升到85.1。

### 量化指标

| 指标 | Before | After |
|------|--------|-------|
| 素材命中率 | 16% | 83% |
| 批量成功率 | - | 100% (20/20) |
| 平均质量分 | ~70 | 85.1 |
| recommended 比例 | ~40% | 100% |
| 静默BGM | 频繁 | 0/20 |
| 重复素材(平均) | 3.4 | 2.2 |
| 可处理素材(单一视频) | 1 | 24 |

### 关键指标

- 97个素材 (94视频 + 3图片)
- 单条视频生成约 30-45 秒
- Average 素材去重后 2.2 个重复
- 支持 5 种配音音色 (Voice Profiles)
- 支持 3 首真实 BGM
- 200+ 测试用例
- 17 篇技术文档

## 技术栈

```
Python 3.14
├── LLM: DeepSeek API (OpenAI-compatible)
├── Image: CLIP ViT-B-32 (open_clip_torch)
├── TTS: Microsoft Edge TTS
├── ASR: Whisper base
├── Video: FFmpeg 8.1.1
├── Scene: PySceneDetect + OpenCV
├── Quality: Heuristic Scorer (7-dimension)
└── Storage: Local index.json + npy embeddings
```

## 后续商业化可能

1. **旅游公司**: 批量生成目的地短视频, 降低内容生产成本
2. **自媒体**: CLI + 未来 Web UI, 个人旅行博主日常使用
3. **API 服务**: Pipeline 封装为 REST API, 批量生产
4. **垂直定制**: 美食/酒店/户外/亲子等细分领域素材库 + Prompt 定制
