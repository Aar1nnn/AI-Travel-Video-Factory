# V4 Quality Scorer — 变更报告

**日期**: 2026-06-09
**分支**: `v4-quality-scorer`

---

## 1. 修改文件

| 文件 | 变更 |
|------|------|
| `src/quality_scorer.py` | **新增** — QualityScorer类, 7维度评分, 发布建议, 风险标记 |
| `src/pipeline.py` | 新增 QualityScorer 导入, Step 7 质量评分, Export挪到评分后 |
| `main.py` | batch_demo 增加 quality_score/publish_recommendation/risk_flags 字段到 quality_report.json |
| `.gitignore` | 新增 experiments output, huggingface cache, raw_downloads |
| `docs/quality_scorer_v1.md` | **新增** — 评分维度设计文档 |

## 2. 新增字段 (quality_report.json)

| 字段 | 类型 | 说明 |
|------|------|------|
| quality_score | int | 0-100 总分 |
| publish_recommendation | str | recommended / needs_review / not_recommended |
| risk_flags | list | 风险标记 |
| improvement_suggestions | list | 改进建议 |

## 3. 输出文件

每条视频额外输出:
- `{topic}_{date}_quality.json` — 完整评分卡

## 4. 测试结果

- 单条测试: 80/100 (recommended)
- batch-demo 5: 5/5 成功
- 评分分布: 2 recommended, 1 needs_review, 2 not_recommended
- 核心测试: 29 passed

## 5. 已知风险

1. V1 评分是启发式规则，不是AI模型
2. 评分可能偏高 (baseline给分较高)
3. 后续需要人工标定来校准权重
