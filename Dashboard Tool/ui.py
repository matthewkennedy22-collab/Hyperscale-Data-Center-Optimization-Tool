"""Shared UI components, CSS, and Plotly chart styling for the dashboard."""
import streamlit as st

# Plotly layout defaults: legend on the right so it doesn't block axis labels
PLOTLY_LAYOUT = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(248,250,252,0.8)",
    margin=dict(l=60, r=160, t=50, b=80),
    hovermode="x unified",
    showlegend=True,
    legend=dict(
        orientation="v",
        x=1.02,
        y=1,
        xanchor="left",
        yanchor="top",
        bgcolor="rgba(255,255,255,0.8)",
        font=dict(size=11),
    ),
    xaxis=dict(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.06)", zeroline=False),
    yaxis=dict(showgrid=True, gridwidth=1, gridcolor="rgba(0,0,0,0.06)", zeroline=False),
    height=380,
)
# Distinct hues so counties are easy to tell apart (blue, orange, green, red, purple, brown)
PLOTLY_COLORWAY = [
    "#0e7490",   # teal
    "#ea580c",   # orange
    "#059669",   # emerald
    "#dc2626",   # red
    "#7c3aed",   # violet
    "#b45309",   # amber/brown
]

# App-wide: color = location (county), pattern/symbol = system. Use same convention on every chart.
# AE = solid fill / circle; WEC = striped fill / square.
SYSTEM_PATTERN_MAP = {"AE": "", "WEC": "/"}   # bar charts: solid vs diagonal stripes
SYSTEM_SYMBOL_MAP = {"AE": "circle", "WEC": "square"}   # scatter: circle vs square


def apply_global_css():
    """Inject custom CSS for cards, sections, and polish. Hide the injection block so CSS is not shown as text."""
    # Hide markdown blocks that contain a <style> tag so our CSS isn't shown as text. Styles still apply.
    st.markdown(
        "<style>div[data-testid='stMarkdown']:has(style), .stMarkdown:has(style) { display: none !important; }</style>",
        unsafe_allow_html=True,
    )
    _raw = """
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
    :root {
        --accent: #0e7490;
        --accent-dark: #0c636d;
        --accent-light: #5eead4;
        --surface: #ffffff;
        --surface-elevated: #f8fafc;
        --border: #e2e8f0;
        --border-strong: #cbd5e1;
        --text: #0f172a;
        --text-muted: #64748b;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04);
        --shadow-lg: 0 10px 25px rgba(0,0,0,0.08), 0 4px 10px rgba(14,116,144,0.12);
        --radius: 12px;
        --radius-sm: 10px;
    }
    
    /* Base: one consistent background (no white bar between sidebar and main) */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main, section[data-testid="stVerticalBlockBorderWrapper"] {
        background: #f1f5f9 !important;
    }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; background: transparent !important; }
    .stMarkdown, .stMarkdown p, [data-testid="stMarkdown"] { font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important; }
    
    /* Section cards: elevated, clear hierarchy */
    .dashboard-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .dashboard-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.07); border-color: var(--border-strong); }
    .dashboard-card h3 { margin-top: 0; color: var(--text); font-size: 1.1rem; font-weight: 600; }
    
    /* Metric boxes: accent bar, clearer elevation */
    .metric-box {
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 3px solid var(--accent);
        border-radius: var(--radius-sm);
        padding: 0.5rem 0.75rem;
        text-align: center;
        box-shadow: var(--shadow-sm);
        width: 100%;
        min-height: 5rem;
        height: 5rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .metric-box:hover { box-shadow: var(--shadow-md); border-color: var(--border-strong); border-left-color: var(--accent-dark); }
    .metric-box .value {
        font-weight: 700;
        color: var(--accent);
        font-size: clamp(0.6rem, 1.1vw, 0.9rem);
        line-height: 1.25;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        line-clamp: 2;
        max-width: 100%;
        word-break: break-word;
    }
    .metric-box .label {
        font-size: clamp(0.55rem, 1vw, 0.7rem);
        color: var(--text-muted);
        margin-top: 0.15rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 100%;
    }
    
    /* Hero: richer gradient and depth */
    .hero {
        background: linear-gradient(135deg, #0e7490 0%, #0c636d 50%, #155e75 100%);
        color: white;
        border-radius: var(--radius);
        padding: 2rem 2.25rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-lg);
        border: 1px solid rgba(255,255,255,0.08);
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: radial-gradient(ellipse 80% 50% at 100% 0%, rgba(255,255,255,0.06) 0%, transparent 50%);
        pointer-events: none;
    }
    .hero h1 { color: white !important; margin-bottom: 0.35rem !important; font-weight: 700 !important; letter-spacing: -0.02em; }
    .hero p { color: rgba(255,255,255,0.92) !important; margin: 0 !important; font-size: 0.95rem; }
    
    /* Nav cards: accent on hover, clearer clickability */
    .nav-card {
        display: block;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 1rem 1.25rem;
        text-decoration: none;
        color: var(--text);
        transition: all 0.2s ease;
        margin-bottom: 0.75rem;
        box-shadow: var(--shadow-sm);
    }
    .nav-card:hover {
        border-color: var(--accent);
        color: var(--accent);
        box-shadow: 0 4px 12px rgba(14,116,144,0.18);
        transform: translateY(-1px);
    }
    .nav-card .title { font-weight: 600; font-size: 0.95rem; }
    .nav-card .desc { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; }
    
    /* Section headers: thicker accent, spacing */
    .section-header {
        border-left: 4px solid var(--accent);
        padding-left: 1rem;
        margin: 1.5rem 0 0.75rem 0;
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text);
    }
    
    /* Sidebar: same base as main so no white bar; subtle border */
    [data-testid="stSidebar"] {
        background: #f1f5f9 !important;
        min-width: 220px;
        border-right: 1px solid var(--border);
        box-shadow: 2px 0 12px rgba(0,0,0,0.04);
    }
    [data-testid="stSidebar"] .stSelectbox label { font-weight: 500; }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] p,
    [data-testid="stSidebar"] label { word-wrap: break-word; overflow-wrap: break-word; white-space: normal !important; }
    
    /* Expanders and inputs: align with card look */
    [data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        box-shadow: var(--shadow-sm);
    }
    
    /* Info/warning/success boxes */
    [data-testid="stAlert"] div,
    [data-testid="stAlert"] p { word-wrap: break-word; overflow-wrap: break-word; white-space: normal !important; overflow: visible !important; }
    [data-testid="stAlert"] { min-height: auto; padding: 0.75rem 1rem; border-radius: var(--radius-sm); }
    
    /* Tabs: clearer active state and spacing */
    [data-testid="stTabs"] {
        border-bottom: 2px solid var(--border);
        margin-bottom: 0.5rem;
    }
    [data-testid="stTabs"] button {
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.6rem 1.25rem !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0.25rem; }
    
    /* Buttons: slight depth */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.2s ease, transform 0.1s ease;
    }
    .stButton > button:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    
    footer { visibility: hidden; }
    </style>
    """
    # Escape underscores so Streamlit markdown doesn't treat them as emphasis (which would break the style block)
    st.markdown(_raw.replace("_", "\\_"), unsafe_allow_html=True)


def metric_row(metrics: list[tuple[str, str]]):
    """Render a row of metric (value, label) tuples in columns."""
    cols = st.columns(len(metrics))
    for i, (value, label) in enumerate(metrics):
        with cols[i]:
            st.markdown(
                f'<div class="metric-box"><div class="value">{value}</div><div class="label">{label}</div></div>',
                unsafe_allow_html=True,
            )


def apply_chart_theme(fig, height=None):
    """Apply consistent layout and colorway to a Plotly figure."""
    fig.update_layout(**{**PLOTLY_LAYOUT, "height": height or PLOTLY_LAYOUT["height"]})
    if hasattr(fig, "layout") and fig.layout.colorway is None:
        fig.update_layout(colorway=PLOTLY_COLORWAY)
    return fig


def section_header(title: str, caption: str = None):
    """Emit a styled section header and optional caption."""
    st.markdown(f'<p class="section-header">{title}</p>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def page_top_anchor():
    """Call once at the top of each page so 'Back to top' can link here. In-flow invisible anchor."""
    st.markdown(
        '<div id="page-top" style="height:0;overflow:hidden;margin:0;padding:0;border:0;" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def back_to_top_button():
    """Render a 'Back to top' link at the bottom of the page only when the page is scrollable. Links to #page-top."""
    html = """
    <div id="back-to-top-wrap" style="text-align: center; margin: 1.5rem 0 2rem 0; visibility: hidden;">
        <a href="#page-top" style="
            display: inline-block;
            padding: 0.5rem 1rem;
            font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
            font-size: 0.875rem;
            font-weight: 600;
            color: #0e7490;
            background: #f0f9ff;
            border: 1px solid #0e7490;
            border-radius: 8px;
            text-decoration: none;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        ">↑ Back to top</a>
    </div>
    <script>
    (function() {
        function isPageScrollable() {
            var el = document.querySelector("[data-testid='stAppViewContainer']");
            if (el && el.scrollHeight > el.clientHeight) return true;
            var root = document.documentElement;
            var body = document.body;
            var sh = Math.max(root.scrollHeight, body.scrollHeight);
            var ch = window.innerHeight || root.clientHeight;
            return sh > ch;
        }
        function checkScrollable() {
            var wrap = document.getElementById("back-to-top-wrap");
            if (!wrap) return;
            wrap.style.visibility = isPageScrollable() ? "visible" : "hidden";
        }
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", checkScrollable);
        } else {
            checkScrollable();
        }
        window.addEventListener("resize", checkScrollable);
        if (window.MutationObserver) {
            var observer = new MutationObserver(function() { setTimeout(checkScrollable, 100); });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    })();
    </script>
    """
    try:
        st.html(html, unsafe_allow_javascript=True)
    except TypeError:
        st.markdown(
            '<div style="text-align: center; margin: 1.5rem 0 2rem 0;">'
            '<a href="#page-top" style="display: inline-block; padding: 0.5rem 1rem; font-family: \'Plus Jakarta Sans\', system-ui, sans-serif; font-size: 0.875rem; font-weight: 600; color: #0e7490; background: #f0f9ff; border: 1px solid #0e7490; border-radius: 8px; text-decoration: none; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">↑ Back to top</a>'
            "</div>",
            unsafe_allow_html=True,
        )
