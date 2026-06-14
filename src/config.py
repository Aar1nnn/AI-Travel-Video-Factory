"""
AI Travel Video Factory — 全局配置模块

从 config/default.yaml 读取默认参数，
支持 .env 环境变量覆盖敏感配置。
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


# ── Paths ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
ASSETS_DIR = PROJECT_ROOT / "assets"
ASSETS_INDEX = ASSETS_DIR / "index.json"
ASSETS_RAW_DIR = ASSETS_DIR / "raw"
ASSETS_PROCESSED_DIR = ASSETS_DIR / "processed"
ASSETS_THUMBNAILS_DIR = ASSETS_DIR / "thumbnails"
ASSETS_EMBEDDINGS_DIR = ASSETS_DIR / "embeddings"
BGM_DIR = PROJECT_ROOT / "bgm"
FONTS_DIR = PROJECT_ROOT / "fonts"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = OUTPUT_DIR / "temp"
LOGS_DIR = PROJECT_ROOT / "logs"


# ── Config Models ──────────────────────────────────────

class VideoConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23


class AudioConfig(BaseModel):
    bgm_volume: float = 0.15
    voice_volume: float = 1.0
    ducking_reduction: float = 0.4
    sample_rate: int = 44100


class TTSConfig(BaseModel):
    provider: str = "edge_tts"
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+10%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2000
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""  # 从 .env 注入，不在 YAML 中


class WhisperConfig(BaseModel):
    model: str = "base"
    language: str = "zh"
    word_timestamps: bool = False


class VoiceProfile(BaseModel):
    """单个语音 profile 定义"""
    name: str
    voice: str
    rate: str
    pitch: str
    volume: str


class AppConfig(BaseModel):
    video: VideoConfig = VideoConfig()
    audio: AudioConfig = AudioConfig()
    tts: TTSConfig = TTSConfig()
    llm: LLMConfig = LLMConfig()
    whisper: WhisperConfig = WhisperConfig()


# ── Load ───────────────────────────────────────────────

def _load_yaml_config() -> dict:
    """加载 default.yaml 返回原始字典。"""
    yaml_path = CONFIG_DIR / "default.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_voice_profiles() -> dict[str, VoiceProfile]:
    """加载 config/voices.yaml 返回 {profile_name: VoiceProfile}。"""
    voices_path = CONFIG_DIR / "voices.yaml"
    if not voices_path.exists():
        return {}
    with open(voices_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    profiles = {}
    for key, pd in data.get("profiles", {}).items():
        profiles[key] = VoiceProfile(**pd)
    return profiles


def _load_env_overrides() -> dict:
    """从 .env 读取敏感配置（API Key 等）。

    使用 find_dotenv 自动定位项目根目录的 .env，
    避免 Streamlit 在不同 CWD 下运行时找不到文件。
    """
    from dotenv import find_dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
    # Fallback: also try explicit path
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists() and not os.getenv("DEEPSEEK_API_KEY"):
        load_dotenv(env_path, override=True)
    return {
        "api_key": os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "",
    }


def get_config() -> AppConfig:
    """
    加载配置：default.yaml（基础） + .env（敏感信息覆盖）。

    两层合并：
      1. 读取 YAML → 得到 video/audio/tts/llm/whisper 各段
      2. 读取 .env → 将 api_key 注入 llm 段
      3. 用 Pydantic 校验整个 AppConfig
    """
    yaml_data = _load_yaml_config()
    env_data = _load_env_overrides()

    # 将 api_key 注入 llm 子配置
    llm_section = yaml_data.get("llm", {})
    llm_section["api_key"] = env_data["api_key"]
    yaml_data["llm"] = llm_section

    return AppConfig(**yaml_data)


def get_voice_profiles() -> dict[str, VoiceProfile]:
    """返回所有 voice profiles（从 config/voices.yaml）。"""
    return _load_voice_profiles()


def get_voice_profile(name: str) -> VoiceProfile | None:
    """获取指定名称的 voice profile，不存在返回 None。"""
    profiles = _load_voice_profiles()
    return profiles.get(name)


# ── Singleton ──────────────────────────────────────────

config: Optional[AppConfig] = None


def init_config() -> AppConfig:
    """初始化全局配置（在 main.py 启动时调用一次）。"""
    global config
    config = get_config()
    return config
