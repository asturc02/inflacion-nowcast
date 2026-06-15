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

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
.stApp {{ background-color: {config.COLORS['bg']}; color: {config.COLORS['headline']}; }}
section[data-testid="stSidebar"] {{ background-color: {config.COLORS['surface']}; border-right: 1px solid {config.COLORS['border']}; }}
h1, h2, h3, label, p, span {{ font-family: 'Inter', sans-serif; }}
[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace !important; }}
.surface-card {{ background-color: {config.COLORS['surface']}; border: 1px solid {config.COLORS['border']}; border-radius: 4px; padding: 1.1rem 1.4rem; margin-bottom: 1rem; }}
.big-num {{ font-family: 'JetBrains Mono', monospace; font-size: 3rem; font-weight: 700; color: {config.COLORS['accent']}; line-height: 1.1; }}
.muted {{ color: #A3A3A3; font-family: 'JetBrains Mono', monospace; }}
.brand {{ color: {config.COLORS['accent']}; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
.stButton > button {{ background-color: {config.COLORS['surface']}; color: {config.COLORS['accent']}; border: 1px solid {config.COLORS['accent']}; border-radius: 4px; font-family: 'JetBrains Mono', monospace; }}
.stButton > button:hover {{ background-color: {config.COLORS['accent']}; color: {config.COLORS['bg']}; }}
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
    if st.sidebar.button("🔄 Recalcular nowcast", use_container_width=True):
        try:
            with st.spinner("Recalculando..."):
                pipeline.build(force_sample=True)
            _load.clear()
            st.sidebar.success("Nowcast actualizado.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo recalcular: {exc}")
    st.sidebar.divider()
    st.sidebar.caption(
        "Fuentes: INDEC (IPC), SEPA/Precios Claros (alta frecuencia), "
        "BCRA REM (consenso), dólar (Bluelytics)."
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
        "nivel_general": config.COLORS["headline"], "nucleo": config.COLORS["nucleo"],
        "estacional": config.COLORS["estacional"], "regulados": config.COLORS["regulados"],
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
    st.plotly_chart(fig, use_container_width=True)


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
        marker_color=config.COLORS["accent"],
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    _style_fig(fig, xaxis_title="Variación mensual estimada (%)", height=380)
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)


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
                             mode="lines", line=dict(color=config.COLORS["headline"], width=2)))
    fig.add_trace(go.Scatter(x=df["date"], y=df["nowcast"], name="Nowcast",
                             mode="lines", line=dict(color=config.COLORS["accent"], width=2, dash="dash")))
    if df["rem"].notna().any():
        fig.add_trace(go.Scatter(x=df["date"], y=df["rem"], name="REM",
                                 mode="lines", line=dict(color=config.COLORS["rem"], width=1.5, dash="dot")))
    _style_fig(fig, yaxis_title="Variación mensual (%)")
    st.plotly_chart(fig, use_container_width=True)

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
    """Apply the shared dark theme to a Plotly figure.

    Args:
        fig: The figure to style (modified in place).
        yaxis_title: Y-axis title.
        xaxis_title: X-axis title.
        height: Figure height in pixels.
    """
    fig.update_layout(
        paper_bgcolor=config.COLORS["bg"], plot_bgcolor=config.COLORS["surface"],
        font=dict(color=config.COLORS["headline"], family="JetBrains Mono, monospace"),
        xaxis=dict(title=xaxis_title, gridcolor=config.COLORS["border"]),
        yaxis=dict(title=yaxis_title, gridcolor=config.COLORS["border"], zerolinecolor=config.COLORS["border"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
