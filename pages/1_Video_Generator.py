"""
Page 1: Video Generation Dashboard
Generate travel videos from topic input with full KPI reporting.
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


inject_css()

# ── Header ──────────────────────────────────────────

st.markdown("### 🎬 视频生成")
st.caption("输入旅游主题，自动生成带脚本、配音、字幕、BGM 的竖屏短视频")

col1, col2, col3, col4 = st.columns(4)
with col1:
    topic = st.text_input("旅游主题", value="云南7天6晚情侣游", placeholder="例如: 沙巴5天4晚旅游攻略")
with col2:
    voice = st.selectbox("配音音色", ["travel_female","travel_male","story_female","story_male","energetic_female"], index=0)
with col3:
    style = st.selectbox("视频风格", ["快节奏","舒缓","文艺"], index=0)
with col4:
    st.write("")
    st.write("")
    generate_btn = st.button("🚀 生成视频", type="primary", use_container_width=True)

st.divider()

# ── Generation ──────────────────────────────────────

if generate_btn and topic.strip():
    progress = st.progress(0, text="初始化...")
    status_text = st.empty()

    try:
        config = init_config()
        progress.progress(10, text="初始化 Pipeline...")
        pipeline = Pipeline(config, output_dir=Path("output/temp"), voice_profile=voice)

        status_text.info("正在调用 LLM 生成脚本...")
        progress.progress(20)
        t0 = time.time()

        result = pipeline.run(topic, style=style)
        elapsed = time.time() - t0

        progress.progress(100, text="完成!")
        status_text.success(f"生成完成! 耗时 {elapsed:.0f}s")

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
        rec_color = "#4ade80" if rec == "recommended" else "#facc15" if rec == "needs_review" else "#f87171"

        kpi_row([
            {"label": "Quality Score", "value": f"{qs}/100", "color": rec_color, "sub": rec},
            {"label": "Duration", "value": f"{result.duration:.1f}s", "sub": f"{result.file_size_mb:.1f} MB"},
            {"label": "Scenes", "value": result.scene_count, "sub": f"{result.asset_count} assets"},
            {"label": "Dup Assets", "value": meta.get("duplicate_asset_count","?"), "sub": f"source_dup: {meta.get('duplicate_source_video_count','?')}"},
            {"label": "Fallback", "value": meta.get("fallback_count","?"), "sub": f"diversity: {meta.get('scene_type_diversity','?')}"},
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
            st.markdown("#### ℹ️ 详情")
            st.metric("BGM", meta.get("bgm_file", "?"))
            st.metric("Subtitle Burned", "✅" if meta.get("subtitle_burned_in") else "❌")
            st.metric("Unique Sources", meta.get("unique_source_video_count", "?"))
            st.metric("Risks", ", ".join(meta.get("risk_flags", [])) or "none")
            if meta.get("improvement_suggestions"):
                for s in meta["improvement_suggestions"][:3]:
                    st.caption(f"💡 {s}")

        # ── Expandable Data ──────────────────────────

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            json_expander("📄 Script", script)
        with col_e2:
            json_expander("📋 Metadata", meta)

        st.divider()
        st.caption(f"Video: {result.final_video_path}")

    except Exception as e:
        progress.progress(100, text="失败")
        st.error(f"生成失败: {e}")
        if hasattr(st, 'exception'):
            st.exception(e)

elif not topic.strip() and generate_btn:
    st.warning("请输入旅游主题")

else:
    st.info("👆 输入主题并点击生成按钮开始创建视频")

    st.divider()
    st.markdown("""
    ### 💡 提示
    - **强Hook**: 系统会为每个视频生成强钩子开头（避坑/省钱/千万别）
    - **7维评分**: 自动评估 Hook、文案、素材、字幕、BGM、节奏、商业可用性
    - **去重保证**: 同一条视频内不会重复使用相同素材
    - **质量报告**: 生成后的 metadata.json 包含完整的评分卡
    """)
