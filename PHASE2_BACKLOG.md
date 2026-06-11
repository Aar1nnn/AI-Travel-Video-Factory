## Phase 2 Sprint 3 — Asset Processor V1 — Complete

### 1. 修改文件列表

| 文件 | 变更 |
|------|------|
| `src/asset_processor.py` | **新增** — AssetProcessor 类, shot detection + cutting + thumbnails |
| `src/asset_library.py` | AssetRecord 新增4字段: thumbnail, source_video, start_time, end_time |
| `src/config.py` | 新增路径常量: ASSETS_RAW_DIR, ASSETS_PROCESSED_DIR, ASSETS_THUMBNAILS_DIR |
| `main.py` | 新增 `--process-assets` CLI 命令 |
| `tests/test_asset_processor.py` | **新增** — 22 个测试 |
| `assets/raw/.gitkeep` | 新建 |
| `assets/processed/.gitkeep` | 新建 |
| `assets/thumbnails/.gitkeep` | 新建 |

### 2. 新增依赖

```
scenedetect==0.7
opencv-python==4.13.0.92
click==8.4.1
platformdirs==4.10.0
```

### 3. 测试结果

```
148/148 passed
```

- test_asset_library: 10
- test_asset_matching_v2: 25
- test_asset_processor: 22 (NEW)
- test_pipeline: 14
- test_scene_understanding: 28
- test_script_generator: 12
- test_video_composer: 15
- test_voice_generator: 22

### 4. CLI 使用方式

```bash
# 1. 把原始视频放入 assets/raw/
cp my_yunnan_sunset.mp4 assets/raw/

# 2. 自动处理
python main.py --process-assets

# 输出:
# [1/1] Processing: my_yunnan_sunset.mp4
#   Detected 18 scenes
#   asset_008: 5.2s [0.0-5.2] 1920x1080
#   asset_009: 3.1s [5.2-8.3] 1920x1080
#   ...

# 3. 检查结果
ls assets/processed/    # 切割后的片段
ls assets/thumbnails/   # 缩略图
cat assets/index.json   # 已更新索引
```

### 5. index.json 示例

```json
{
  "id": "asset_008",
  "path": "processed/asset_008.mp4",
  "type": "video",
  "tags": [],
  "country": "",
  "city": "",
  "category": "",
  "scene_type": "general",
  "moods": [],
  "duration": 5.2,
  "resolution": "1920x1080",
  "orientation": "horizontal",
  "file_size_kb": 8450,
  "source": "auto-processed",
  "thumbnail": "thumbnails/asset_008.jpg",
  "source_video": "raw/my_yunnan_sunset.mp4",
  "start_time": 0.0,
  "end_time": 5.2
}
```

### 6. AI 自动打标签扩展点

预留字段（当前为空，可接入AI）：

| 字段 | 类型 | AI接入方式 | 难度 |
|------|------|-----------|------|
| `tags` | list | CLIP zero-shot 分类 | 中 |
| `scene_type` | str | CLIP + 17类文本描述匹配 | 低 |
| `moods` | list | 画面分类模型 | 中 |
| `category` | str | 从scene_type推导 | 低 |
| `city` / `country` | str | 从目录名或用户指定 | 低 |

建议第一版AI打标签方案：
```python
# future: src/asset_tagger.py
class AssetTagger:
    def tag(self, asset: AssetRecord) -> AssetRecord:
        # 1. 从缩略图提取 CLIP embedding
        # 2. 与17个 scene_type 描述文本比较
        # 3. 取 top-1 作为 scene_type
        # 4. 可选的 tags 从预定义词库中检索 top-5
        ...
```
