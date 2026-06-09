# Batch Quality Analysis V3

**日期**: 2026-06-09
**数据来源**: output/quality_report.json (20条批量生成)

---

## 1. 总览

| 指标 | 数值 |
|------|------|
| 总生成数量 | 20 |
| 成功数量 | 20 |
| 失败数量 | 0 |
| 成功率 | 100% |
| 平均时长 | 25.4s |
| 平均文件大小 | 9.7 MB |
| 平均唯一素材数 | 13.8 |
| 平均重复素材数 | 3.4 |
| 重复素材比例 | ~20% |
| 字幕烧录成功率 | 20/20 (100%) |
| 使用BGM文件数 | 4个不同文件 |

---

## 2. BGM 使用分布

| BGM文件 | 使用次数 |
|---------|----------|
| leberch-travel-documentary-519393.mp3 | 8 |
| leberch-travel-525093.mp3 | 5 |
| the_mountain-travel-487023.mp3 | 4 |
| bgm_01.mp3 (silent) | 3 |

---

## 3. quality_report.json 已能证明

1. ✅ 系统稳定性: 20/20 全部成功, 无crash
2. ✅ 字幕烧录: 100% 成功率
3. ✅ BGM接入: 4个文件轮换使用
4. ✅ 素材使用: 平均13.8个唯一素材/视频
5. ✅ 输出一致性: 所有视频1080×1920, H.264+AAC
6. ✅ 批量生成可规模化

---

## 4. quality_report.json 不能证明

| 缺失指标 | 说明 |
|----------|------|
| 开头3秒钩子评分 | 无法评估是否吸引观众 |
| 文案自然度评分 | 无法评估AI感 |
| 素材匹配度评分 | 无法评估画面与文案的相关性 |
| 字幕可读性评分 | 无法评估字体/位置/同步是否合理 |
| BGM适配评分 | 无法评估配乐与内容是否协调 |
| 节奏流畅度评分 | 无法评估剪辑节奏 |
| 商业可用性评分 | 无法评估整个视频是否可发布 |
| 总分 (100分制) | 无综合评分 |
| 是否建议发布 | 无人工/自动审核结论 |

---

## 5. 当前报告字段 vs 理想字段

### 已有
```json
{
  "topic": "云南7天6晚情侣游",
  "generation_status": "ok",
  "video_path": "output/temp/...",
  "used_assets_count": 15,
  "duplicate_asset_count": 3,
  "bgm_file": "leberch-travel-documentary-519393.mp3",
  "subtitle_burned_in": true,
  "duration": 30.4,
  "file_size_mb": 12.73
}
```

### 理想
```json
{
  ...以上字段...,
  "hook_score": 15,
  "script_naturalness": 12,
  "asset_match_score": 16,
  "subtitle_readability": 13,
  "bgm_fit_score": 8,
  "rhythm_score": 7,
  "commercial_usability": 8,
  "total_score": 79,
  "pass_threshold_80": false,
  "recommend_publish": false,
  "review_notes": "字幕有繁体字，素材重复较多"
}
```

---

## 6. 结论

**当前质量报告是技术质量报告，不是内容质量报告。**

它能证明系统可以稳定生成视频，但不能证明生成的视频"好看"或"可发布"。

下一步需要 **Quality Scorer V1** 来补充内容质量评分。
