"""
Page 3: 素材库浏览器
可视化素材库 Dashboard — 浏览、筛选、检查素材。
All UI labels in Chinese.
"""

import json
import sys
from pathlib import Path
from collections import Counter

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.asset_library import AssetLibraryManager, SceneType
from src.config import ASSETS_DIR, ASSETS_INDEX
from ui_components import inject_css, metric_card, status_badge, json_expander, kpi_row, filter_bar
from ui_components.shared import status_label

inject_css()

# ── Load Data ───────────────────────────────────────

@st.cache_data(ttl=30)
def load_assets():
    mgr = AssetLibraryManager(ASSETS_DIR, ASSETS_INDEX)
    records = mgr.get_all_records()
    return [r.model_dump() for r in records]

assets = load_assets()

# ── Header ──────────────────────────────────────────

st.markdown("### 🗂️ 素材库浏览器")
st.caption(f"当前索引中共有 {len(assets)} 个素材")

# ── KPI Row ─────────────────────────────────────────

videos = [a for a in assets if a.get("type") == "video"]
images = [a for a in assets if a.get("type") == "image"]
tagged = [a for a in assets if a.get("tags")]
source_ids = set(a.get("source_video_id", a.get("source_video", "")) for a in assets if a.get("source_video_id") or a.get("source_video"))
stypes = set(a.get("scene_type", "general") for a in assets if a.get("scene_type"))
avg_q = sum(a.get("quality_score", 0) or 0 for a in assets) / max(len(assets), 1)

general_pct = sum(1 for a in assets if a.get("scene_type") == "general") / max(len(assets), 1) * 100

kpi_row([
    {"label": "素材总数", "value": len(assets), "sub": f"{len(videos)} 视频, {len(images)} 图片"},
    {"label": "已标注", "value": len(tagged), "color": "#4ade80" if len(tagged) / max(len(assets),1) > 0.5 else "#facc15",
     "sub": f"覆盖率 {len(tagged) * 100 // max(len(assets),1)}%"},
    {"label": "场景类型", "value": len(stypes), "color": "#4ade80" if len(stypes) >= 5 else "#f87171",
     "sub": f"{general_pct:.0f}% 为通用类型"},
    {"label": "原始视频源", "value": len(source_ids) if source_ids else "暂无"},
    {"label": "平均质量", "value": f"{avg_q:.2f}" if avg_q > 0 else "暂无", "color": "#4ade80" if avg_q >= 0.7 else "#facc15"},
])

st.divider()

# ── Filters ─────────────────────────────────────────

all_tags = sorted(set(t for a in assets for t in a.get("tags", [])))
all_scene_types = sorted(set(a.get("scene_type", "general") for a in assets))
all_sources = sorted(set(a.get("source_video_id", a.get("source_video", "")) for a in assets if a.get("source_video_id") or a.get("source_video")))

col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    filter_type = st.selectbox("媒体类型", ["全部", "video", "image"])
with col_f2:
    filter_st = st.selectbox("场景类型", ["全部"] + list(SceneType.ALL))
with col_f3:
    selected_tags = st.multiselect("标签筛选", all_tags[:30] if len(all_tags) > 30 else all_tags, placeholder="选择标签...")
with col_f4:
    search_id = st.text_input("搜索素材 ID", placeholder="asset_001")

# ── Risk Flags ──────────────────────────────────────

col_r1, col_r2, col_r3 = st.columns(3)
with col_r1:
    show_missing_tags = st.checkbox("⚠️ 缺少标签", value=False)
with col_r2:
    show_low_quality = st.checkbox("⚠️ 质量较低（<0.5）", value=False)
with col_r3:
    show_dup_source = st.checkbox("🔄 来源重复", value=False)

# ── Filter Logic ────────────────────────────────────

filtered = []
for a in assets:
    if filter_type != "全部" and a.get("type") != filter_type:
        continue
    if filter_st != "全部" and a.get("scene_type") != filter_st:
        continue
    if selected_tags and not any(t in a.get("tags", []) for t in selected_tags):
        continue
    if search_id and search_id not in a.get("id", ""):
        continue
    if show_missing_tags and a.get("tags"):
        continue
    if show_low_quality and (a.get("quality_score") or 0) >= 0.5:
        continue
    if show_dup_source:
        svid = a.get("source_video_id", a.get("source_video", ""))
        if not svid or sum(1 for aa in assets if aa.get("source_video_id") == svid) <= 1:
            continue
    filtered.append(a)

st.caption(f"当前显示 {len(filtered)} / {len(assets)} 个素材")

# ── Asset Grid ──────────────────────────────────────

if not filtered:
    st.info("没有符合条件的素材，请调整筛选条件重试。")
else:
    cols_per_row = 4
    for i in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx >= len(filtered):
                break
            a = filtered[idx]
            with cols[j]:
                # Thumbnail
                thumb = a.get("thumbnail", "")
                thumb_path = ASSETS_DIR / thumb if thumb else None
                if thumb_path and thumb_path.exists():
                    st.image(str(thumb_path), use_container_width=True)
                else:
                    st.markdown(f'<div style="height:120px;background:#1a1a1a;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#555">{a.get("id","?")}</div>', unsafe_allow_html=True)

                # Info
                aid = a.get("id", "?")
                stype = a.get("scene_type", "general")
                tags_str = ", ".join(a.get("tags", [])[:3]) or "-"
                dur = a.get("duration", 0) or 0
                qs = a.get("quality_score")
                svid = a.get("source_video_id", a.get("source_video", "?"))
                svid_short = (svid or "?")[:25]

                st.caption(f"**{aid}**")
                st.caption(f"⏱ {dur:.1f}秒 | 🏷 {stype}")
                st.caption(f"📹 {svid_short}")

                # Risk indicators
                risks = []
                if not a.get("tags"):
                    risks.append("🏷️缺少标签")
                if qs and qs < 0.5:
                    risks.append("⭐质量低")
                if not a.get("thumbnail"):
                    risks.append("🖼️缺少缩略图")
                if risks:
                    st.caption(" ".join(risks))

                # Tags
                if tags_str != "-":
                    st.caption(f"`{tags_str}`")

                # Quality bar
                if qs:
                    st.progress(min(float(qs), 1.0), text=f"质量分={qs:.2f}")

                # Detail expander
                with st.expander("📋 查看详情", expanded=False):
                    json_expander(aid, a, expanded=True)

    # ── Scene Type Distribution ─────────────────────

    st.divider()
    st.markdown("#### 📊 场景类型分布")

    st_type_counts = Counter(a.get("scene_type", "general") for a in filtered)
    st.bar_chart(dict(st_type_counts.most_common(15)), horizontal=True)

    # ── Tag Cloud ───────────────────────────────────

    st.markdown("#### ☁️ 标签云")

    tag_counts = Counter(t for a in filtered for t in a.get("tags", []))
    top_tags = tag_counts.most_common(30)
    if top_tags:
        tag_html = " ".join(
            f'<span style="font-size:{max(0.7, min(2.0, c*0.25))}rem;color:#ccc;margin:4px;display:inline-block">{t}</span>'
            for t, c in top_tags
        )
        st.markdown(f'<div style="line-height:2.5">{tag_html}</div>', unsafe_allow_html=True)
    else:
        st.caption("暂无标签数据")

st.divider()
st.caption("素材库路径：assets/ ｜ 索引文件：assets/index.json")
