# WhisperX / faster-whisper 替换方案评估报告

**日期**: 2026-06-09
**测试目录**: experiments/whisperx_test/
**产出文件**: test_output.srt, test_output.ass

---

## 1. 结论：不推荐接入 WhisperX，推荐用 faster-whisper 替换当前 whisper

| 维度 | WhisperX | faster-whisper | 当前 whisper |
|------|----------|---------------|--------------|
| Python 3.14 兼容 | ❌ 不支持 | ✅ | ✅ |
| pip 安装 | ❌ ctranslate2 版本冲突 | ✅ 直接安装 | ✅ 已安装 |
| 推理速度 | ? (无法测试) | 0.3s (base) | 3-8s |
| Word timestamps | ✅ | ✅ | ❌ |
| 强制对齐 (forced alignment) | ✅ (需 wav2vec2) | ❌ | ❌ |
| 繁简体 | ？ | 繁体 (需 post-fix) | 偶尔繁体 |
| ASS 生成 | ？ | ✅ (经SRT转换) | ✅ |
| 接入工作量 | 高 | **低 (API 几乎相同)** | - |

---

## 2. 为什么不能用 WhisperX

```
WhisperX 要求 Python < 3.13
当前环境: Python 3.14.5
pip install whisperx → ctranslate2==4.4.0 不存在 (当前只有 4.8.0)
```

除非降级 Python 或 Docker 隔离，否则无法安装。

---

## 3. faster-whisper 测试数据

| 指标 | 数值 |
|------|------|
| 模型 | base |
| 推理速度 | **0.3s** (27.6s 音频) |
| Word timestamps | ✅ 109 个词，每个词有 start/end/probability |
| 语言检测 | ✅ 自动 (zh, prob=1.00) |
| Segment 分割质量 | 5 segments, 平均 5.5s/段 |

### Word timestamp 示例:
```
從 [0.00s-0.28s] prob=0.93
立 [0.28s-0.40s] prob=0.48
江 [0.40s-0.54s] prob=0.71
出 [0.54s-0.72s] prob=0.96
發 [0.72s-0.90s] prob=0.99
```

---

## 4. 是否推荐接入主项目

**✅ 推荐用 faster-whisper 替换当前 whisper (openai-whisper)**

### 理由:
1. 推理快 10-20x
2. Word timestamps → 可以做逐词高亮字幕
3. API 几乎相同：`model.transcribe(audio, language="zh")`
4. 不需要额外依赖（已经装好了）
5. 可以解决 "字幕与语音不同步" 问题（word timestamps 精确到 0.01s）

### 不过:
- faster-whisper base 模型输出仍然是繁体中文（和 whisper 一样的问题）
- 需要在后处理中加繁→简转换（`opencc` 或 `zhconv`）

---

## 5. 最小接入方案

### 修改文件:
1. `src/subtitle_generator.py` — 替换 `import whisper` → `from faster_whisper import WhisperModel`
2. `requirements.txt` — 添加 `faster-whisper`

### 改动量:
- 约 20 行代码变更
- 预计 30 分钟

### 风险:
- 低。API 相似度 90%，只需改 model.load 和 transcribe 调用方式
- faster-whisper 返回的 segments 是 generator，需要 list() 转换

### 不建议改动:
- SRT/ASS pipeline 保持不变
- _split_segments 逻辑保持
- VideoComposer 完全不变

---

## 6. 输出文件

- `experiments/whisperx_test/test_output.srt` — 生成的SRT字幕
- `experiments/whisperx_test/test_output.ass` — 生成的ASS字幕
- `experiments/whisperx_test/voice.mp3` — 测试音频
