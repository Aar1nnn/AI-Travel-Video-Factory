"""
Page 2: 长视频切片工作台
上传长视频 → 镜头检测 → 切片 → 缩略图预览
All UI labels in Chinese.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui_components import inject_css, metric_card, status_badge, json_expander, kpi_row
from ui_components.shared import status_label

inject_css()

# ── Header ──────────────────────────────────────────

st.markdown("### ✂️ 长视频切片工作台")
st.caption("上传长视频文件，自动检测镜头切换并切割为独立素材片段")

# ── Settings ────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
with col1:
    min_clip_duration = st.number_input("最短片段时长（秒）", value=1.0, min_value=0.5, max_value=10.0, step=0.5)
with col2:
    detect_threshold = st.slider("镜头检测灵敏度", 15.0, 50.0, 27.0, 1.0,
        help="数值越低越敏感（产生更多片段），越高越少。")
with col3:
    auto_thumbnail = st.checkbox("自动生成缩略图", value=True)
with col4:
    auto_tag = st.checkbox("自动打标签（CLIP）", value=False,
        help="使用 CLIP 模型对每个片段自动分类（较慢但质量高）")

uploaded = st.file_uploader("选择视频文件", type=["mp4", "mov", "avi", "webm", "mkv"])

st.divider()

# ── Process ─────────────────────────────────────────

if uploaded and st.button("🔪 开始切片", type="primary"):
    # Save to project-local uploads directory
    from datetime import datetime
    uploads_dir = Path("assets/raw/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize filename: keep Chinese chars, remove special chars
    original_name = uploaded.name
    safe_stem = "".join(c for c in Path(original_name).stem if c.isalnum() or '一' <= c <= '鿿' or c in "_-")
    if not safe_stem:
        safe_stem = "video"
    dest_name = f"upload_{ts}_{safe_stem}{Path(original_name).suffix}"
    tmp_video = uploads_dir / dest_name
    tmp_video.write_bytes(uploaded.read())

    st.info(f"文件已保存到素材目录：assets/raw/uploads/{dest_name}（{tmp_video.stat().st_size // (1024*1024):.1f} MB）")

    progress = st.progress(0, text="正在检测镜头...")

    try:
        from src.asset_processor import AssetProcessor

        proc = AssetProcessor(
            raw_dir=uploads_dir,
            processed_dir=Path("assets/processed"),
            thumbnails_dir=Path("assets/thumbnails"),
            index_path=Path("assets/index.json"),
            min_scene_duration=min_clip_duration,
        )

        progress.progress(10, text="正在检测镜头切换...")
        scenes = proc._detect_scenes(tmp_video)

        if not scenes:
            st.warning("未检测到镜头切换。建议降低「镜头检测灵敏度」参数后重试。")
            st.stop()

        progress.progress(30, text=f"检测到 {len(scenes)} 个镜头...")

        # Process video
        records = proc.process_video(tmp_video)

        progress.progress(80, text="处理完成，正在加载预览...")

        # ── Results ──────────────────────────────────

        st.success(f"切片完成！共生成 {len(records)} 个片段")

        if records:
            kpi_row([
                {"label": "生成片段数", "value": len(records), "color": "#4ade80"},
                {"label": "总时长", "value": f"{sum(r.duration or 0 for r in records):.1f}秒"},
                {"label": "平均时长", "value": f"{sum(r.duration or 0 for r in records) / len(records):.1f}秒"},
                {"label": "总文件大小", "value": f"{sum(r.file_size_kb for r in records) // 1024:.0f} MB"},
            ])

        # ── Clip Grid ───────────────────────────────

        st.markdown("#### 🎞️ 片段预览")
        clips_per_row = 4
        for i in range(0, len(records), clips_per_row):
            cols = st.columns(clips_per_row)
            for j in range(clips_per_row):
                idx = i + j
                if idx >= len(records):
                    break
                r = records[idx]
                with cols[j]:
                    thumb = Path("assets/thumbnails") / f"{r.id}.jpg" if auto_thumbnail else None
                    if thumb and thumb.exists():
                        st.image(str(thumb), use_container_width=True)
                    else:
                        st.markdown('<div style="height:120px;background:#1a1a1a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#555">暂无预览</div>', unsafe_allow_html=True)
                    st.caption(f"**{r.id}** | {r.duration:.1f}秒")
                    st.caption(f"{r.resolution} | {r.scene_type}")

        # ── Details ──────────────────────────────────

        st.divider()
        st.markdown("#### 📋 片段详情")
        json_expander("全部片段数据", [r.model_dump() for r in records])

        # Auto-tag option
        if auto_tag and records:
            st.info("正在使用 CLIP 自动打标签...（可能需要几分钟）")
            try:
                from src.auto_tagger import AutoTagger
                tagger = AutoTagger()
                count = tagger.tag_all()
                st.success(f"自动标注完成，共更新 {count} 个素材")
            except Exception as e:
                st.warning(f"自动标注失败：{e}")

    except Exception as e:
        progress.progress(100, text="失败")
        error_msg = str(e)
        # Friendly Chinese error message
        if "relative_to" in error_msg or "subpath" in error_msg:
            st.error("处理失败：上传文件路径异常，已尝试保存到素材目录后重新处理。")
        else:
            st.error(f"处理失败：{error_msg[:200]}")
        with st.expander("🔍 查看详细错误信息"):
            if hasattr(st, 'exception'):
                st.exception(e)
            else:
                st.code(error_msg)

elif uploaded:
    st.info("👆 点击「开始切片」开始分析视频")

else:
    st.info("👆 上传一个长视频文件开始切片")

st.divider()
st.caption("提示：视频先上传到临时目录处理。如需保存到素材库，使用命令行：python main.py --process-assets")
