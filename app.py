"""
AI Travel Video Factory — Dashboard

Streamlit 多页 Dashboard 入口。

Usage:
    streamlit run app.py

Pages:
    1. 视频生成 — 输入主题 → 生成完整短视频
    2. 长视频切片 — 上传长视频 → 镜头检测 → 切片
    3. 素材库浏览器 — 浏览、筛选、检查素材库
"""

import sys
from pathlib import Path

# Ensure project root in Python path BEFORE any other imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

# ── Page Config ─────────────────────────────────────

st.set_page_config(
    page_title="AI 旅游视频工厂",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar Navigation ──────────────────────────────

st.sidebar.markdown("""
<div style="padding: 12px 0; text-align: center;">
    <h1 style="font-size: 1.6rem; margin: 0;">🎬 AI 旅游视频工厂</h1>
    <p style="color: #888; font-size: 0.8rem; margin: 4px 0;">作品集展示面板</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

# Navigation using st.navigation
pages = {
    "🎬 视频生成": [
        st.Page("pages/1_Video_Generator.py", title="视频生成工作台", icon="🎬"),
    ],
    "✂️ 素材处理": [
        st.Page("pages/2_Asset_Processor.py", title="长视频切片工作台", icon="✂️"),
    ],
    "🗂️ 素材库": [
        st.Page("pages/3_Asset_Library.py", title="素材库浏览器", icon="🗂️"),
    ],
}

nav = st.navigation(pages)
nav.run()

# ── Sidebar Footer ──────────────────────────────────

st.sidebar.divider()
st.sidebar.caption("AI 旅游视频工厂 v3")
st.sidebar.caption("Streamlit Dashboard 版")
st.sidebar.caption("[命令行: python main.py --help]")

# Quick status
try:
    from src.config import ASSETS_INDEX, BGM_DIR
    import json
    idx = json.loads(ASSETS_INDEX.read_text(encoding="utf-8"))
    bgm_count = len([f for f in BGM_DIR.glob("*") if f.suffix.lower() in (".mp3", ".wav") and f.stat().st_size > 10000])
    st.sidebar.metric("素材库", f"{len(idx)} 个素材")
    st.sidebar.metric("背景音乐", f"{bgm_count} 首")
except Exception:
    pass
