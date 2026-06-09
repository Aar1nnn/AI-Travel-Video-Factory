# AI Travel Video Factory — 模块映射 V3

**日期**: 2026-06-09

| # | 当前模块 | 当前文件 | 当前作用 | 输入 | 输出 | 当前能力 | 可参考开源 | 是否接入 | 接入优先级 | 风险 | 下一步建议 |
|---|----------|----------|----------|------|------|----------|------------|----------|------------|------|------------|
| 1 | 文案生成 | script_generator.py | DeepSeek LLM生成旁白脚本 | topic, style | Script(scenes) | LLM生成中英文文案, scene_type+tags, 自动重试 | - | - | - | LLM文本长度偶尔异常 | 优化Prompt |
| 2 | 分镜生成 | script_generator.py | 每个scene输出mood+scene_type+tags | Script.scenes | scene.mood, scene.scene_type, scene.asset_tags | 6种mood, 17种scene_type | - | - | - | tags与素材库不匹配 | Prompt微调 |
| 3 | 素材匹配 | asset_library.py | V4语义+标签+场景类型多维度打分 | Scene + index.json | ScoredAsset[] | CLIP semantic + scene_type + tag + mood + city | - | - | - | 61%素材为general | auto-tag全覆盖 |
| 4 | 素材去重 | pipeline.py | 统计duplicate_asset_count | Scene assets | metadata | 跨场景统计重复素材ID | - | - | - | - | 记录到metadata |
| 5 | 配音 | voice_generator.py | Edge TTS per-scene生成→FFmpeg concat | Script.scenes | voice.mp3 | mood调整语速, 5种voice profile | - | - | - | Edge TTS偶尔失败 | 增加retry |
| 6 | 字幕生成 | subtitle_generator.py | Whisper base转录→SRT | voice.mp3 | subtitles.srt | 中文识别, 长句拆分, 18字/行 | faster-whisper | **建议接入** | P0 | 输出繁体 | 替换whisper → faster-whisper |
| 7 | ASS字幕烧录 | video_composer.py | SRT→ASS→FFmpeg subtitles filter | subtitles.srt + concat_video.mp4 | composed_video.mp4 | TikTok样式: 白字黑边, 底部居中 | - | - | - | Windows路径转义 | 改用drawtext |
| 8 | BGM | video_composer.py | 随机选择bgm/*.mp3, volume 0.15, fade | bgm/目录 | composed_video with BGM | 5首BGM随机, 自动fade, warning if missing | - | - | - | BGM都是静默测试文件 | 下载真实配乐 |
| 9 | 视频合成 | video_composer.py | FFmpeg: crop+scale→concat→merge→subtitle→bgm→mp4 | clips + voice + srt + bgm | composed_video.mp4 | 1080×1920竖屏, H.264+AAC, 30fps | Remotion | **建议实验** | P2 | FFmpeg路径硬编码 | 配置化FFmpeg路径 |
| 10 | 批量生成 | main.py | --batch-demo N 批量生成+quality_report | N | quality_report.json | 20条/批, 自动记录成功/失败 | - | - | - | 无API限流 | 增加速率控制 |
| 11 | 质量报告 | main.py + pipeline.py | 统计技术指标 | batch run | quality_report.json | 时长/大小/场景/素材/去重/BGM/字幕 | - | - | - | 只有技术指标,缺内容评分 | Quality Scorer V1 |
| 12 | WhisperX实验 | experiments/whisperx_test/ | 评估faster-whisper | voice.mp3 | test_output.srt/.ass | 已验证word timestamps, 推理0.3s | - | - | - | Python 3.14不兼容WhisperX | 接入faster-whisper |
| 13 | 交付打包 | exporter.py | 复制+重命名最终视频 | composed_video.mp4 | {topic}_{date}.mp4 | 元数据+字幕+脚本全部导出 | - | - | - | - | Delivery Package V1 |
| 14 | 未来前端UI | (未开发) | - | - | - | - | OpenShorts, YumCut | **仅参考** | P6 | 技术栈差异大 | 不做 |
| 15 | 未来Remotion模板 | (未开发) | 片头/价格卡片/封面 | - | - | - | Remotion | **建议实验** | P2 | React技术栈依赖 | experiments/remotion_test/ |

---

## 当前可立即接入 (P0)
- **faster-whisper**: 替换subtitle_generator.py中的whisper, 预计30分钟

## 当前建议实验 (P1-P2)
- **Pexels API**: experiments/pexels_asset_test/
- **Remotion**: experiments/remotion_test/

## 当前不做 (P3+)
- 前端UI
- SaaS
- 自动发布TikTok
