"""
Page 2: Asset Processor — Long Video Clip Splitter
Upload long videos, detect scenes, generate clips and thumbnails.
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

inject_css()

# ── Header ──────────────────────────────────────────

st.markdown("### ✂️ 长视频切片")
st.caption("上传长视频文件，自动检测镜头切换并切割为独立素材")

# ── Settings ────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
with col1:
    min_clip_duration = st.number_input("Min Clip Duration (s)", value=1.0, min_value=0.5, max_value=10.0, step=0.5)
with col2:
    detect_threshold = st.slider("Scene Threshold", 15.0, 50.0, 27.0, 1.0,
        help="Lower = more sensitive (more clips). Higher = fewer clips.")
with col3:
    auto_thumbnail = st.checkbox("Auto Thumbnail", value=True)
with col4:
    auto_tag = st.checkbox("Auto Tag (CLIP)", value=False,
        help="Use CLIP to auto-classify each clip (slower but high quality)")

uploaded = st.file_uploader("选择视频文件", type=["mp4", "mov", "avi", "webm", "mkv"])

st.divider()

# ── Process ─────────────────────────────────────────

if uploaded and st.button("🔪 处理视频", type="primary"):
    # Save uploaded file to temp
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_video = tmp_dir / uploaded.name
    tmp_video.write_bytes(uploaded.read())

    st.info(f"文件已上传: {uploaded.name} ({tmp_video.stat().st_size // (1024*1024):.1f} MB)")

    progress = st.progress(0, text="检测镜头...")

    try:
        from src.asset_processor import AssetProcessor

        proc = AssetProcessor(
            raw_dir=tmp_dir,
            processed_dir=tmp_dir / "processed",
            thumbnails_dir=tmp_dir / "thumbnails",
            index_path=tmp_dir / "index.json",
            min_scene_duration=min_clip_duration,
        )

        # Override scene detection threshold
        progress.progress(10, text="检测镜头切换...")
        scenes = proc._detect_scenes(tmp_video)

        if not scenes:
            st.warning("未检测到镜头切换。尝试降低 Scene Threshold 参数。")
            st.stop()

        progress.progress(30, text=f"检测到 {len(scenes)} 个镜头...")

        # Process video
        records = proc.process_video(tmp_video)

        progress.progress(80, text="处理完成，加载预览...")

        # ── Results ──────────────────────────────────

        st.success(f"处理完成! {len(records)} 个片段")

        if records:
            kpi_row([
                {"label": "Clips Generated", "value": len(records), "color": "#4ade80"},
                {"label": "Total Duration", "value": f"{sum(r.duration or 0 for r in records):.1f}s"},
                {"label": "Avg Duration", "value": f"{sum(r.duration or 0 for r in records) / len(records):.1f}s"},
                {"label": "Total Size", "value": f"{sum(r.file_size_kb for r in records) // 1024:.0f} MB"},
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
                    thumb = tmp_dir / "thumbnails" / f"{r.id}.jpg" if auto_thumbnail else None
                    if thumb and thumb.exists():
                        st.image(str(thumb), use_container_width=True)
                    else:
                        st.markdown('<div style="height:120px;background:#1a1a1a;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#555">no preview</div>', unsafe_allow_html=True)
                    st.caption(f"**{r.id}** | {r.duration:.1f}s")
                    st.caption(f"{r.resolution} | {r.scene_type}")

        # ── Details ──────────────────────────────────

        st.divider()
        st.markdown("#### 📋 片段详情")
        json_expander("All Clips", [r.model_dump() for r in records])

        # Auto-tag option
        if auto_tag and records:
            st.info("Auto-tagging with CLIP... (this may take a few minutes)")
            try:
                from src.auto_tagger import AutoTagger
                tagger = AutoTagger()
                count = tagger.tag_all()
                st.success(f"Auto-tagged {count} assets")
            except Exception as e:
                st.warning(f"Auto-tagging failed: {e}")

    except Exception as e:
        progress.progress(100, text="失败")
        st.error(f"处理失败: {e}")
        if hasattr(st, 'exception'):
            st.exception(e)

elif uploaded:
    st.info("👆 点击「处理视频」开始分析")

else:
    st.info("👆 上传一个长视频文件开始切片")

st.divider()
st.caption("提示: 视频先上传到临时目录处理。如需保存到素材库，使用命令行: python main.py --process-assets")
