"""Shared helpers: cache I/O, date handling, and display formatting.

UI-agnostic (no Streamlit) and model-agnostic. Imported across the ingestion,
modeling, and app layers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import config

# Spanish month names for display (1-indexed).
MESES_ES: tuple[str, ...] = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def ensure_dirs() -> None:
    """Create the data/raw and data/processed directories if missing."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_ipc_history() -> pd.DataFrame:
    """Load the processed monthly IPC history.

    Returns:
        A DataFrame indexed by month-start ``date`` with the component and area
        MoM-percent columns, or an empty DataFrame if the cache is missing.
    """
    try:
        df = pd.read_parquet(config.IPC_HISTORY_FILE)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except (FileNotFoundError, OSError, ValueError):
        return pd.DataFrame()


def save_ipc_history(df: pd.DataFrame) -> None:
    """Persist the processed monthly IPC history to parquet.

    Args:
        df: DataFrame with a ``date`` column plus component/area columns.
    """
    ensure_dirs()
    df.to_parquet(config.IPC_HISTORY_FILE, index=False)


def load_nowcast() -> dict[str, Any]:
    """Load the latest nowcast result JSON.

    Returns:
        The nowcast dict, or an empty dict if the file is missing/corrupt.
    """
    try:
        with open(config.NOWCAST_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_nowcast(data: dict[str, Any]) -> None:
    """Persist the nowcast result JSON with pretty formatting.

    Args:
        data: The nowcast result dict.
    """
    ensure_dirs()
    with open(config.NOWCAST_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def month_label_es(date: datetime | pd.Timestamp | str) -> str:
    """Format a date as a Spanish "month year" label, e.g. ``"junio 2026"``.

    Args:
        date: A datetime, Timestamp, or ISO date string.

    Returns:
        The Spanish month-year label.
    """
    ts = pd.to_datetime(date)
    return f"{MESES_ES[ts.month]} {ts.year}"


def next_month(date: datetime | pd.Timestamp | str) -> pd.Timestamp:
    """Return the first day of the month following ``date``.

    Args:
        date: Any date within the reference month.

    Returns:
        A Timestamp at the first day of the next month.
    """
    ts = pd.to_datetime(date).to_period("M") + 1
    return ts.to_timestamp()


def format_pct(value: float, signed: bool = False) -> str:
    """Format a percentage value for display.

    Args:
        value: The percent value (e.g. ``2.3`` for 2.3%).
        signed: When True, prefix non-negative values with ``+``.

    Returns:
        A formatted string such as ``"2.3%"`` or ``"+2.3%"``.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/d"
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"
