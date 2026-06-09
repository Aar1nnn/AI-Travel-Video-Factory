"""
模块 1: Script Generator（脚本 + 场景规划）

职责：
- 接收用户主题
- 调用 LLM 生成 30 秒旅游视频旁白脚本
- 同时为每个场景规划素材标签
- 输出标准化的 script.json
"""

import json
import re
import time
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ValidationError, field_validator


# ── SceneType ───────────────────────────────────────────

class SceneType:
    AIRPORT = "airport"; HOTEL = "hotel"; BEACH = "beach"; ISLAND = "island"
    LAKE = "lake"; MOUNTAIN = "mountain"; CITY = "city"; FOOD = "food"
    MARKET = "market"; TEMPLE = "temple"; SUNSET = "sunset"; NIGHT = "night"
    WILDLIFE = "wildlife"; SHOPPING = "shopping"; TRANSPORT = "transport"
    LANDSCAPE = "landscape"; GENERAL = "general"
    ALL = frozenset([AIRPORT, HOTEL, BEACH, ISLAND, LAKE, MOUNTAIN, CITY, FOOD, MARKET, TEMPLE, SUNSET, NIGHT, WILDLIFE, SHOPPING, TRANSPORT, LANDSCAPE, GENERAL])

    @classmethod
    def is_valid(cls, v): return v in cls.ALL
    @classmethod
    def default(cls): return cls.GENERAL


# ── Data Models ────────────────────────────────────────

class Scene(BaseModel):
    """单个场景"""
    id: int
    text: str
    mood: str
    asset_tags: list[str]
    scene_type: str = "general"

    @field_validator("scene_type")
    @classmethod
    def validate_scene_type(cls, v):
        if not SceneType.is_valid(v):
            raise ValueError(f"无效 scene_type: {v}，允许: {sorted(SceneType.ALL)}")
        return v


class Script(BaseModel):
    """完整脚本"""
    title: str
    topic: str
    scenes: list[Scene]


# ── Style Descriptions ─────────────────────────────────

STYLE_DESCRIPTIONS = {
    "快节奏": "画面切换迅速（每2-3秒切一次），配乐动感，语速较快，适合抖音/小红书年轻用户。",
    "舒缓": "画面切换柔和（每4-5秒切一次），配乐轻缓，语速适中，适合意境类内容。",
    "文艺": "画面细腻，配乐优雅，文案富有诗意和故事感，适合高端旅游品牌。",
}

VALID_MOODS = {"开场吸引", "轻松惬意", "活力刺激", "神秘探索", "温馨感人", "结尾号召"}

# Scene type descriptions for the LLM prompt
SCENE_TYPE_DESCRIPTIONS = {
    "airport": "机场/出发", "hotel": "酒店/住宿", "beach": "海滩/沙滩",
    "island": "海岛/岛屿", "lake": "湖泊", "mountain": "高山/雪山",
    "city": "城市/街道", "food": "美食/餐饮", "market": "夜市/市场",
    "temple": "寺庙/神社", "sunset": "日落/黄昏", "night": "夜景",
    "wildlife": "动物/生态", "shopping": "购物/商业", "transport": "交通/出行",
    "landscape": "自然风光", "general": "通用",
}


# ── Generator ──────────────────────────────────────────

class ScriptGenerator:
    """
    旅游视频脚本生成器。

    使用 DeepSeek API 根据主题生成结构化脚本。

    Attributes:
        llm_config: LLM 配置（api_key, model, base_url 等）
        prompt_template: 从文件加载的 Prompt 模板字符串
        client: OpenAI 兼容客户端
    """

    def __init__(self, llm_config, prompt_template_path: Path):
        """
        Args:
            llm_config: LLMConfig 实例（含 api_key, model, base_url 等）
            prompt_template_path: Prompt 模板文件路径
        """
        self.llm_config = llm_config
        self.prompt_template = self._load_template(prompt_template_path)

        # 使用 OpenAI 兼容客户端连接 DeepSeek
        self.client = OpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
        )

    # ── Public API ─────────────────────────────────────

    def generate(self, topic: str, style: str = "快节奏") -> Script:
        """
        根据主题生成脚本。

        Args:
            topic: 旅游主题，如 "沙巴5天4晚旅游攻略"
            style: 视频风格，"快节奏" / "舒缓" / "文艺"

        Returns:
            Script 对象，包含 title 和 scenes 列表

        Raises:
            ValueError: 风格不支持，或 LLM 返回格式无效
            RuntimeError: 3 次重试后 LLM API 仍失败
        """
        if style not in STYLE_DESCRIPTIONS:
            raise ValueError(
                f"不支持的风格: {style}，可选: {list(STYLE_DESCRIPTIONS.keys())}"
            )

        prompt = self._build_prompt(topic, style)

        # 最多重试 3 次
        last_error = None
        for attempt in range(1, 4):
            try:
                print(f"  [ScriptGenerator] 第 {attempt} 次调用 LLM...")
                raw_text = self._call_llm(prompt)
                script = self._parse_response(raw_text, topic)
                self._validate(script)
                print(f"  [ScriptGenerator] 脚本生成成功: {script.title}")
                return script
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                last_error = e
                print(f"  [ScriptGenerator] WARNING 第 {attempt} 次失败: {e}")
                if attempt < 3:
                    time.sleep(1 * attempt)  # 递增等待：1s, 2s
            except Exception as e:
                last_error = e
                print(f"  [ScriptGenerator] WARNING 第 {attempt} 次 API 异常: {e}")
                if attempt < 3:
                    time.sleep(2 * attempt)  # API 错误等待更长：2s, 4s

        raise RuntimeError(
            f"LLM 脚本生成失败，已重试 3 次。最后一次错误: {last_error}"
        )

    # ── Private Methods ────────────────────────────────

    def _load_template(self, path: Path) -> str:
        """从文件加载 Prompt 模板。"""
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _build_prompt(self, topic: str, style: str) -> str:
        """填充 Prompt 模板中的占位符。"""
        style_desc = STYLE_DESCRIPTIONS[style]
        return (
            self.prompt_template
            .replace("{topic}", topic)
            .replace("{style}", style)
            .replace("{style_description}", style_desc)
        )

    def _call_llm(self, prompt: str) -> str:
        """
        调用 DeepSeek API（OpenAI 兼容接口）。

        Returns:
            LLM 返回的原始文本

        Raises:
            RuntimeError: API 调用失败
        """
        response = self.client.chat.completions.create(
            model=self.llm_config.model,
            messages=[
                {"role": "system", "content": "你是一个专业的旅游短视频脚本撰写人。只输出 JSON，不输出其他内容。"},
                {"role": "user", "content": prompt},
            ],
            temperature=self.llm_config.temperature,
            max_tokens=self.llm_config.max_tokens,
        )

        raw = response.choices[0].message.content
        if raw is None:
            raise ValueError("LLM 返回内容为空")
        return raw.strip()

    def _parse_response(self, raw_text: str, topic: str) -> Script:
        """
        从 LLM 原始响应中提取 JSON 并解析为 Script 对象。

        处理 LLM 可能包裹的 ```json...``` 标记。
        """
        # 尝试提取 ```json ... ``` 代码块
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # 直接当作 JSON 解析
            json_str = raw_text.strip()

        data = json.loads(json_str)

        # 注入 topic 字段
        data["topic"] = topic

        return Script(**data)

    def _validate(self, script: Script) -> None:
        """
        校验脚本质量。

        Raises:
            ValueError: 脚本不满足质量要求
        """
        # 场景数量 3~6
        if not (3 <= len(script.scenes) <= 6):
            raise ValueError(
                f"场景数量异常: {len(script.scenes)} (期望 3~6)"
            )

        # 总文本字符数 80~200（对应约 20~40 秒朗读）
        total_chars = sum(len(s.text) for s in script.scenes)
        if not (80 <= total_chars <= 200):
            raise ValueError(
                f"总文本长度异常: {total_chars} 字 (期望 80~200)"
            )

        # mood 必须在允许值内
        for scene in script.scenes:
            if scene.mood not in VALID_MOODS:
                raise ValueError(
                    f"场景 {scene.id} mood 无效: {scene.mood}，允许: {VALID_MOODS}"
                )

        # asset_tags 每个场景 2~8 个标签
        for scene in script.scenes:
            if not (2 <= len(scene.asset_tags) <= 8):
                raise ValueError(
                    f"场景 {scene.id} asset_tags 数量异常: "
                    f"{len(scene.asset_tags)} (期望 2~8)"
                )

            # scene_type 必须在允许值内
            if scene.scene_type and not SceneType.is_valid(scene.scene_type):
                raise ValueError(
                    f"场景 {scene.id} scene_type 无效: {scene.scene_type}，允许: {sorted(SceneType.ALL)}"
                )

        # Scene id 从 1 开始连续递增
        expected_ids = list(range(1, len(script.scenes) + 1))
        actual_ids = [s.id for s in script.scenes]
        if actual_ids != expected_ids:
            raise ValueError(
                f"场景 id 不连续: {actual_ids} (期望 {expected_ids})"
            )

        # title 不为空
        if not script.title or len(script.title.strip()) == 0:
            raise ValueError("title 为空")
