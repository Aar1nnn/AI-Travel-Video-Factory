"""
AI Travel Video Factory — Streamlit Demo UI

Usage:
    streamlit run app.py

Requirements:
    pip install streamlit
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import init_config
from src.pipeline import Pipeline

# ── Page Config ──────────────────────────────────

st.set_page_config(
    page_title="AI Travel Video Factory",
    page_icon="🎬",
    layout="wide",
)

# ── Title ────────────────────────────────────────

st.title("🎬 AI Travel Video Factory")
st.caption("输入旅游主题，自动生成竖屏短视频 — Streamlit Demo")

# ── Sidebar: Inputs ──────────────────────────────

with st.sidebar:
    st.header("⚙️ 生成设置")

    topic = st.text_input(
        "旅游主题",
        value="云南7天6晚情侣游",
        placeholder="例如: 沙巴5天4晚旅游攻略",
    )

    voice = st.selectbox(
        "配音音色",
        options=["travel_female", "travel_male", "story_female", "story_male", "energetic_female"],
        index=0,
    )

    style = st.selectbox(
        "视频风格",
        options=["快节奏", "舒缓", "文艺"],
        index=0,
    )

    generate_btn = st.button("🚀 生成视频", type="primary", use_container_width=True)

    st.divider()

    st.header("📊 项目状态")
    # Check asset count
    try:
        from src.config import ASSETS_INDEX
        idx = json.loads(ASSETS_INDEX.read_text(encoding="utf-8"))
        st.metric("素材库", f"{len(idx)} 个")
    except Exception:
        st.metric("素材库", "N/A")

    # Show BGM count
    from src.config import BGM_DIR
    bgm_files = [f for f in BGM_DIR.glob("*") if f.suffix.lower() in (".mp3", ".wav") and f.stat().st_size > 1000]
    st.metric("BGM", f"{len(bgm_files)} 首")

    st.divider()
    st.caption("AI Travel Video Factory v3")
    st.caption("[docs/](docs/) · [experiments/](experiments/)")

# ── Main Area: Results ───────────────────────────

if generate_btn:
    if not topic.strip():
        st.error("请输入旅游主题")
    else:
        # Progress
        progress = st.progress(0, text="初始化...")
        status = st.empty()

        try:
            # Init
            progress.progress(5, text="加载配置...")
            config = init_config()

            progress.progress(10, text="初始化 Pipeline...")
            pipeline = Pipeline(
                config,
                output_dir=Path("output/temp"),
                voice_profile=voice,
            )

            # Generate
            progress.progress(20, text="生成脚本...")
            status.info("Step 1/6: 正在调用 LLM 生成脚本...")
            t0 = time.time()

            result = pipeline.run(topic, style=style)
            elapsed = time.time() - t0

            progress.progress(100, text="完成!")
            status.success(f"生成完成! 耗时 {elapsed:.0f}s")

            # Load metadata
            meta = {}
            if result.metadata_path.exists():
                try:
                    meta = json.loads(result.metadata_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            # Load script
            script = {}
            script_path = Path("output/temp/script.json")
            if script_path.exists():
                try:
                    script = json.loads(script_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            # ── Display Results ─────────────────────

            col1, col2 = st.columns([3, 2])

            with col1:
                st.subheader("📺 最终视频")

                video_path = result.final_video_path
                if video_path.exists():
                    st.video(str(video_path))

                    # Download button
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label="📥 下载视频",
                            data=f,
                            file_name=video_path.name,
                            mime="video/mp4",
                        )
                else:
                    st.warning("视频文件未找到")

            with col2:
                st.subheader("📈 质量评分")

                qs = meta.get("quality_score", "N/A")
                rec = meta.get("publish_recommendation", "N/A")

                if qs and qs != "N/A":
                    if qs >= 80:
                        st.success(f"总分: {qs}/100 — **{rec}** ✅")
                    elif qs >= 70:
                        st.warning(f"总分: {qs}/100 — **{rec}** ⚠️")
                    else:
                        st.error(f"总分: {qs}/100 — **{rec}** ❌")
                else:
                    st.info("质量评分: 未生成")

                # Metrics
                st.metric("时长", f"{result.duration:.1f}s")
                st.metric("场景数", result.scene_count)
                st.metric("素材数", result.asset_count)
                st.metric("文件大小", f"{result.file_size_mb:.1f} MB")

                if meta:
                    st.metric("唯一素材", meta.get("unique_asset_count", "N/A"))
                    st.metric("重复素材", meta.get("duplicate_asset_count", "N/A"))
                    bgm_name = meta.get("bgm_file", "N/A")
                    st.metric("BGM", bgm_name)
                    st.metric("字幕烧录", "✅" if meta.get("subtitle_burned_in") else "❌")

                # Risk flags
                risks = meta.get("risk_flags", [])
                if risks:
                    st.caption("⚠️ 风险标记: " + ", ".join(risks))

            # ── Expandable Details ──────────────────

            with st.expander("📄 脚本内容 (script.json)"):
                if script:
                    st.json(script)
                else:
                    st.caption("暂无")

            with st.expander("📋 元数据 (metadata.json)"):
                if meta:
                    st.json(meta)
                else:
                    st.caption("暂无")

            with st.expander("📁 输出文件"):
                output_files = list(Path("output/temp").glob(f"*{datetime.now().strftime('%Y%m%d')}*"))
                for f in sorted(output_files)[-10:]:
                    st.text(f"  {f.name} ({f.stat().st_size // 1024} KB)")

        except Exception as e:
            progress.progress(100, text="失败")
            st.error(f"生成失败: {e}")
            st.exception(e)

# ── Empty State ──────────────────────────────────

else:
    st.info("👈 在左侧输入主题并点击生成按钮")

    st.divider()
    st.subheader("📖 使用说明")

    st.markdown("""
    1. **输入旅游主题** — 例如 "云南7天6晚情侣游"
    2. **选择配音音色** — 5 种 Edge TTS 音色可选
    3. **选择视频风格** — 快节奏/舒缓/文艺
    4. **点击生成** — 等待约 30-45 秒

    ### 命令行版本

    ```bash
    # 单条视频
    python main.py "云南7天6晚情侣游" --voice travel_female

    # 批量验证
    python main.py --batch-demo 20
    ```

    ### 输出文件

    ```
    output/temp/{topic}_{date}.mp4        # 最终视频
    output/temp/{topic}_{date}.json       # 元数据 + 质量评分
    output/temp/{topic}_{date}.srt        # 字幕文件
    output/temp/{topic}_{date}_script.json # 脚本
    ```

    ### 技术文档

    完整架构文档见 [docs/](docs/) 目录。
    """)

# ── Footer ───────────────────────────────────────

st.divider()
st.caption(
    f"AI Travel Video Factory v3 · Streamlit Demo · "
    f"Python 3.14 · FFmpeg 8.1.1 · DeepSeek · Edge TTS · Whisper · CLIP"
)
