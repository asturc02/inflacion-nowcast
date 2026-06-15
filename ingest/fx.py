"""Dólar (FX) ingestion — historical and current oficial/blue quotes.

The exchange rate is a dominant leading indicator of Argentine inflation
(pass-through), so its month-over-month change is a core nowcast feature.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

import config


class FXError(RuntimeError):
    """Raised when FX data cannot be retrieved."""


def fetch_history() -> pd.DataFrame:
    """Fetch the historical oficial and blue dólar series from Bluelytics.

    Returns:
        A daily DataFrame with columns ``date``, ``oficial``, ``blue`` (sell
        prices in ARS per USD).

    Raises:
        FXError: On network failure or unexpected response format.
    """
    try:
        resp = requests.get(
            config.BLUELYTICS_EVOLUTION_CSV,
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FXError(f"Could not download Bluelytics evolution CSV: {exc}") from exc

    try:
        raw = pd.read_csv(io.StringIO(resp.text))
        # Columns: day, source, value_sell, value_buy
        raw = raw.rename(columns={"day": "date"})
        raw["date"] = pd.to_datetime(raw["date"])
        wide = (
            raw.pivot_table(index="date", columns="source", values="value_sell")
            .rename(columns={"Oficial": "oficial", "Blue": "blue"})
            .reset_index()
            .sort_values("date")
        )
        return wide[["date", "oficial", "blue"]]
    except (KeyError, ValueError) as exc:
        raise FXError(f"Unexpected Bluelytics CSV format: {exc}") from exc


def monthly_change(history: pd.DataFrame) -> pd.DataFrame:
    """Collapse the daily FX history to monthly averages and MoM percent change.

    Args:
        history: Daily FX DataFrame from :func:`fetch_history`.

    Returns:
        A monthly DataFrame with ``date`` (month start), ``oficial_mom`` and
        ``blue_mom`` percent changes.
    """
    monthly = (
        history.set_index("date")[["oficial", "blue"]]
        .resample("MS")
        .mean()
    )
    out = pd.DataFrame(
        {
            "date": monthly.index,
            "oficial_mom": monthly["oficial"].pct_change() * 100,
            "blue_mom": monthly["blue"].pct_change() * 100,
        }
    ).reset_index(drop=True)
    return out
