# AI Travel Video Factory — 实验规则

## 核心原则

**所有开源项目、外部依赖、新能力接入前，必须先在 `experiments/` 目录完成独立测试和评估。**

---

## 规则

### 1. 隔离规则

| # | 规则 |
|---|------|
| 1 | 所有开源项目只允许在 `experiments/` 目录测试 |
| 2 | 不允许直接修改 `src/` 目录 |
| 3 | 不允许直接修改 `main.py` |
| 4 | 不允许直接修改 `src/pipeline.py` |

### 2. 报告规则

| # | 规则 |
|---|------|
| 5 | 每个实验必须输出 `report.md` |
| 6 | `report.md` 必须明确结论：**建议接入 / 暂缓 / 放弃** |
| 7 | 只有 `report.md` 结论为"建议接入"时，才允许进入主项目改造 |
| 8 | `report.md` 必须包含：是否成功运行、安装难度、性能、输出格式、与当前方案对比 |

### 3. 安全规则

| # | 规则 |
|---|------|
| 9 | 每次主项目接入前必须创建 `git branch`（当前非git，建议先 `git init`） |
| 10 | 每次接入前必须写接入计划（在 `docs/` 中） |
| 11 | 每次接入后必须运行单条视频测试和 batch-demo 测试 |
| 12 | 主项目必须始终保持可运行 |

### 4. 依赖规则

| # | 规则 |
|---|------|
| 13 | experiments 目录不能污染主项目依赖 |
| 14 | 外部项目不能直接复制进 `src/` |
| 15 | 如果需要安装新依赖，必须先记录在实验 `report.md` 中 |
| 16 | 如果新依赖会影响主项目环境，必须先说明风险 |

---

## 实验目录结构

```
experiments/
├── {project_name}/
│   ├── README.md           # 实验目标和环境
│   ├── run_test.py         # 或 research_notes.md
│   ├── report.md           # 结论和建议
│   └── (测试输出文件)
```

---

## 当前实验状态

| 实验 | 状态 | 结论 |
|------|------|------|
| `whisperx_test/` | 已完成 | faster-whisper: 建议接入 / WhisperX: 暂缓 (Python 3.14不兼容) |
| `short_video_maker_test/` | 待创建 | - |
| `remotion_test/` | 待创建 | - |
| `openshorts_research/` | 待创建 | - |
| `yumcut_research/` | 待创建 | - |
| `pexels_asset_test/` | 待创建 | - |
