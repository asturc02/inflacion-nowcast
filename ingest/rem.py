"""BCRA REM ingestion — analyst consensus for headline and core CPI.

The Relevamiento de Expectativas de Mercado (REM) publishes the median analyst
forecast for the current month's CPI (general and core). It is the natural
benchmark a nowcast must beat, and the current-month median doubles as a model
feature.
"""

from __future__ import annotations

import pandas as pd

import config


class REMError(RuntimeError):
    """Raised when REM expectations cannot be retrieved or parsed."""


def fetch_expectations() -> pd.DataFrame:
    """Fetch the REM median CPI expectations time series.

    Returns:
        A monthly DataFrame with ``date`` (the forecast target month),
        ``rem_headline`` and ``rem_nucleo`` median expected MoM percent.

    Raises:
        REMError: If the REM publication cannot be downloaded or parsed.

    Notes:
        The REM is distributed as monthly Excel/PDF files whose layout is
        confirmed at runtime. Until mapped, this raises ``REMError`` so the
        pipeline falls back to the cached/sample consensus series.
    """
    raise REMError(
        "BCRA REM workbook geometry not yet mapped at runtime; using "
        "cached/sample consensus series."
    )


def latest_consensus(expectations: pd.DataFrame) -> dict[str, float]:
    """Return the most recent REM headline/core consensus.

    Args:
        expectations: DataFrame from :func:`fetch_expectations`.

    Returns:
        A dict ``{"rem_headline": float, "rem_nucleo": float}`` for the latest
        target month, or an empty dict if the input is empty.
    """
    if expectations.empty:
        return {}
    last = expectations.sort_values("date").iloc[-1]
    return {
        "rem_headline": float(last.get("rem_headline", float("nan"))),
        "rem_nucleo": float(last.get("rem_nucleo", float("nan"))),
    }
