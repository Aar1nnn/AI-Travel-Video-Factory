# Provider Architecture Plan

**日期**: 2026-06-09
**状态**: 设计文档, 不实现代码

---

## 1. VoiceProvider 接口

```python
class VoiceProvider(ABC):
    """配音Provider抽象接口"""
    
    @abstractmethod
    def generate(self, text: str, profile: VoiceProfile, output_path: Path) -> Path:
        """生成单段配音 → mp3文件"""
        ...
    
    @abstractmethod
    def get_available_voices(self) -> list[dict]:
        """返回可用音色列表"""
        ...
```

### 可选实现

| Provider | 方案 | 状态 |
|----------|------|------|
| EdgeTTSProvider | 当前方案 (edge_tts) | ✅ 已实现 |
| OpenAITTSProvider | OpenAI TTS API | 未实现 |
| AzureTTSProvider | Azure Speech SDK | 未实现 |
| LocalTTSProvider | Coqui/Bark等本地模型 | 未实现 |

---

## 2. SubtitleProvider 接口

```python
class SubtitleProvider(ABC):
    """字幕Provider抽象接口"""
    
    @abstractmethod
    def generate(self, audio_path: Path) -> Path:
        """从音频生成字幕 → srt/ass文件"""
        ...
    
    @abstractmethod
    def get_capabilities(self) -> dict:
        """返回能力: word_timestamps, language_detect, etc."""
        ...
```

### 可选实现

| Provider | 方案 | 状态 |
|----------|------|------|
| WhisperProvider | openai-whisper | ✅ 已实现 |
| FasterWhisperProvider | faster-whisper (word timestamps) | 🔬 实验中 |
| WhisperXProvider | WhisperX (forced alignment) | ❌ Python 3.14不兼容 |
| DirectSRTProvider | 从script.text直接生成SRT (跳过Whisper) | 💡 建议实现 |
| ASSProvider | SRT→ASS转换 | ✅ 已实现 |

---

## 3. AssetProvider 接口

```python
class AssetProvider(ABC):
    """素材Provider抽象接口"""
    
    @abstractmethod
    def search(self, query: AssetQuery) -> list[AssetRecord]:
        """搜索素材"""
        ...
    
    @abstractmethod
    def download(self, asset: AssetRecord, target_dir: Path) -> Path:
        """下载素材到本地"""
        ...
```

### 可选实现

| Provider | 方案 | 状态 |
|----------|------|------|
| LocalAssetProvider | 本地assets/ + index.json | ✅ 已实现 |
| PexelsAssetProvider | Pexels API | 未实现 |
| PixabayAssetProvider | Pixabay API | 未实现 |
| ClientAssetProvider | 客户私有素材 | 未实现 |

---

## 4. Renderer 接口

```python
class Renderer(ABC):
    """渲染器抽象接口"""
    
    @abstractmethod
    def compose(self, script_with_assets: dict, voice: Path, 
                subtitle: Path, bgm: Path, output: Path) -> CompositionResult:
        """合成最终视频"""
        ...
```

### 可选实现

| Renderer | 方案 | 状态 |
|----------|------|------|
| FFmpegRenderer | 当前FFmpeg方案 | ✅ 已实现 |
| RemotionRenderer | React-based渲染 | 🔬 待实验 |
| HybridRenderer | FFmpeg + Remotion片段混合 | 未实现 |

---

## 5. 迁移建议

### 当前代码 → Provider架构

| 当前文件 | 需要改动 | 优先级 |
|----------|----------|--------|
| `voice_generator.py` | 提取VoiceProvider接口 | P3 (低) |
| `subtitle_generator.py` | 先加DirectSRTProvider (免Whisper) | P1 (高) |
| `asset_library.py` | 保持现有接口, 暂不加Provider层 | P2 (中) |
| `video_composer.py` | 保持现有接口, 暂不加Renderer层 | P3 (低) |

### 推荐迁移顺序

1. **DirectSRTProvider** — 从script.text直接生成SRT (免去Whisper, 解决繁简体)
2. **FasterWhisper接入** — 保留Whisper作为fallback
3. **PexelsAssetProvider实验** — 不替换本地库
4. **VoiceProvider/AssetProvider** — 低优先级, 当前接口够用

### 暂不能动的文件

- `video_composer.py` — FFmpeg路径硬编码, 高度耦合
- `pipeline.py` — 6步流程硬编码, 改动影响大
- `main.py` — CLI参数解析, 改动需同步tests

---

## 6. 接入新Provider前必须通过

1. 单条视频生成测试: `python main.py "云南7天6晚情侣游"`
2. 批量测试: `python main.py --batch-demo 3`
3. 现有测试: `pytest tests/`
4. ASS字幕烧录正常
5. BGM正常
6. quality_report.json输出正确
