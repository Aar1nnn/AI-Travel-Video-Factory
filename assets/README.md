# assets/ — 素材目录

请自行添加拥有版权或可商用授权的视频和图片素材。

## 目录结构

```
assets/
├── index.json        # 素材索引（自动生成）
├── raw/              # 原始素材 → --process-assets
├── processed/        # 处理后片段（自动生成）
├── thumbnails/       # 缩略图（自动生成）
└── embeddings/       # CLIP embeddings（自动生成）
```

## 快速开始

1. 将你的视频放入 `raw/` 目录
2. 运行 `python main.py --scan-assets` 生成索引
3. 运行 `python main.py --process-assets` 自动切镜头
4. 运行 `python main.py --auto-tag` 自动标注标签
