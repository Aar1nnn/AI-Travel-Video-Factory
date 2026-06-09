# AI Travel Video Factory — 开源集成规划

**日期**: 2026-06-09

---

## 候选开源项目

| # | 项目 | 用途 | 对应模块 | 建议接入 | 优先级 | 接入方式 | 风险 | 必须先进experiments |
|---|------|------|----------|----------|--------|----------|------|---------------------|
| 1 | **faster-whisper** | Word-level timestamp, 更快转录, 字幕对齐 | subtitle_generator.py | **建议接入** | P0 | 替换 `import whisper` → `from faster_whisper import WhisperModel` | 低 | ✅ 已完成 |
| 2 | **Pexels API** | 补充素材 (图片/视频) | asset_library.py | **建议接入** | P1 | 新增PexelsAssetProvider, 不改LocalAssetProvider | 中 (API限流) | ✅ 必须先实验 |
| 3 | **Remotion** | 片头动画, 价格卡片, 封面, 动态字幕 | video_composer.py (不替换主流程) | **建议实验** | P2 | experiments/remotion_test/ → 生成独立PNG/MP4片段, FFmpeg合成 | 高 (React依赖) | ✅ 必须 |
| 4 | **WhisperX** | Forced alignment, word timestamps | subtitle_generator.py | **暂缓** | P3 | Python 3.14不兼容, 无法安装 | 致命 | ✅ 已实验，结论：暂缓 |
| 5 | **Short Video Maker** | TTS/captions/bgm流程参考 | pipeline.py | **仅参考** | P4 | 只研究流程设计, 不接入代码 | 低 | ✅ research only |
| 6 | **OpenShorts** | Dashboard, 项目管理, 发布流程 | 未来前端UI | **仅参考** | P5 | 只研究产品架构, 不做代码移植 | 低 | ✅ research only |
| 7 | **YumCut** | Prompt-to-video交互设计 | main.py CLI | **仅参考** | P6 | 只研究前端交互, 不接入代码 | 低 | ✅ research only |

---

## 详细分析

### 1. faster-whisper (建议接入, P0)

- **实验路径**: `experiments/whisperx_test/`
- **报告**: `experiments/whisperx_test/REPORT.md`
- **结论**: 比openai-whisper快10-20x, 原生word timestamps, API几乎相同
- **接入方案**: 替换 `src/subtitle_generator.py` 中的 `import whisper` → `from faster_whisper`
- **改动量**: ~20行, 预计30分钟
- **风险**: 低。faster-whisper已安装并可运行

### 2. Pexels API (建议接入, P1)

- **实验路径**: `experiments/pexels_asset_test/` (待创建)
- **用途**: 通过Pexels API搜索并下载素材, 补充本地素材库
- **接入方式**: 
  - 新增 `src/pexels_provider.py` → AssetProvider接口
  - 不影响 `src/asset_library.py` 的LocalAssetProvider
  - CLI: `python main.py --pexels-search "洱海日落" --download`
- **风险**: API限流(200次/小时), 版权需标注, 网络依赖
- **是否修改主项目**: 新增文件, 不改现有文件

### 3. Remotion (建议实验, P2)

- **实验路径**: `experiments/remotion_test/` (待创建)
- **用途**: 生成9:16旅游片头模板, 价格标签卡片, 路线信息卡片
- **接入方式**: Remotion渲染PNG/MP4片段 → FFmpeg合成到最终视频
- **风险**: React + Node依赖, 与Python主流程不同技术栈, child_process调用
- **是否修改主项目**: 暂不修改, 仅实验

### 4-7. 其他 (仅参考, P3-P6)

不接入代码, 仅研究设计思路。

---

## 接入规则

1. 所有项目先在 `experiments/` 测试
2. Report.md 结论为"建议接入"才进入主项目
3. 接入时新增文件，不改现有核心文件
4. 接入后运行单条测试 + batch-demo测试
5. 不允许直接复制开源代码到 `src/`
