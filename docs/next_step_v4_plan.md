# V4 下一阶段规划

**日期**: 2026-06-09
**原则**: 只规划，不写功能代码。按优先级排序。

---

## P0: Quality Scorer V1 (内容质量评分)

### 目标
从"技术成功"升级到"内容质量评分"

### 评分维度

| 维度 | 满分 | 评估方式 |
|------|------|----------|
| 开头3秒钩子 | 20 | 检测scene_1.text长度 + 是否有hook关键词 |
| 文案自然度 | 15 | LLM文本长度异常? retry次数? |
| 素材匹配度 | 20 | match_score均值, fallback比例 |
| 字幕观感 | 15 | 字幕条数/场景数比例, 是否有繁体字 |
| BGM适配 | 10 | 是否使用了真实BGM |
| 节奏流畅度 | 10 | clip时长方差, <2s或>10s clip比例 |
| 商业可用性 | 10 | duplicate_asset比例, 总时长是否在20-35s |
| **总分** | **100** | - |

### 规则
- 低于80分: **不建议发布**
- 80-90分: 可发布但需微调
- 90+分: 高质量可发布

### 输出
- `output/quality_report.json` 增加上述字段
- `output/{topic}_scorecard.json` 每个视频的评分卡

---

## P1: Asset Match V2 (减少重复素材)

### 目标
- duplicate_asset_count 尽量控制在0-1
- 增加scene与asset的匹配理由

### 改动
- `pipeline.py`: match_results中附加match_reason
- `asset_library.py`: 增加per-scene dedup优先级
- 输出 `storyboard_with_assets.json`: 每个scene+素材+匹配理由

---

## P2: Delivery Package V1 (独立项目文件夹)

### 目标
每条视频输出为独立项目文件夹

### 目录结构
```
output/projects/{project_id}/
├── final.mp4
├── script.json
├── scenes.json
├── subtitles.ass
├── quality_report.json
├── title.txt
├── caption.txt
├── hashtags.txt
└── metadata.json
```

---

## P3: faster-whisper 接入

### 条件
仅当 `experiments/whisperx_test/report.md` 结论为"建议接入"

### 方案
- 替换 `src/subtitle_generator.py` 中 `import whisper`
- 保留当前字幕方案作为fallback
- 不需要Provider接口（Python内置切换）

---

## P4: Remotion 实验 (不进主项目)

### 目标
仅实验，不进主项目

### 用途
- 生成9:16旅游片头
- 生成价格标签卡片
- 生成路线信息卡片
- 生成封面模板

### 注意
不要用Remotion替换当前FFmpeg主渲染流程

---

## P5: 前端UI (暂不做)

不做。当前优先CLI。
