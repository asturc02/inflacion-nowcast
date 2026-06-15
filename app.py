"""Streamlit dashboard for the Inflación Nowcast (UI in Spanish).

UI-only module: it reads the processed artifacts produced by ``pipeline.py`` and
renders the nowcast, decomposition, area breakdown, high-frequency tracker,
backtest, and table. Modeling lives in ``model.py``/``features.py`` and AI in
``narrative.py``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import narrative
import pipeline
import utils

st.set_page_config(
    page_title="Nowcast de Inflación · Argentina",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- "Apple Crypto" design system -------------------------------------------
# iOS Stocks meets a DeFi portfolio tracker: frosted glass on a true-black
# lock-screen base, Apple system colors, SF Pro typography with tabular figures.
# Defined here in the UI layer so the look is fully owned by app.py — config.py's
# COLORS palette is intentionally left untouched.
FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", '
    '"Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
)
PALETTE: dict[str, str] = {
    # Surfaces
    "bg": "#000000",                      # OLED black, iOS Stocks base
    "surface": "rgba(28,28,30,0.72)",     # frosted systemGray6 (translucent)
    "surface_solid": "#1C1C1E",           # opaque fallback
    "border": "rgba(255,255,255,0.08)",   # hairline separator
    # Text (Apple label hierarchy)
    "headline": "#F5F5F7",                # primary label
    "muted": "rgba(235,235,245,0.60)",    # secondary label
    "faint": "rgba(235,235,245,0.30)",    # tertiary label
    # Brand accent — Apple system blue (dark variant)
    "accent": "#0A84FF",
    "accent_hi": "#409CFF",
    # Data series — Apple system colors (dark variants)
    "nucleo": "#64D2FF",                  # teal
    "estacional": "#FF9F0A",              # orange
    "regulados": "#FF453A",               # red
    "rem": "#BF5AF2",                     # purple
    # Chart chrome
    "grid": "rgba(255,255,255,0.06)",
}
PLOTLY_FONT = 'Inter, -apple-system, "Segoe UI", sans-serif'

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Lock-screen depth: near-black with faint blue/purple glows so the frosted
   cards have something real to blur behind them. */
.stApp {{
  background-color: {PALETTE['bg']};
  background-image:
    radial-gradient(900px 620px at 10% -10%, rgba(10,132,255,0.12), transparent 60%),
    radial-gradient(820px 600px at 100% 0%, rgba(191,90,242,0.09), transparent 55%);
  background-attachment: fixed;
  color: {PALETTE['headline']};
  font-family: {FONT_STACK};
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}
html, body, h1, h2, h3, h4, label, p, span, div, button, input {{ font-family: {FONT_STACK}; }}
/* Keep Material icon ligatures (e.g. sidebar collapse arrow) on the icon font,
   otherwise the broad span rule above leaks raw text like "keyboard_double_arrow_left". */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded,
.material-symbols-outlined, span[translate="no"] {{
  font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}}

/* Tabular figures — Apple aligns numbers with SF's tnum, never a mono font. */
[data-testid="stMetricValue"], .big-num, .muted, [data-testid="stTable"], .stDataFrame {{
  font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1, "cv01" 1;
}}

h1 {{ letter-spacing: -0.022em; font-weight: 700; }}
h2, h3 {{ letter-spacing: -0.012em; font-weight: 600; }}

section[data-testid="stSidebar"] {{
  background: rgba(20,20,22,0.55);
  backdrop-filter: blur(30px) saturate(180%);
  -webkit-backdrop-filter: blur(30px) saturate(180%);
  border-right: 1px solid {PALETTE['border']};
}}

/* Frosted glass surface — the signature iOS / Control Center material. */
.surface-card {{
  background: {PALETTE['surface']};
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border: 1px solid {PALETTE['border']};
  border-radius: 20px;
  padding: 1.35rem 1.6rem;
  margin-bottom: 1rem;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 10px 30px rgba(0,0,0,0.35);
}}

.big-num {{
  font-size: 3.4rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.04;
  color: {PALETTE['accent']};
}}
.muted {{ color: {PALETTE['muted']}; font-size: 0.92rem; }}
.brand {{ color: {PALETTE['faint']}; font-size: 0.78rem; letter-spacing: 0.005em; }}

/* Metrics: secondary-label caption, tight tabular value. */
[data-testid="stMetricLabel"] p {{ color: {PALETTE['muted']} !important; font-weight: 500; }}
[data-testid="stMetricValue"] {{ font-weight: 600; letter-spacing: -0.02em; color: {PALETTE['headline']}; }}

/* iOS filled button (primary actions). */
.stButton > button {{
  background: {PALETTE['accent']}; color: #FFFFFF; border: 0;
  border-radius: 12px; font-weight: 600; letter-spacing: -0.01em;
  padding: 0.55rem 1.05rem;
  box-shadow: 0 4px 14px rgba(10,132,255,0.32);
  transition: transform .16s ease, background .16s ease, box-shadow .16s ease;
}}
.stButton > button:hover {{ background: {PALETTE['accent_hi']}; transform: translateY(-1px); box-shadow: 0 7px 20px rgba(10,132,255,0.42); }}
.stButton > button:active {{ transform: translateY(0); box-shadow: 0 3px 10px rgba(10,132,255,0.30); }}

/* iOS tinted button (download / secondary actions). */
.stDownloadButton > button {{
  background: rgba(10,132,255,0.15); color: {PALETTE['accent']};
  border: 1px solid rgba(10,132,255,0.30); border-radius: 12px; font-weight: 600;
  transition: background .16s ease;
}}
.stDownloadButton > button:hover {{ background: rgba(10,132,255,0.26); border-color: rgba(10,132,255,0.45); }}

/* Rounded, frosted-feeling alerts, inputs, and dataframe. */
[data-testid="stAlert"] {{ border-radius: 14px; border: 1px solid {PALETTE['border']}; }}
.stDataFrame {{ border-radius: 14px; overflow: hidden; }}
hr, [data-testid="stDivider"] {{ border-color: {PALETTE['border']} !important; }}
.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: {PALETTE['accent']}; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _load() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load the cached IPC history and nowcast artifacts.

    Returns:
        A tuple ``(history_df, nowcast_dict)``.
    """
    return utils.load_ipc_history(), utils.load_nowcast()


def render_sidebar() -> None:
    """Render the sidebar: branding, rebuild button, and data-source notes."""
    st.sidebar.title("📊 Nowcast Inflación")
    st.sidebar.markdown('<div class="brand">Built by Cristopher Astur | UBA Economist</div>', unsafe_allow_html=True)
    st.sidebar.divider()
    if st.sidebar.button("🔄 Actualizar datos (INDEC)", use_container_width=True):
        try:
            with st.spinner("Descargando INDEC y recalculando..."):
                pipeline.build(force_sample=False)
            _load.clear()
            st.sidebar.success("Datos actualizados desde INDEC.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo actualizar: {exc}")
    st.sidebar.divider()
    st.sidebar.caption(
        "Fuentes en vivo: INDEC IPC (datos.gob.ar Series API), dólar oficial/blue "
        "(Bluelytics), BCRA REM (consenso, parcial). SEPA/Precios Claros: en desarrollo."
    )


def render_hero(nowcast: dict[str, Any]) -> None:
    """Render the headline nowcast card plus the optional LLM reading.

    Args:
        nowcast: The nowcast result dict.
    """
    st.subheader(f"Nowcast · {nowcast.get('target_month_label', '—')}")
    left, right = st.columns([1, 2])
    with left:
        st.markdown(
            f'<div class="surface-card"><div class="big-num">'
            f'{utils.format_pct(nowcast.get("headline", float("nan")))}</div>'
            f'<div class="muted">Rango {utils.format_pct(nowcast.get("band_low",0))}'
            f' – {utils.format_pct(nowcast.get("band_high",0))}</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        c1, c2, c3 = st.columns(3)
        c1.metric("Núcleo (est.)", utils.format_pct(nowcast.get("core", float("nan"))))
        c2.metric("Consenso REM", utils.format_pct(nowcast.get("rem_headline") or float("nan")))
        c3.metric("Último oficial", utils.format_pct(nowcast.get("last_official", float("nan"))))

    if narrative.is_available():
        if st.button("🤖 Generar lectura del mes"):
            try:
                with st.spinner("Generando lectura..."):
                    text = narrative.generate_reading(nowcast)
                st.markdown(f'<div class="surface-card">{text}</div>', unsafe_allow_html=True)
            except narrative.NarrativeError as exc:
                st.error(str(exc))
    else:
        st.info("💡 Configurá ANTHROPIC_API_KEY en .env para habilitar la lectura automática (IA).")


def render_decomposition(history: pd.DataFrame) -> None:
    """Plot headline vs núcleo vs estacional vs regulados over time.

    Args:
        history: The IPC history DataFrame.
    """
    st.subheader("Descomposición: general · núcleo · estacional · regulados")
    fig = go.Figure()
    palette = {
        "nivel_general": PALETTE["headline"], "nucleo": PALETTE["nucleo"],
        "estacional": PALETTE["estacional"], "regulados": PALETTE["regulados"],
    }
    labels = {"nivel_general": "Nivel general", "nucleo": "Núcleo",
              "estacional": "Estacional", "regulados": "Regulados"}
    for col, color in palette.items():
        if col in history.columns:
            fig.add_trace(go.Scatter(
                x=history["date"], y=history[col], name=labels[col],
                mode="lines", line=dict(color=color, width=2),
            ))
    _style_fig(fig, yaxis_title="Variación mensual (%)")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_areas(nowcast: dict[str, Any]) -> None:
    """Bar chart of the per-area nowcast for the target month.

    Args:
        nowcast: The nowcast result dict.
    """
    st.subheader("Nowcast por rubro")
    areas = nowcast.get("areas", {})
    if not areas:
        st.info("Sin desagregación por rubro disponible.")
        return
    items = sorted(areas.items(), key=lambda kv: kv[1], reverse=True)
    fig = go.Figure(go.Bar(
        x=[v for _, v in items],
        y=[config.AREAS.get(a, a) for a, _ in items],
        orientation="h",
        marker=dict(color=PALETTE["accent"], cornerradius=7, line=dict(width=0)),
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    _style_fig(fig, xaxis_title="Variación mensual estimada (%)", height=380)
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_backtest(nowcast: dict[str, Any]) -> None:
    """Render the backtest chart and accuracy metrics vs REM and naïve.

    Args:
        nowcast: The nowcast result dict (carries the ``backtest`` payload).
    """
    st.subheader("Backtest: precisión del modelo")
    bt = nowcast.get("backtest", {})
    series = bt.get("series", [])
    if not series:
        st.info("Sin backtest disponible.")
        return
    df = pd.DataFrame(series)
    df["date"] = pd.to_datetime(df["date"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["actual"], name="Oficial",
                             mode="lines", line=dict(color=PALETTE["headline"], width=2.5)))
    fig.add_trace(go.Scatter(x=df["date"], y=df["nowcast"], name="Nowcast",
                             mode="lines", line=dict(color=PALETTE["accent"], width=2.5, dash="dash")))
    if df["rem"].notna().any():
        fig.add_trace(go.Scatter(x=df["date"], y=df["rem"], name="REM",
                                 mode="lines", line=dict(color=PALETTE["rem"], width=1.5, dash="dot")))
    _style_fig(fig, yaxis_title="Variación mensual (%)")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    metrics = bt.get("metrics", {})
    cols = st.columns(3)
    for col, key, label in zip(cols, ("nowcast", "rem", "naive"), ("Nowcast", "REM", "Naïve")):
        m = metrics.get(key, {})
        col.metric(f"MAE {label}", f"{m.get('mae', float('nan')):.2f}",
                   help=f"RMSE: {m.get('rmse', float('nan')):.2f}")


def render_table(nowcast: dict[str, Any]) -> None:
    """Render the backtest table with a CSV download.

    Args:
        nowcast: The nowcast result dict.
    """
    st.subheader("Datos del backtest")
    series = nowcast.get("backtest", {}).get("series", [])
    if not series:
        return
    df = pd.DataFrame(series).rename(columns={
        "date": "Fecha", "actual": "Oficial", "nowcast": "Nowcast",
        "rem": "REM", "naive": "Naïve",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Descargar CSV", data=df.to_csv(index=False).encode("utf-8"),
                       file_name="nowcast_backtest.csv", mime="text/csv")


def _style_fig(fig: go.Figure, yaxis_title: str = "", xaxis_title: str = "", height: int = 420) -> None:
    """Apply the shared "Apple Crypto" theme to a Plotly figure.

    Transparent canvas (so the page's frosted surface shows through), hairline
    gridlines, Inter typography, and a dark frosted-glass hover label.

    Args:
        fig: The figure to style (modified in place).
        yaxis_title: Y-axis title.
        xaxis_title: X-axis title.
        height: Figure height in pixels.
    """
    axis_common = dict(
        gridcolor=PALETTE["grid"], zeroline=False, showline=False,
        ticks="", tickfont=dict(color=PALETTE["muted"], size=12),
        title_font=dict(color=PALETTE["muted"], size=12),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family=PLOTLY_FONT, size=13),
        xaxis=dict(title=xaxis_title, **axis_common),
        yaxis=dict(title=yaxis_title, **axis_common),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=PALETTE["muted"], size=12)),
        hoverlabel=dict(
            bgcolor="rgba(28,28,30,0.92)", bordercolor=PALETTE["border"],
            font=dict(color=PALETTE["headline"], family=PLOTLY_FONT, size=12),
        ),
        margin=dict(l=40, r=20, t=30, b=40), height=height,
    )


def main() -> None:
    """Compose the full dashboard."""
    st.title("Nowcast de Inflación · Argentina")
    st.caption("Estimación de la inflación del mes en curso antes del dato oficial del INDEC.")

    history, nowcast = _load()
    render_sidebar()

    if history.empty or not nowcast:
        st.warning("No hay datos procesados. Ejecutá `python pipeline.py --sample` para generarlos.")
        return

    if nowcast.get("is_sample"):
        st.info("🧪 Mostrando datos de demostración (sintéticos). Conectá las fuentes reales para datos en vivo.")

    render_hero(nowcast)
    st.divider()
    render_decomposition(history)
    st.divider()
    render_areas(nowcast)
    st.divider()
    render_backtest(nowcast)
    st.divider()
    render_table(nowcast)


if __name__ == "__main__":
    main()
