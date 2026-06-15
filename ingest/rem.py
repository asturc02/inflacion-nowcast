"""BCRA REM ingestion — analyst consensus for headline CPI (benchmark).

Uses the datos.gob.ar Series API mirror of the REM median monthly CPI
expectation. Note: this mirrored series can lag the latest BCRA publication, so
recent months may be missing — recent values fall back to NaN and the nowcast
simply runs without the REM feature/benchmark for those months.
"""

from __future__ import annotations

import pandas as pd
import requests

import config

SERIES_API: str = "https://apis.datos.gob.ar/series/api/series/"
# REM: median expected monthly national CPI for the current month (fraction).
REM_HEADLINE_SERIES: str = "430.1_REM_IPC_NAL_T_M_0_0_25_28"


class REMError(RuntimeError):
    """Raised when REM expectations cannot be retrieved or parsed."""


def fetch_expectations() -> pd.DataFrame:
    """Fetch the REM median CPI expectation time series.

    Returns:
        A monthly DataFrame with ``date`` (target month) and ``rem_headline``
        median expected MoM percent.

    Raises:
        REMError: If the series cannot be downloaded or parsed.
    """
    try:
        resp = requests.get(
            SERIES_API,
            params={"ids": REM_HEADLINE_SERIES, "format": "json", "limit": 1000, "collapse": "month"},
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json().get("data")
    except (requests.RequestException, ValueError) as exc:
        raise REMError(f"REM Series API request failed: {exc}") from exc
    if not data:
        raise REMError("REM series returned no data.")

    df = pd.DataFrame(data, columns=["date", "rem_headline"])
    df["date"] = pd.to_datetime(df["date"])
    # The mirrored series stores the median as a fraction (0.023 → 2.3%).
    df["rem_headline"] = (df["rem_headline"].astype(float) * 100).round(2)
    return df


def latest_consensus(expectations: pd.DataFrame) -> dict[str, float]:
    """Return the most recent REM headline consensus.

    Args:
        expectations: DataFrame from :func:`fetch_expectations`.

    Returns:
        ``{"rem_headline": float}`` for the latest month, or ``{}`` if empty.
    """
    if expectations.empty:
        return {}
    last = expectations.sort_values("date").iloc[-1]
    return {"rem_headline": float(last["rem_headline"])}


if __name__ == "__main__":  # Smoke test
    print(fetch_expectations().tail(4).to_string(index=False))
