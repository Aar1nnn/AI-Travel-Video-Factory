"""Reusable UI components for AI Travel Video Factory dashboard."""

import json
from pathlib import Path

import streamlit as st


# ── Custom CSS ─────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    /* Dark theme base */
    .stApp {
        background-color: #0c0c0c;
    }
    .main .block-container {
        padding-top: 1rem;
    }

    /* Metric cards */
    .metric-card {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 8px;
    }
    .metric-card .label {
        color: #888;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card .value {
        color: #fff;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-card .sub {
        color: #666;
        font-size: 0.75rem;
    }

    /* Asset cards */
    .asset-card {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        overflow: hidden;
        transition: border-color 0.2s;
    }
    .asset-card:hover {
        border-color: #4a4a4a;
    }
    .asset-card img {
        width: 100%;
        height: 140px;
        object-fit: cover;
    }
    .asset-card .info {
        padding: 10px 12px;
        font-size: 0.78rem;
        color: #ccc;
    }

    /* Status badges */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .badge-ok { background: #0f3a1e; color: #4ade80; }
    .badge-warn { background: #3a2e0f; color: #facc15; }
    .badge-err { background: #3a0f0f; color: #f87171; }

    /* Section dividers */
    .section-title {
        color: #fff;
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* JSON expander */
    .json-panel {
        background: #111;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        padding: 12px;
        font-family: 'SF Mono', 'Consolas', monospace;
        font-size: 0.75rem;
        max-height: 300px;
        overflow-y: auto;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Metric Card ────────────────────────────────────

def metric_card(label: str, value, sub: str = "", color: str = "#fff"):
    st.markdown(f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value" style="color:{color}">{value}</div>
        <div class="sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Status Badge ───────────────────────────────────

def status_badge(status: str):
    badge_class = "badge-ok" if status in ("ok","recommended","recommended✅","success") else \
                  "badge-warn" if status in ("needs_review","warning","processing") else "badge-err"
    st.markdown(f'<span class="badge {badge_class}">{status}</span>', unsafe_allow_html=True)


# ── Asset Card ─────────────────────────────────────

def asset_card(asset: dict, col=None):
    """Render a single asset card with thumbnail and metadata."""
    thumb = asset.get("thumbnail", "")
    asset_id = asset.get("id", "?")
    scene_type = asset.get("scene_type", "general")
    tags = asset.get("tags", [])
    source = asset.get("source_video_id", asset.get("source_video", "?"))
    duration = asset.get("duration", 0) or 0
    quality = asset.get("quality_score", None)

    thumb_path = Path("assets") / thumb if thumb else None
    if thumb_path and thumb_path.exists():
        st.image(str(thumb_path), use_container_width=True)
    else:
        st.markdown('<div style="height:140px;background:#1a1a1a;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#555">no preview</div>', unsafe_allow_html=True)

    tags_str = ", ".join(tags[:3]) if tags else "-"
    st.caption(f"**{asset_id}** | {scene_type}")
    st.caption(f"⏱ {duration:.1f}s | 🏷 {tags_str}")
    if quality:
        st.caption(f"⭐ {quality:.2f}")


# ── JSON Expander ──────────────────────────────────

def json_expander(label: str, data, expanded: bool = False):
    with st.expander(label, expanded=expanded):
        st.json(data)


# ── KPI Row ────────────────────────────────────────

def kpi_row(metrics: list[dict]):
    """Render a row of KPI cards. Each dict: {label, value, sub, color?}"""
    cols = st.columns(len(metrics))
    for i, m in enumerate(metrics):
        with cols[i]:
            metric_card(
                label=m.get("label", ""),
                value=m.get("value", "-"),
                sub=m.get("sub", ""),
                color=m.get("color", "#fff"),
            )


# ── Filter Bar ─────────────────────────────────────

def filter_bar(filters: list[dict]) -> dict:
    """Render a horizontal filter bar. Each dict: {key, label, options, type}.
    Returns dict of selected values."""
    cols = st.columns(len(filters))
    values = {}
    for i, f in enumerate(filters):
        with cols[i]:
            if f.get("type") == "select":
                values[f["key"]] = st.selectbox(f["label"], f.get("options", []), key=f"filter_{f['key']}")
            elif f.get("type") == "multiselect":
                values[f["key"]] = st.multiselect(f["label"], f.get("options", []), key=f"filter_{f['key']}")
    return values
