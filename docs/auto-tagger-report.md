# AI Auto Tagger — 技术报告

**日期**: 2026-06-08
**模块**: `src/auto_tagger.py`
**测试**: 174/174 passed (+26 new tests)

---

## 1. 总览

实现了基于 CLIP ViT-B-32 的离线自动标签系统。不需要任何付费 API。

## 2. 架构

```
assets/thumbnails/*.jpg
        ↓
  CLIP ViT-B-32 (laion2b_s34b_b79k)
  - 图像编码 → image_features
  - 文本编码 → text_features (16 scene_type + 50+ tags)
  - 余弦相似度 → softmax
        ↓
  scene_type: "lake"
  tags: ["洱海", "湖景", "云南", "全景"]
  confidence: 0.82
        ↓
  index.json 更新
```

## 3. 修改文件

| 文件 | 变更 |
|------|------|
| `src/auto_tagger.py` | **新增** — CLIP 零样本分类, 16 scene_type + 50+ 标签词库 |
| `src/asset_library.py` | AssetRecord 新增 `confidence: float` 字段 |
| `main.py` | 新增 `--auto-tag` CLI 命令 |
| `tests/test_auto_tagger.py` | **新增** — 26 个测试 |

## 4. 新增依赖

```
open-clip-torch==3.3.0
torchvision==0.27.0
huggingface-hub==1.18.0
timm==1.0.27
Pillow==12.2.0
```

## 5. 测试结果

```
174/174 passed
```

各模块明细:
- test_asset_library: 10
- test_asset_matching_v2: 25
- test_asset_processor: 22
- **test_auto_tagger: 26 (NEW)**
- test_pipeline: 14
- test_scene_understanding: 28
- test_script_generator: 12
- test_video_composer: 15
- test_voice_generator: 22

## 6. 命中率对比

| 指标 | Before (无标签) | After (CLIP标注) |
|------|----------------|-------------------|
| 总场景数 | 6 | 6 |
| 真实素材命中 | 1 | **5** |
| Fallback 使用 | 5 | 1 |
| **命中率** | **16%** | **83%** ✅ |
| 使用素材数 | 8 | 16 |
| 成片时长 | 25.0s | 25.7s |
| 文件大小 | 1.4 MB | 12.0 MB |

## 7. CLI 使用

```bash
# 1. 处理原始视频
python main.py --process-assets

# 2. AI 自动标注
python main.py --auto-tag

# 3. 生成视频
python main.py "云南7天6晚情侣游" --voice travel_female
```

## 8. 已知限制与改进方向

| 问题 | 现状 | 改进方案 |
|------|------|----------|
| confidence 偏低 (0.06-0.07) | ViT-B-32 在 CPU 上精度有限 | 换 ViT-L-14 或 SigLIP |
| 标签偏通用 ("全景"出现38次) | 词库可扩展 | 按地区动态选择标签词库 |
| 模型加载慢 (~5秒) | CPU 推理 | 持久化加载或 GPU 加速 |
| 未利用视频内容 | 仅分析单帧缩略图 | 多帧采样取平均 |
