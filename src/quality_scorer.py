"""
模块: Quality Scorer V1（内容质量评分）

职责:
- 读取生成元数据 对视频进行100分制评分
- 输出评分卡 + 风险标记 + 改进建议

评分维度:
  hook_score (20): 开头钩子
  script_score (15): 文案自然度
  asset_match_score (20): 素材匹配度
  subtitle_score (15): 字幕观感
  bgm_score (10): BGM适配
  pacing_score (10): 节奏流畅度
  commercial_score (10): 商业可用性
"""

import json
from pathlib import Path
from pydantic import BaseModel


class ContentScore(BaseModel):
    """内容质量评分"""
    hook_score: int = 0
    script_score: int = 0
    asset_match_score: int = 0
    subtitle_score: int = 0
    bgm_score: int = 0
    pacing_score: int = 0
    commercial_score: int = 0
    total_score: int = 0
    publish_recommendation: str = "needs_review"


class QualityReport(BaseModel):
    """完整质量报告"""
    technical_status: dict = {}
    content_score: ContentScore = ContentScore()
    risk_flags: list[str] = []
    improvement_suggestions: list[str] = []
    quality_scorer_status: str = "ok"
    quality_scorer_error: str = ""


class QualityScorer:
    """
    V1 内容质量评分器。

    基于生成元数据和脚本内容进行启发式评分。
    不依赖外部AI模型。

    Attributes:
        metadata: Pipeline生成的元数据字典
        script: Script对象的model_dump()结果
    """

    def __init__(self):
        pass

    def score(self, metadata: dict, script: dict | None = None) -> QualityReport:
        """
        执行质量评分。

        Args:
            metadata: Pipeline生成的metadata字典
            script: Script对象的字典（可选，用于分析文案质量）

        Returns:
            QualityReport 含评分卡
        """
        try:
            content = self._score_content(metadata, script)
            risks = self._detect_risks(metadata, content, script)
            suggestions = self._generate_suggestions(metadata, content, risks)

            return QualityReport(
                technical_status={
                    "generation_status": "ok",
                    "video_path": metadata.get("video_path", ""),
                    "duration": metadata.get("duration", 0),
                    "file_size_mb": metadata.get("file_size_mb", 0),
                    "used_assets_count": metadata.get("unique_asset_count", 0),
                    "duplicate_asset_count": metadata.get("duplicate_asset_count", 0),
                    "bgm_file": metadata.get("bgm_file", ""),
                    "subtitle_burned_in": metadata.get("subtitle_burned_in", False),
                },
                content_score=content,
                risk_flags=risks,
                improvement_suggestions=suggestions,
            )
        except Exception as e:
            return QualityReport(
                technical_status=metadata,
                quality_scorer_status="failed",
                quality_scorer_error=str(e)[:200],
            )

    # ── Content Scoring ──────────────────────────────

    def _score_content(self, metadata: dict, script: dict | None) -> ContentScore:
        hook = self._score_hook(metadata, script)
        script_s = self._score_script(metadata, script)
        asset = self._score_asset_match(metadata)
        subtitle = self._score_subtitle(metadata, script)
        bgm = self._score_bgm(metadata)
        pacing = self._score_pacing(metadata)
        commercial = self._score_commercial(metadata, script)
        total = hook + script_s + asset + subtitle + bgm + pacing + commercial

        return ContentScore(
            hook_score=hook,
            script_score=script_s,
            asset_match_score=asset,
            subtitle_score=subtitle,
            bgm_score=bgm,
            pacing_score=pacing,
            commercial_score=commercial,
            total_score=total,
            publish_recommendation=self._recommend(total),
        )

    # ── Individual Scorers ───────────────────────────

    def _score_hook(self, metadata: dict, script: dict | None) -> int:
        """开头钩子 0-20分"""
        score = 10  # baseline
        if not script:
            return score

        scenes = script.get("scenes", [])
        if not scenes:
            return score

        first_text = scenes[0].get("text", "")
        first_mood = scenes[0].get("mood", "")
        first_tags = scenes[0].get("asset_tags", [])

        # Strong hook keywords
        strong_hooks = ["避坑", "懒人", "预算", "免费", "一定要去", "最", "不踩雷",
                        "情侣", "亲子", "闺蜜", "一个人", "不要", "千万别", "必须",
                        "隐藏", "小众", "天花板", "天花板", "醉美", "绝美"]
        medium_hooks = ["攻略", "路线", "打卡", "推荐", "旅行", "玩", "吃", "住",
                        "5天", "7天", "省钱"]

        has_strong = any(h in first_text for h in strong_hooks)
        has_medium = any(h in first_text for h in medium_hooks)
        tags_strong = any(h in ",".join(first_tags) for h in strong_hooks)

        if has_strong or tags_strong:
            score = 18
        elif has_medium:
            score = 14
        elif len(first_text) > 30:
            score = 12

        if first_mood == "开场吸引":
            score = min(20, score + 1)

        return min(20, max(0, score))

    def _score_script(self, metadata: dict, script: dict | None) -> int:
        """文案自然度 0-15分"""
        score = 8
        if not script:
            return score

        scenes = script.get("scenes", [])
        if not scenes:
            return score

        total_chars = sum(len(s.get("text", "")) for s in scenes)
        scene_count = len(scenes)

        # Ideal: 80-200 chars, 3-6 scenes
        if 100 <= total_chars <= 180:
            score = 13
        elif 80 <= total_chars <= 200:
            score = 11
        elif total_chars < 80:
            score = 6
        else:
            score = 10

        # All moods valid → +1
        moods = {s.get("mood", "") for s in scenes}
        valid_moods = {"开场吸引", "轻松惬意", "活力刺激", "神秘探索", "温馨感人", "结尾号召"}
        if moods.issubset(valid_moods) and len(moods) >= 3:
            score = min(15, score + 1)

        return min(15, max(0, score))

    def _score_asset_match(self, metadata: dict) -> int:
        """素材匹配度 0-20分"""
        unique = metadata.get("unique_asset_count", 0)
        dup = metadata.get("duplicate_asset_count", 0)
        total = unique + dup
        scene_count = metadata.get("scene_count", 6)

        if total == 0:
            return 5

        # Ideal: 2-4 unique per scene, minimal dup
        ratio = unique / max(scene_count, 1)
        dup_ratio = dup / max(total, 1)

        if 2 <= ratio <= 4 and dup_ratio <= 0.1:
            return 18
        elif 2 <= ratio <= 5 and dup_ratio <= 0.25:
            return 14
        elif ratio >= 1 and dup_ratio <= 0.4:
            return 10
        else:
            return 6

    def _score_subtitle(self, metadata: dict, script: dict | None) -> int:
        """字幕观感 0-15分"""
        score = 10
        if metadata.get("subtitle_burned_in"):
            score = 13

        # Check for likely traditional Chinese risk
        if script:
            texts = [s.get("text", "") for s in script.get("scenes", [])]
            all_text = "".join(texts)
            if any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in all_text):
                score = min(15, score + 1)

        # If subtitle file exists
        if metadata.get("subtitle_path", ""):
            score = min(15, score + 1)

        return min(15, max(0, score))

    def _score_bgm(self, metadata: dict) -> int:
        """BGM适配 0-10分"""
        bgm = metadata.get("bgm_file", "")

        if not bgm or bgm in ("bgm_dir_missing", "no_real_bgm", "bgm_01.mp3"):
            return 2
        elif bgm.startswith("bgm_"):
            return 4
        else:
            return 9  # Real named BGM

    def _score_pacing(self, metadata: dict) -> int:
        """节奏流畅度 0-10分"""
        duration = metadata.get("duration", 0)

        if 25 <= duration <= 35:
            return 9
        elif 20 <= duration <= 40:
            return 7
        elif 15 <= duration <= 50:
            return 5
        else:
            return 3

    def _score_commercial(self, metadata: dict, script: dict | None) -> int:
        """商业可用性 0-10分"""
        score = 5
        if not script:
            return score

        scenes = script.get("scenes", [])
        all_tags = [t for s in scenes for t in s.get("asset_tags", [])]

        # Has commercial keywords
        commercial_kws = ["攻略", "路线", "预算", "避坑", "推荐", "打卡", "省钱",
                          "必去", "必吃", "必玩", "性价比", "自由行"]
        matches = sum(1 for kw in commercial_kws if any(kw in t for t in all_tags))
        score += min(3, matches)

        # Has title
        if script.get("title", ""):
            score += 1

        # Scene count reasonable
        if 4 <= len(scenes) <= 6:
            score += 1

        return min(10, max(0, score))

    # ── Risk Detection ───────────────────────────────

    def _detect_risks(self, metadata: dict, content: ContentScore, script: dict | None) -> list[str]:
        risks = []

        if content.asset_match_score < 10:
            risks.append("asset_match_too_low")
        if metadata.get("duplicate_asset_count", 0) > 3:
            risks.append("duplicate_assets_high")
        if metadata.get("unique_asset_count", 0) < 5:
            risks.append("too_few_unique_assets")
        if not metadata.get("bgm_file") or metadata.get("bgm_file", "") in ("no_real_bgm", "bgm_01.mp3", "bgm_dir_missing"):
            risks.append("weak_or_missing_bgm")
        if content.hook_score < 12:
            risks.append("weak_hook")
        if content.pacing_score < 5:
            risks.append("pacing_issue")
        if metadata.get("duration", 0) < 15:
            risks.append("duration_too_short")
        if metadata.get("duration", 0) > 50:
            risks.append("duration_too_long")

        return risks

    # ── Suggestions ──────────────────────────────────

    def _generate_suggestions(self, metadata: dict, content: ContentScore, risks: list[str]) -> list[str]:
        suggestions = []

        if "asset_match_too_low" in risks or "duplicate_assets_high" in risks:
            suggestions.append(
                f"素材去重不足：当前 {metadata.get('duplicate_asset_count', 0)} 个重复素材。"
                "建议增加素材多样性或降低 top_n 参数。"
            )
        if "weak_hook" in risks:
            suggestions.append(
                "开头钩子太弱：第一句话应该包含 避坑/预算/天数/目的地 等吸引人的关键词。"
            )
        if "weak_or_missing_bgm" in risks:
            suggestions.append(
                "BGM需改善：当前使用静默BGM或没有BGM。建议在 bgm/ 目录中放入真实的旅行配乐文件。"
            )
        if "duration_too_short" in risks:
            suggestions.append("视频时长过短 (<15s)，增加文案长度或降低语速。")
        if "duration_too_long" in risks:
            suggestions.append("视频时长过长 (>50s)，缩减文案或增加语速。")
        if "pacing_issue" in risks:
            suggestions.append("节奏不够流畅，检查素材时长分布是否合理。")

        if not suggestions:
            suggestions.append("质量合格，可以发布。")

        return suggestions

    # ── Recommendation ───────────────────────────────

    @staticmethod
    def _recommend(total: int) -> str:
        if total >= 80:
            return "recommended"
        elif total >= 70:
            return "needs_review"
        else:
            return "not_recommended"
