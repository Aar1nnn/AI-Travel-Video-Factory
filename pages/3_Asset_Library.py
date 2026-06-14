"""
Page 3: Asset Library Browser
Visual dashboard for browsing, filtering, and inspecting the asset library.
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

inject_css()

# ── Load Data ───────────────────────────────────────

@st.cache_data(ttl=30)
def load_assets():
    mgr = AssetLibraryManager(ASSETS_DIR, ASSETS_INDEX)
    records = mgr.get_all_records()
    return [r.model_dump() for r in records]

assets = load_assets()

# ── Header ──────────────────────────────────────────

st.markdown("### 🗂️ 素材库")
st.caption(f"当前索引: {len(assets)} 个素材")

# ── KPI Row ─────────────────────────────────────────

videos = [a for a in assets if a.get("type") == "video"]
images = [a for a in assets if a.get("type") == "image"]
tagged = [a for a in assets if a.get("tags")]
source_ids = set(a.get("source_video_id", a.get("source_video", "")) for a in assets if a.get("source_video_id") or a.get("source_video"))
stypes = set(a.get("scene_type", "general") for a in assets if a.get("scene_type"))
avg_q = sum(a.get("quality_score", 0) or 0 for a in assets) / max(len(assets), 1)

general_pct = sum(1 for a in assets if a.get("scene_type") == "general") / max(len(assets), 1) * 100

kpi_row([
    {"label": "Total Assets", "value": len(assets), "sub": f"{len(videos)} videos, {len(images)} images"},
    {"label": "Tagged", "value": len(tagged), "color": "#4ade80" if len(tagged) / max(len(assets),1) > 0.5 else "#facc15",
     "sub": f"{len(tagged) * 100 // max(len(assets),1)}% coverage"},
    {"label": "Scene Types", "value": len(stypes), "color": "#4ade80" if len(stypes) >= 5 else "#f87171",
     "sub": f"{general_pct:.0f}% general"},
    {"label": "Source Videos", "value": len(source_ids) if source_ids else "N/A"},
    {"label": "Avg Quality", "value": f"{avg_q:.2f}" if avg_q > 0 else "N/A", "color": "#4ade80" if avg_q >= 0.7 else "#facc15"},
])

st.divider()

# ── Filters ─────────────────────────────────────────

all_tags = sorted(set(t for a in assets for t in a.get("tags", [])))
all_scene_types = sorted(set(a.get("scene_type", "general") for a in assets))
all_sources = sorted(set(a.get("source_video_id", a.get("source_video", "")) for a in assets if a.get("source_video_id") or a.get("source_video")))

col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    filter_type = st.selectbox("Media Type", ["all", "video", "image"])
with col_f2:
    filter_st = st.selectbox("Scene Type", ["all"] + list(SceneType.ALL))
with col_f3:
    selected_tags = st.multiselect("Tags", all_tags[:30] if len(all_tags) > 30 else all_tags, placeholder="Select tags...")
with col_f4:
    search_id = st.text_input("Search Asset ID", placeholder="asset_001")

# ── Risk Flags ──────────────────────────────────────

col_r1, col_r2, col_r3 = st.columns(3)
with col_r1:
    show_missing_tags = st.checkbox("⚠️ Missing Tags", value=False)
with col_r2:
    show_low_quality = st.checkbox("⚠️ Low Quality (<0.5)", value=False)
with col_r3:
    show_dup_source = st.checkbox("🔄 Duplicate Source", value=False)

# ── Filter Logic ────────────────────────────────────

filtered = []
for a in assets:
    if filter_type != "all" and a.get("type") != filter_type:
        continue
    if filter_st != "all" and a.get("scene_type") != filter_st:
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

st.caption(f"显示 {len(filtered)} / {len(assets)} 个素材")

# ── Asset Grid ──────────────────────────────────────

if not filtered:
    st.info("没有符合条件的素材。调整筛选条件试试。")
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
                st.caption(f"⏱ {dur:.1f}s | 🏷 {stype}")
                st.caption(f"📹 {svid_short}")

                # Risk indicators
                risks = []
                if not a.get("tags"):
                    risks.append("🏷️")
                if qs and qs < 0.5:
                    risks.append("⭐↓")
                if not a.get("thumbnail"):
                    risks.append("🖼️↓")
                if risks:
                    st.caption(" ".join(risks))

                # Tags
                if tags_str != "-":
                    st.caption(f"`{tags_str}`")

                # Quality bar
                if qs:
                    st.progress(min(float(qs), 1.0), text=f"q={qs:.2f}")

                # Detail expander
                with st.expander("📋", expanded=False):
                    json_expander(aid, a, expanded=True)

    # ── Scene Type Distribution ─────────────────────

    st.divider()
    st.markdown("#### 📊 Scene Type 分布")

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
st.caption("素材库路径: assets/ | 索引: assets/index.json")
