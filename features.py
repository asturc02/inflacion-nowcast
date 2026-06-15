"""Feature engineering for the inflation nowcast.

Combines the INDEC IPC history with the leading indicators (FX pass-through,
SEPA food prices, REM consensus) into a single monthly modeling frame with
lags, seasonal terms, and month dummies.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

# Indicator columns that may be merged in from the ingestion layer.
INDICATOR_COLS: tuple[str, ...] = (
    "oficial_mom",
    "blue_mom",
    "sepa_food_mom",
    "rem_headline",
    "rem_nucleo",
)


def build_feature_frame(
    history: pd.DataFrame,
    fx: pd.DataFrame | None = None,
    sepa: pd.DataFrame | None = None,
    rem: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Assemble the monthly modeling frame.

    Args:
        history: Canonical IPC MoM history (``date`` + component/area columns).
        fx: Optional monthly FX change frame (``date``, ``oficial_mom``, ``blue_mom``).
        sepa: Optional monthly SEPA food frame (``date``, ``sepa_food_mom``).
        rem: Optional monthly REM frame (``date``, ``rem_headline``, ``rem_nucleo``).

    Returns:
        A merged, feature-engineered DataFrame sorted by ``date``. Adds lag and
        seasonal columns for the headline/core targets and a ``month`` field.
    """
    df = history.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for extra in (fx, sepa, rem):
        if extra is not None and not extra.empty:
            merged = extra.copy()
            merged["date"] = pd.to_datetime(merged["date"])
            df = df.merge(merged, on="date", how="left")

    # Ensure indicator columns exist even when a source was unavailable.
    for col in INDICATOR_COLS:
        if col not in df.columns:
            df[col] = np.nan

    # Lags and seasonal terms for the two main targets.
    for target in ("nivel_general", "nucleo"):
        if target in df.columns:
            df[f"{target}_lag1"] = df[target].shift(1)
            df[f"{target}_lag12"] = df[target].shift(12)

    df["month"] = df["date"].dt.month
    return df


def feature_columns(df: pd.DataFrame, target: str) -> list[str]:
    """List the predictor columns available for a given target.

    Args:
        df: The modeling frame from :func:`build_feature_frame`.
        target: ``"nivel_general"`` or ``"nucleo"``.

    Returns:
        The ordered list of predictor column names present in ``df``.
    """
    candidates = [
        f"{target}_lag1",
        f"{target}_lag12",
        "oficial_mom",
        "blue_mom",
        "sepa_food_mom",
        "rem_headline" if target == "nivel_general" else "rem_nucleo",
        "month",
    ]
    return [c for c in candidates if c in df.columns]


def design_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Build a numeric design matrix with month one-hot encoding and imputation.

    Args:
        df: The modeling frame.
        cols: Predictor columns (may include the categorical ``month``).

    Returns:
        A numeric DataFrame ready for scikit-learn, with NaNs filled by column
        means and ``month`` expanded into dummy variables.
    """
    x = df[cols].copy()
    if "month" in x.columns:
        dummies = pd.get_dummies(x["month"], prefix="m")
        x = pd.concat([x.drop(columns=["month"]), dummies], axis=1)
    x = x.apply(pd.to_numeric, errors="coerce")
    # Forward-fill missing indicators (rows are date-ordered) so a stale/lagging
    # source is imputed with its most recent value — the current regime — rather
    # than the full-history mean, which would be biased by past high-inflation.
    return x.ffill().fillna(0.0)
