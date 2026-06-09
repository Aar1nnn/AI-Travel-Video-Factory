"""
Script Generator 单元测试

运行方式:
    cd d:/AI-Workspace/projects/ai-travel-video-factory
    python -m pytest tests/test_script_generator.py -v

    或者直接运行:
    python tests/test_script_generator.py
"""

import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import init_config, LLMConfig
from src.script_generator import ScriptGenerator, Script, Scene, VALID_MOODS


# ── Mock 测试（不需要真实 API Key）─────────────────────

class MockOpenAIResponse:
    """模拟 OpenAI API 响应"""
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockChoice:
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    def __init__(self, content: str):
        self.content = content


class FakeCompletions:
    """模拟 chat.completions"""
    def __init__(self, return_content: str):
        self.return_content = return_content

    def create(self, **kwargs):
        return MockOpenAIResponse(self.return_content)


class FakeClient:
    """模拟 OpenAI 客户端"""
    def __init__(self, return_content: str):
        self.chat = FakeCompletions(return_content)


# ── Test Fixtures ──────────────────────────────────────

VALID_SCRIPT_JSON = '''
{
  "title": "沙巴5天4晚｜热带天堂",
  "scenes": [
    {
      "id": 1,
      "text": "沙巴，马来西亚的宝藏目的地，5天4晚带你玩转热带天堂。",
      "mood": "开场吸引",
      "asset_tags": ["全景", "海滩", "沙巴", "俯瞰"]
    },
    {
      "id": 2,
      "text": "第一天落地亚庇，入住海景酒店，傍晚去丹绒亚路看全球最美日落。",
      "mood": "轻松惬意",
      "asset_tags": ["机场", "酒店", "日落", "海滩"]
    },
    {
      "id": 3,
      "text": "第二天跳岛浮潜，马努干岛的玻璃海让你不想上岸。",
      "mood": "活力刺激",
      "asset_tags": ["海岛", "浮潜", "沙滩", "玻璃海"]
    },
    {
      "id": 4,
      "text": "第三天探访红树林，寻找长鼻猴和萤火虫的奇幻夜。",
      "mood": "神秘探索",
      "asset_tags": ["丛林", "红树林", "动物", "萤火虫"]
    },
    {
      "id": 5,
      "text": "沙巴，一个来了就不想走的地方。关注我们，获取更多旅行攻略。",
      "mood": "结尾号召",
      "asset_tags": ["日落", "全景", "总结", "品牌"]
    }
  ]
}
'''

INVALID_MOOD_JSON = '''
{
  "title": "测试标题",
  "scenes": [
    {
      "id": 1,
      "text": "测试文本不少于十个字以确保通过字数校验这是补充文字。",
      "mood": "不存在的氛围",
      "asset_tags": ["测试", "无效"]
    },
    {
      "id": 2,
      "text": "测试文本2不少于十个字以确保通过字数校验这是补充文字。",
      "mood": "开场吸引",
      "asset_tags": ["测试2", "标签"]
    },
    {
      "id": 3,
      "text": "测试文本3不少于十个字以确保通过字数校验这是补充文字。",
      "mood": "轻松惬意",
      "asset_tags": ["测试3", "标签"]
    }
  ]
}
'''


# ── Test Cases ─────────────────────────────────────────

def test_parse_valid_script():
    """测试正确解析 LLM 返回的合法 JSON"""
    generator = _make_generator(VALID_SCRIPT_JSON)
    script = generator._parse_response(VALID_SCRIPT_JSON, "沙巴5天4晚旅游攻略")

    assert isinstance(script, Script)
    assert script.title == "沙巴5天4晚｜热带天堂"
    assert script.topic == "沙巴5天4晚旅游攻略"
    assert len(script.scenes) == 5
    assert script.scenes[0].id == 1
    assert script.scenes[0].mood == "开场吸引"
    assert "海滩" in script.scenes[0].asset_tags


def test_parse_json_with_code_block():
    """测试解析被 ```json...``` 包裹的 LLM 响应"""
    wrapped = f"```json\n{VALID_SCRIPT_JSON}\n```"
    generator = _make_generator(wrapped)
    script = generator._parse_response(wrapped, "沙巴")

    assert isinstance(script, Script)
    assert len(script.scenes) == 5


def test_parse_json_without_code_block():
    """测试解析裸 JSON（无代码块包裹）"""
    generator = _make_generator(VALID_SCRIPT_JSON)
    script = generator._parse_response(VALID_SCRIPT_JSON, "沙巴")

    assert isinstance(script, Script)
    assert script.title == "沙巴5天4晚｜热带天堂"


def test_validate_passes():
    """测试校验通过"""
    generator = _make_generator(VALID_SCRIPT_JSON)
    script = generator._parse_response(VALID_SCRIPT_JSON, "沙巴")
    # 不应抛出异常
    generator._validate(script)


def test_validate_rejects_invalid_mood():
    """测试校验拒绝无效 mood"""
    generator = _make_generator(INVALID_MOOD_JSON)
    script = generator._parse_response(INVALID_MOOD_JSON, "测试")
    try:
        generator._validate(script)
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "mood 无效" in str(e)


def test_validate_rejects_wrong_scene_count():
    """测试校验拒绝场景数量异常"""
    too_few = json.loads(VALID_SCRIPT_JSON)
    too_few["scenes"] = too_few["scenes"][:2]  # 只有 2 个场景
    from src.script_generator import Script as S
    script = S(**too_few, topic="测试")
    generator = _make_generator(json.dumps(too_few))
    try:
        generator._validate(script)
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "场景数量" in str(e)


def test_validate_rejects_short_text():
    """测试校验拒绝文本过短"""
    data = json.loads(VALID_SCRIPT_JSON)
    # 将所有场景文本改为很短
    for s in data["scenes"]:
        s["text"] = "短"
    from src.script_generator import Script as S
    script = S(**data, topic="测试")
    generator = _make_generator(json.dumps(data))
    try:
        generator._validate(script)
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "文本长度" in str(e)


def test_validate_rejects_non_sequential_ids():
    """测试校验拒绝不连续的 scene id"""
    data = json.loads(VALID_SCRIPT_JSON)
    data["scenes"][0]["id"] = 99  # 破坏连续性
    from src.script_generator import Script as S
    script = S(**data, topic="测试")
    generator = _make_generator(json.dumps(data))
    try:
        generator._validate(script)
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "不连续" in str(e)


def test_prompt_building():
    """测试 Prompt 模板填充"""
    generator = _make_generator(VALID_SCRIPT_JSON)
    prompt = generator._build_prompt("沙巴5天4晚", "快节奏")

    assert "沙巴5天4晚" in prompt
    assert "快节奏" in prompt
    assert "画面切换迅速" in prompt  # 快节奏的描述


def test_scene_model():
    """测试 Scene Pydantic 模型"""
    scene = Scene(id=1, text="测试文本", mood="开场吸引", asset_tags=["标签1", "标签2"])
    assert scene.id == 1
    assert scene.mood in VALID_MOODS

    # asset_tags 必须是字符串列表
    try:
        Scene(id=1, text="测试", mood="开场吸引", asset_tags=[1, 2, 3])
        assert False, "应抛出 ValidationError"
    except Exception:
        pass


def test_style_rejection():
    """测试不支持的风格"""
    generator = _make_generator(VALID_SCRIPT_JSON)
    # 使用 FakeClient 所以不需要真实 API
    generator.client = FakeClient(VALID_SCRIPT_JSON)

    try:
        generator.generate("测试", style="不存在的风格")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "不支持的风格" in str(e)


# ── 集成测试（需要真实 API Key）────────────────────────

def test_generate_with_real_api():
    """
    集成测试：使用真实 DeepSeek API 生成脚本。

    需要有 .env 或 DEEPSEEK_API_KEY 环境变量。
    如果没有 API Key，跳过此测试。
    """
    try:
        config = init_config()
    except Exception:
        print("\n  [跳过] 无法加载配置（可能缺少 .env 或 default.yaml）")
        return

    if not config.llm.api_key:
        print("\n  [跳过] 未配置 DEEPSEEK_API_KEY，跳过集成测试")
        return

    prompt_path = PROJECT_ROOT / "prompts" / "script_generation.txt"
    generator = ScriptGenerator(config.llm, prompt_path)

    script = generator.generate("沙巴5天4晚旅游攻略", style="快节奏")

    # 基础断言
    assert isinstance(script, Script)
    assert len(script.title) > 0
    assert 3 <= len(script.scenes) <= 6
    assert script.topic == "沙巴5天4晚旅游攻略"

    # 每个 scene 校验
    for scene in script.scenes:
        assert len(scene.text) > 0
        assert scene.mood in VALID_MOODS
        assert 2 <= len(scene.asset_tags) <= 8

    print(f"\n  ✅ 集成测试通过！")
    print(f"  标题: {script.title}")
    print(f"  场景数: {len(script.scenes)}")
    total_chars = sum(len(s.text) for s in script.scenes)
    print(f"  总字数: {total_chars}")
    for s in script.scenes:
        print(f"    Scene {s.id}: [{s.mood}] {s.text[:40]}...")


# ── Helpers ────────────────────────────────────────────

def _make_generator(mock_response: str) -> ScriptGenerator:
    """创建一个使用 Mock 客户端的 ScriptGenerator"""
    llm_config = LLMConfig(
        provider="deepseek",
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=2000,
        base_url="https://api.deepseek.com",
        api_key="mock-key",
    )
    prompt_path = PROJECT_ROOT / "prompts" / "script_generation.txt"
    generator = ScriptGenerator(llm_config, prompt_path)
    generator.client = FakeClient(mock_response)
    return generator


# ── Main ───────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Script Generator — 单元测试")
    print("=" * 60)

    tests = [
        ("解析合法 JSON", test_parse_valid_script),
        ("解析代码块包裹的 JSON", test_parse_json_with_code_block),
        ("解析裸 JSON", test_parse_json_without_code_block),
        ("校验通过", test_validate_passes),
        ("拒绝无效 mood", test_validate_rejects_invalid_mood),
        ("拒绝场景数量异常", test_validate_rejects_wrong_scene_count),
        ("拒绝文本过短", test_validate_rejects_short_text),
        ("拒绝不连续 id", test_validate_rejects_non_sequential_ids),
        ("Prompt 模板填充", test_prompt_building),
        ("Scene Pydantic 模型", test_scene_model),
        ("拒绝不支持的风格", test_style_rejection),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed, {len(tests)} total")

    # 集成测试
    print("\n--- 集成测试 ---")
    test_generate_with_real_api()

    print("\n" + "=" * 60)
