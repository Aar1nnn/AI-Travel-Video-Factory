# Quality Scorer V1 — 设计文档

**日期**: 2026-06-09
**文件**: `src/quality_scorer.py`

---

## 1. 评分维度

| 维度 | 满分 | 评分方式 | 关键逻辑 |
|------|------|----------|----------|
| hook_score | 20 | 检测开头是否含强钩子关键词 (避坑/预算/情侣/懒人等) | 强钩子=18, 中钩子=14, 无=10 |
| script_score | 15 | 文本长度+ mood多样性 | 100-180字=13, 80-200字=11, mood≥3种+1 |
| asset_match_score | 20 | unique/dup比例 | ratio 2-4 + dup≤10%=18, dup≤25%=14 |
| subtitle_score | 15 | burn-in + 文本存在 | burned=13+1(中文), default=10 |
| bgm_score | 10 | BGM文件质量 | 真实命名BGM=9, bgm_开头的测试=4, 无=2 |
| pacing_score | 10 | 时长范围 | 25-35s=9, 20-40s=7 |
| commercial_score | 10 | 商业关键词+title+场景数 | 含攻略/路线等+3, 有title+1, 4-6场景+1 |

---

## 2. 发布建议规则

| 总分 | 建议 | 含义 |
|------|------|------|
| >= 80 | recommended | 建议发布 |
| 70-79 | needs_review | 需要人工审核 |
| < 70 | not_recommended | 不建议发布 |

---

## 3. 风险标记

| 风险标记 | 触发条件 |
|----------|----------|
| duplicate_assets_high | dup_count > 3 |
| weak_or_missing_bgm | bgm为空或测试文件 |
| weak_hook | hook_score < 12 |
| pacing_issue | pacing_score < 5 |
| duration_too_short | < 15s |
| duration_too_long | > 50s |
| too_few_unique_assets | < 5 |

---

## 4. V1 局限

1. hook_score 基于关键词匹配，不理解语义
2. script_score 只看长度和mood，不评估"是否像真人说话"
3. asset_match_score 只看去重统计，不看"画面是否匹配"
4. subtitle_score 不检测实际字幕内容质量
5. bgm_score 不检测音频适配度
6. 所有评分都是启发式规则，不是AI模型

---

## 5. V2 改进方向

1. 接入 AI 评估 hook 是否吸引人 → LLM评分
2. 素材匹配改用 semantic_score 均值
3. 字幕质量检测繁简体 + 字/场景比例
4. BGM适配检测 tempo 与 scene 节奏匹配
5. 引入人工评分标定 → 校准V2权重
