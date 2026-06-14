"""
Page 1: 视频生成工作台
输入旅游主题 → 生成完整短视频 + KPI 仪表板
All UI labels in Chinese.
"""

import json
import time
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import init_config
from src.pipeline import Pipeline
from ui_components import inject_css, metric_card, status_badge, json_expander, kpi_row
from ui_components.shared import (
    VOICE_DISPLAY_NAMES, DEFAULT_VOICE_DISPLAY, VOICE_DISPLAY_TO_ID,
    DEFAULT_VOICE_ID, status_label, get_voice_preview_path, generate_voice_preview,
)

inject_css()

# ── Header ──────────────────────────────────────────

st.markdown("### 🎬 视频生成工作台")
st.caption("输入旅游主题，自动生成带脚本、配音、字幕、BGM 的竖屏短视频")

col1, col2, col3, col4 = st.columns(4)
with col1:
    topic = st.text_input("旅游主题", value="云南7天6晚情侣游", placeholder="例如：沙巴5天4晚旅游攻略")
with col2:
    voice_display = st.selectbox("选择配音", VOICE_DISPLAY_NAMES, index=0)
    voice_id = VOICE_DISPLAY_TO_ID.get(voice_display, DEFAULT_VOICE_ID)
with col3:
    style = st.selectbox("视频风格", ["快节奏", "舒缓", "文艺"], index=0)
with col4:
    st.write("")
    st.write("")

col_btn1, col_btn2 = st.columns([2, 1])
with col_btn1:
    generate_btn = st.button("🚀 生成视频", type="primary", use_container_width=True)
with col_btn2:
    preview_btn = st.button("🔊 试听声音", use_container_width=True)

# ── Voice Preview ───────────────────────────────────

if preview_btn:
    preview_path = get_voice_preview_path(voice_id)
    if preview_path.exists() and preview_path.stat().st_size > 500:
        st.success(f"正在播放「{voice_display}」试听：")
        st.audio(str(preview_path))
        st.caption("（试听已缓存，再次点击直接播放）")
    else:
        with st.spinner("正在生成试听音频..."):
            result = generate_voice_preview(voice_id)
            if result:
                st.success(f"「{voice_display}」试听：")
                st.audio(str(result))
                st.caption("（试听已缓存，可重复播放）")
            else:
                st.error("试听生成失败，请检查网络连接后重试。")

st.divider()

# ── Generation ──────────────────────────────────────

if generate_btn and topic.strip():
    progress = st.progress(0, text="正在初始化...")
    status_text = st.empty()

    try:
        config = init_config()
        progress.progress(10, text="正在初始化管线...")
        pipeline = Pipeline(config, output_dir=Path("output/temp"), voice_profile=voice_id)

        status_text.info("正在调用大模型生成脚本...")
        progress.progress(20)
        t0 = time.time()

        result = pipeline.run(topic, style=style)
        elapsed = time.time() - t0

        progress.progress(100, text="生成完成！")
        status_text.success(f"视频生成完成！耗时 {elapsed:.0f} 秒")

        # ── Load data ────────────────────────────────

        meta = {}
        if result.metadata_path.exists():
            try: meta = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            except: pass

        script = {}
        script_path = Path("output/temp/script.json")
        if script_path.exists():
            try: script = json.loads(script_path.read_text(encoding="utf-8"))
            except: pass

        # ── KPI Row ──────────────────────────────────

        st.markdown("#### 📊 生成报告")

        qs = meta.get("quality_score", 0) or 0
        rec = meta.get("publish_recommendation", "needs_review")
        rec_label = status_label(rec)
        rec_color = "#4ade80" if rec == "recommended" else "#facc15" if rec == "needs_review" else "#f87171"

        kpi_row([
            {"label": "质量评分", "value": f"{qs}/100", "color": rec_color, "sub": rec_label},
            {"label": "时长", "value": f"{result.duration:.1f}秒", "sub": f"{result.file_size_mb:.1f} MB"},
            {"label": "场景数", "value": result.scene_count, "sub": f"使用 {result.asset_count} 个素材"},
            {"label": "重复素材", "value": meta.get("duplicate_asset_count","?"), "sub": f"来源重复: {meta.get('duplicate_source_video_count','?')}"},
            {"label": "兜底匹配", "value": meta.get("fallback_count","?"), "sub": f"场景多样性: {meta.get('scene_type_diversity','?')}"},
        ])

        # ── Video + Details ──────────────────────────

        col_v, col_d = st.columns([3, 2])

        with col_v:
            st.markdown("#### 📺 最终视频")
            if result.final_video_path.exists():
                st.video(str(result.final_video_path))
                with open(result.final_video_path, "rb") as f:
                    st.download_button("📥 下载视频", f, file_name=result.final_video_path.name, mime="video/mp4")

        with col_d:
            st.markdown("#### ℹ️ 详情信息")
            st.metric("背景音乐", meta.get("bgm_file", "?"))
            st.metric("字幕烧录", "✅ 已烧录" if meta.get("subtitle_burned_in") else "❌ 未烧录")
            st.metric("唯一素材来源", meta.get("unique_source_video_count", "?"))
            risks_raw = meta.get("risk_flags", []) or []
            risks_cn = [status_label(r) for r in risks_raw]
            st.metric("风险标记", "、".join(risks_cn) if risks_cn else "无")
            if meta.get("improvement_suggestions"):
                for s in meta["improvement_suggestions"][:3]:
                    st.caption(f"💡 {s}")

        # ── Expandable Data ──────────────────────────

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            json_expander("📄 生成脚本", script)
        with col_e2:
            json_expander("📋 元数据", meta)

        st.divider()
        st.caption(f"视频路径: {result.final_video_path}")

    except Exception as e:
        progress.progress(100, text="失败")
        msg = str(e)
        if "api_key" in msg.lower() or "credentials" in msg.lower():
            st.error("生成失败：请先在 .env 文件中配置 DEEPSEEK_API_KEY。")
        else:
            st.error(f"生成失败：{e}")
        if hasattr(st, 'exception'):
            st.exception(e)

elif not topic.strip() and generate_btn:
    st.warning("请输入旅游主题")

else:
    st.info("👆 输入主题并点击「生成视频」开始创建视频")

    st.divider()
    st.markdown("""
    ### 💡 使用提示
    - **强钩子开头**：系统会为每条视频自动生成强钩子开头（避坑、省钱、千万别等句式）
    - **七维质量评分**：自动评估 Hook 力度、文案自然度、素材匹配、字幕观感、BGM 适配、节奏流畅度、商业可用性
    - **自动去重**：同一条视频内不会重复使用相同素材片段
    - **完整报告**：生成后的元数据文件包含完整的评分明细和改进建议
    """)
