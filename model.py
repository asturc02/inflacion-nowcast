"""Nowcast models, rolling backtest, and bottom-up area aggregation.

Provides interpretable baselines (seasonal-naïve), a regularized Ridge nowcast
for the headline and core series, a rolling-origin backtest that benchmarks the
nowcast against the REM consensus and the naïve baseline, and a bottom-up
aggregation of per-area nowcasts into the headline.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

import config
import features as feat


def seasonal_naive(df: pd.DataFrame, target: str, idx: int) -> float:
    """Seasonal-naïve prediction: the value 12 months earlier (else previous).

    Args:
        df: The modeling frame.
        target: Target column name.
        idx: Row index of the month being predicted.

    Returns:
        The naïve predicted MoM percent.
    """
    if idx >= 12 and not pd.isna(df[target].iloc[idx - 12]):
        return float(df[target].iloc[idx - 12])
    if idx >= 1:
        return float(df[target].iloc[idx - 1])
    return float(df[target].iloc[idx])


def fit_predict_ridge(
    df: pd.DataFrame, target: str, train_idx: np.ndarray, predict_idx: int, alpha: float = 1.0
) -> float:
    """Fit a Ridge model on the training rows and predict one month.

    Args:
        df: The modeling frame.
        target: Target column name.
        train_idx: Integer row positions to train on.
        predict_idx: Integer row position to predict.
        alpha: Ridge regularization strength.

    Returns:
        The predicted MoM percent for ``predict_idx``.
    """
    cols = feat.feature_columns(df, target)
    x_all = feat.design_matrix(df, cols)
    y = df[target]

    train_mask = np.array([i for i in train_idx if not pd.isna(y.iloc[i])])
    if len(train_mask) < 6:  # Too little data — fall back to naïve.
        return seasonal_naive(df, target, predict_idx)

    model = Ridge(alpha=alpha)
    model.fit(x_all.iloc[train_mask], y.iloc[train_mask])
    return float(model.predict(x_all.iloc[[predict_idx]])[0])


def rolling_backtest(
    df: pd.DataFrame, target: str = "nivel_general", min_train: int = 24
) -> dict[str, Any]:
    """Run an expanding-window backtest of the nowcast vs REM and naïve.

    Args:
        df: The modeling frame (must contain ``target`` and ``date``).
        target: Target column to backtest.
        min_train: Minimum months before the first out-of-sample prediction.

    Returns:
        A dict with a per-month ``series`` (date, actual, nowcast, rem, naive)
        and ``metrics`` (MAE/RMSE for nowcast, rem, naive).
    """
    rows: list[dict[str, Any]] = []
    rem_col = "rem_headline" if target == "nivel_general" else "rem_nucleo"

    for i in range(min_train, len(df)):
        actual = df[target].iloc[i]
        if pd.isna(actual):
            continue
        train_idx = np.arange(0, i)  # Expanding window, excludes the test month.
        nowcast = fit_predict_ridge(df, target, train_idx, i)
        naive = seasonal_naive(df, target, i)
        rem = float(df[rem_col].iloc[i]) if rem_col in df.columns else np.nan
        rows.append(
            {
                "date": df["date"].iloc[i].strftime("%Y-%m-%d"),
                "actual": round(float(actual), 2),
                "nowcast": round(nowcast, 2),
                "rem": None if pd.isna(rem) else round(rem, 2),
                "naive": round(naive, 2),
            }
        )

    return {"series": rows, "metrics": _metrics(rows)}


def _metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Compute MAE/RMSE for each predictor against the actuals.

    Args:
        rows: Backtest rows from :func:`rolling_backtest`.

    Returns:
        A dict mapping ``"nowcast"``/``"rem"``/``"naive"`` to ``{"mae","rmse"}``.
    """
    out: dict[str, dict[str, float]] = {}
    actual = np.array([r["actual"] for r in rows], dtype=float)
    for key in ("nowcast", "rem", "naive"):
        preds = np.array(
            [r[key] if r[key] is not None else np.nan for r in rows], dtype=float
        )
        mask = ~np.isnan(preds)
        if mask.sum() == 0:
            out[key] = {"mae": float("nan"), "rmse": float("nan")}
            continue
        err = preds[mask] - actual[mask]
        out[key] = {
            "mae": round(float(np.mean(np.abs(err))), 3),
            "rmse": round(float(np.sqrt(np.mean(err ** 2))), 3),
        }
    return out


def nowcast_areas(df: pd.DataFrame) -> dict[str, float]:
    """Nowcast each thematic area's MoM via a seasonal/AR blend.

    Args:
        df: The modeling frame containing area columns.

    Returns:
        A dict mapping area id → predicted MoM percent for the next month.
    """
    out: dict[str, float] = {}
    for area in config.AREAS:
        if area not in df.columns or df[area].dropna().empty:
            continue
        series = df[area].dropna()
        seasonal = series.iloc[-12] if len(series) >= 12 else series.iloc[-1]
        recent = series.iloc[-1]
        out[area] = float(0.5 * seasonal + 0.5 * recent)  # Simple blend.
    return out


def aggregate_headline(area_nowcasts: dict[str, float]) -> float:
    """Aggregate per-area nowcasts into a weighted headline MoM.

    Args:
        area_nowcasts: Mapping of area id → predicted MoM percent.

    Returns:
        The weight-aggregated headline MoM percent.
    """
    num = sum(config.AREA_WEIGHTS.get(a, 0.0) * v for a, v in area_nowcasts.items())
    den = sum(config.AREA_WEIGHTS.get(a, 0.0) for a in area_nowcasts)
    return float(num / den) if den else float("nan")


if __name__ == "__main__":  # Smoke test against the cached history.
    import utils

    frame = feat.build_feature_frame(utils.load_ipc_history())
    if frame.empty:
        print("No IPC history cached. Run pipeline.py --sample first.")
    else:
        bt = rolling_backtest(frame)
        print("Backtest metrics:", bt["metrics"])
