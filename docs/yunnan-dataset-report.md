# 云南素材库 — 数据集报告

**日期**: 2026-06-08
**处理工具**: Asset Processor V2 + Auto Tagger V2

---

## 1. 原始素材

| 指标 | 数值 |
|------|------|
| 原始视频数量 | 24 |
| 总时长 | 5668s (94.5 min) |
| 总大小 | 11.31 GB |
| 分辨率 | 4K (3840x2160) 为主 |

## 2. 处理结果

| 指标 | 数值 |
|------|------|
| 检测到的 scene 总数 | 94 |
| 实际生成的 clip 数量 | 94 |
| 生成的 thumbnail 数量 | 93 |
| index.json 总记录数 | 101 |
| Clip 总时长 | 1142s (19.0 min) |
| Clip 时长范围 | 1.0s - 72.6s |
| 平均 clip 时长 | 12.1s |

## 3. Scene Type 分布

| Scene Type | 数量 |
|------------|------|
| general | 55 |
| sunset | 11 |
| transport | 8 |
| lake | 7 |
| landscape | 7 |
| mountain | 3 |
| night | 2 |
| wildlife | 1 |

**问题**: 55 个 clip (58%) scene_type 为 general — 新处理的视频未运行 auto-tag。

## 4. 分辨率 & 方向

| 分辨率 | 数量 |
|--------|------|
| 3840x2160 (4K横屏) | 93 |
| 未知 | 1 |

横屏: 93, 竖屏: 0

**注意**: 所有素材均为横屏 4K。竖屏视频生成时 FFmpeg 会做 scale+crop 自动适配。

## 5. 标签 Top 30 (部分乱码 — 编码问题)

中文标签存储正常，但控制台输出乱码。实际标签包括：
山景、湖景、全景、市场、丽江、大理、俯瞰、夕阳、夜景、Vlog、蓝天、洱海、玉龙雪山、公路、雪山等。

## 6. 待改进

1. 58% clip 为 "general" — 需运行 `--auto-tag` 补全
2. 平均 clip 时长 12.1s — 偏长，建议调 ContentDetector threshold
3. 没有 quality_score — 需运行 V2 compute_quality_score
4. 素材全部横屏 — 后续建议收集竖屏素材
