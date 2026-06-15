"""Orchestration: ingest → features → nowcast → cache.

``build()`` tries the live ingestion modules and falls back to a synthetic but
realistic sample whenever a source's runtime format is not yet mapped. It writes
two artifacts consumed by the dashboard:

- ``data/processed/ipc_history.parquet`` — monthly IPC history (components + areas).
- ``data/processed/nowcast.json`` — current-month nowcast, backtest, and metrics.

Run ``python pipeline.py --sample`` to (re)generate the committed demo artifacts.
"""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np
import pandas as pd

import config
import features as feat
import model as mdl
import utils
from ingest import fx as fx_src
from ingest import indec as indec_src
from ingest import rem as rem_src
from ingest import sepa as sepa_src


# --------------------------------------------------------------------------- #
# Synthetic sample (deterministic) — mirrors Argentina's 2021–2026 path.
# --------------------------------------------------------------------------- #
def _synthesize() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate a realistic synthetic dataset for the demo.

    Reproduces the broad shape of recent Argentine inflation: acceleration into
    the Dec-2023 devaluation peak, then disinflation toward ~2% by 2026, with
    FX, food, and REM indicators carrying genuine signal.

    Returns:
        A tuple ``(history, fx, sepa, rem)`` of monthly DataFrames. Indicators
        extend one month past the IPC history so the last frame row is the month
        to nowcast.
    """
    rng = np.random.default_rng(42)
    months = pd.date_range("2021-01-01", "2026-06-01", freq="MS")
    n = len(months)
    t = np.arange(n)
    month_num = months.month.to_numpy()  # plain ndarray (avoids immutable Index)

    # Headline MoM path: rising to a peak near the Dec-2023 devaluation, then
    # disinflating. Built from a smooth backbone plus seasonality and noise.
    peak = list(months).index(pd.Timestamp("2023-12-01"))
    backbone = 3.5 + 0.55 * t  # gentle acceleration
    backbone = backbone - 1.25 * np.maximum(0, t - peak)  # disinflation after peak
    backbone = np.clip(backbone, 1.8, 26.0)
    seasonal = 0.8 * np.sin(2 * np.pi * (month_num - 1) / 12)
    headline = backbone + seasonal + rng.normal(0, 0.6, n)
    headline[peak] += 12.0  # devaluation pass-through spike
    headline = np.clip(headline, 1.2, None)

    # FX: large devaluation at the peak month, otherwise a managed crawl.
    oficial_mom = np.full(n, 0.0)
    oficial_mom[: peak] = 5.0 + rng.normal(0, 1.0, peak)
    oficial_mom[peak] = 118.0
    oficial_mom[peak + 1 :] = np.clip(6.0 - 0.15 * np.arange(n - peak - 1), 1.5, 6.0)
    blue_mom = oficial_mom * 0.7 + rng.normal(0, 1.5, n)

    # Components derived from the headline.
    nucleo = headline * 0.92 + rng.normal(0, 0.4, n)
    estacional = headline + 1.5 * np.sin(2 * np.pi * month_num / 12) + rng.normal(0, 1.2, n)
    regulados = headline * 0.8 + 0.04 * oficial_mom + rng.normal(0, 0.8, n)

    history = pd.DataFrame(
        {
            "date": months,
            "nivel_general": headline.round(2),
            "nucleo": nucleo.round(2),
            "estacional": estacional.round(2),
            "regulados": np.clip(regulados, 0.5, None).round(2),
        }
    )

    # Areas: anchored on the headline with area-specific factors/sensitivities.
    area_factor = {
        "alimentos": 1.05, "energia_vivienda": 1.20, "transporte": 1.10,
        "indumentaria": 0.85, "salud": 0.95, "educacion": 0.70,
        "equipamiento": 0.90, "comunicacion": 0.65, "recreacion": 0.88,
        "restaurantes": 1.00, "otros": 0.92,
    }
    for area, fct in area_factor.items():
        sens = 0.05 if area in ("alimentos", "transporte", "energia_vivienda") else 0.0
        history[area] = (headline * fct + sens * oficial_mom + rng.normal(0, 0.7, n)).round(2)

    # SEPA food tracker: a noisy early read of the alimentos series.
    sepa = pd.DataFrame(
        {"date": months, "sepa_food_mom": (history["alimentos"] + rng.normal(0, 0.5, n)).round(2)}
    )

    # REM: analyst median ≈ actual headline/core plus forecast error.
    rem = pd.DataFrame(
        {
            "date": months,
            "rem_headline": (headline + rng.normal(0, 0.7, n)).round(2),
            "rem_nucleo": (nucleo + rng.normal(0, 0.7, n)).round(2),
        }
    )

    fx = pd.DataFrame(
        {"date": months, "oficial_mom": oficial_mom.round(2), "blue_mom": blue_mom.round(2)}
    )

    # Extend indicators one month past the IPC history → the month to nowcast.
    nxt = utils.next_month(months[-1])
    fx = pd.concat([fx, pd.DataFrame({"date": [nxt], "oficial_mom": [2.0], "blue_mom": [1.5]})], ignore_index=True)
    sepa = pd.concat([sepa, pd.DataFrame({"date": [nxt], "sepa_food_mom": [2.4]})], ignore_index=True)
    rem = pd.concat([rem, pd.DataFrame({"date": [nxt], "rem_headline": [2.3], "rem_nucleo": [2.1]})], ignore_index=True)

    return history, fx, sepa, rem


def _ingest_live() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    """Attempt live ingestion from all sources.

    Returns:
        The ``(history, fx, sepa, rem)`` tuple if INDEC (the target) succeeds,
        otherwise ``None`` to signal the caller to fall back to the sample.
    """
    try:
        history = indec_src.fetch_history()
    except indec_src.INDECError:
        return None

    def _safe(fn, default: pd.DataFrame) -> pd.DataFrame:
        try:
            return fn()
        except Exception:  # noqa: BLE001 - any source failure → empty frame
            return default

    fx = _safe(lambda: fx_src.monthly_change(fx_src.fetch_history()), pd.DataFrame())
    sepa = _safe(sepa_src.fetch_basket_index, pd.DataFrame())
    rem = _safe(rem_src.fetch_expectations, pd.DataFrame())
    return history, fx, sepa, rem


def _compute_nowcast(frame: pd.DataFrame, backtest: dict[str, Any]) -> dict[str, Any]:
    """Build the nowcast result dict for the latest (unpublished) month.

    Args:
        frame: The full feature frame; its last row is the month to nowcast.
        backtest: Output of :func:`model.rolling_backtest` (for the error band).

    Returns:
        The serializable nowcast dict consumed by the dashboard.
    """
    last_idx = len(frame) - 1
    train_idx = np.arange(0, last_idx)

    headline = mdl.fit_predict_ridge(frame, "nivel_general", train_idx, last_idx)
    core = mdl.fit_predict_ridge(frame, "nucleo", train_idx, last_idx)

    rmse = backtest["metrics"].get("nowcast", {}).get("rmse", 0.5) or 0.5
    areas = mdl.nowcast_areas(frame.iloc[:last_idx])
    last_official = float(frame["nivel_general"].iloc[:last_idx].dropna().iloc[-1])
    rem_headline = frame.get("rem_headline", pd.Series([np.nan])).iloc[last_idx]

    return {
        "target_month": frame["date"].iloc[last_idx].strftime("%Y-%m-%d"),
        "target_month_label": utils.month_label_es(frame["date"].iloc[last_idx]),
        "headline": round(headline, 2),
        "core": round(core, 2),
        "band_low": round(headline - rmse, 2),
        "band_high": round(headline + rmse, 2),
        "last_official": round(last_official, 2),
        "rem_headline": None if pd.isna(rem_headline) else round(float(rem_headline), 2),
        "areas": {a: round(v, 2) for a, v in areas.items()},
        "backtest": backtest,
        "generated_at": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M UTC"),
        "is_sample": True,
    }


def build(force_sample: bool = False) -> dict[str, Any]:
    """Run the full pipeline and persist the artifacts.

    Args:
        force_sample: When True, skip live ingestion and use the synthetic sample.

    Returns:
        The nowcast result dict (also written to ``data/processed/nowcast.json``).
    """
    utils.ensure_dirs()
    sources = None if force_sample else _ingest_live()
    used_sample = sources is None
    history, fx, sepa, rem = _synthesize() if used_sample else sources

    # Append the next (unpublished) month as a blank row so it becomes the frame's
    # last row — the month to nowcast. Its indicators merge in; its target is NaN.
    target = utils.next_month(pd.to_datetime(history["date"]).max())
    history = pd.concat(
        [history, pd.DataFrame({"date": [target]})], ignore_index=True
    )

    frame = feat.build_feature_frame(history, fx, sepa, rem)
    backtest = mdl.rolling_backtest(frame, target="nivel_general")
    nowcast = _compute_nowcast(frame, backtest)
    nowcast["is_sample"] = used_sample

    # Persist: history excludes the appended nowcast month (target NaN rows).
    hist_out = frame[frame["nivel_general"].notna()][
        ["date", *config.COMPONENTS, *config.AREAS]
    ].copy()
    utils.save_ipc_history(hist_out)
    utils.save_nowcast(nowcast)
    return nowcast


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the inflation nowcast artifacts.")
    parser.add_argument("--sample", action="store_true", help="Use synthetic sample data.")
    args = parser.parse_args()
    result = build(force_sample=args.sample)
    print(
        f"Nowcast {result['target_month_label']}: headline {result['headline']}% "
        f"(REM {result['rem_headline']}%) | sample={result['is_sample']}"
    )
    print("Backtest metrics:", result["backtest"]["metrics"])
