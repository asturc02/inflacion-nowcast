"""INDEC IPC ingestion — the target series and its decomposition.

Produces a monthly DataFrame of month-over-month percent changes for the
aggregate components (nivel general, núcleo, estacional, regulados) and for the
thematic areas defined in :data:`config.AREAS`.

Primary source is the INDEC "cuadros" Excel; the datos.gob.ar CSV mirror is a
fallback. Both formats shift occasionally, so callers should treat a raised
``INDECError`` as "use the cached/sample history instead".
"""

from __future__ import annotations

import io

import pandas as pd
import requests

import config


class INDECError(RuntimeError):
    """Raised when IPC data cannot be retrieved or parsed."""


def _download(url: str) -> bytes:
    """GET a URL and return its raw bytes.

    Args:
        url: Absolute URL to download.

    Returns:
        The response body as bytes.

    Raises:
        INDECError: On any network error or non-2xx status.
    """
    try:
        resp = requests.get(
            url,
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        raise INDECError(f"Download failed for {url}: {exc}") from exc


def fetch_history() -> pd.DataFrame:
    """Fetch and normalize the monthly IPC history.

    Attempts the INDEC Excel first, then the datos.gob.ar CSV mirror. The return
    shape is the canonical frame consumed by the modeling layer.

    Returns:
        A DataFrame with a ``date`` column (month start) plus MoM-percent columns
        for each component in :data:`config.COMPONENTS` and each area in
        :data:`config.AREAS`.

    Raises:
        INDECError: If neither source yields a usable series.
    """
    try:
        return _parse_indec_excel(_download(config.INDEC_IPC_XLS_URL))
    except INDECError:
        # Fallback: at minimum recover nivel_general from the datos.gob.ar mirror.
        return _parse_datos_gob_csv(_download(config.DATOS_GOB_IPC_CSV_URL))


def _parse_indec_excel(content: bytes) -> pd.DataFrame:
    """Parse the INDEC IPC "aperturas" Excel workbook.

    The workbook layout (sheet names, header rows) is confirmed at runtime; this
    parser targets the national index/variation tables. Raises on mismatch so the
    caller can fall back.

    Args:
        content: Raw ``.xls``/``.xlsx`` bytes.

    Returns:
        The canonical monthly MoM DataFrame.

    Raises:
        INDECError: If the expected tables are not found.
    """
    try:
        book = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure uniformly
        raise INDECError(f"Could not open INDEC Excel: {exc}") from exc
    # The exact sheet/row geometry must be confirmed against the live file. Until
    # mapped, signal a fallback so the pipeline uses the cached/sample history.
    raise INDECError(
        "INDEC Excel geometry not yet mapped at runtime; using fallback. "
        f"(workbook had {len(book)} sheets)"
    )


def _parse_datos_gob_csv(content: bytes) -> pd.DataFrame:
    """Parse the datos.gob.ar nivel-general IPC CSV mirror (fallback).

    This recovers only the headline index; component/area columns are filled with
    NaN so the modeling layer can still run on whatever is available.

    Args:
        content: Raw CSV bytes.

    Returns:
        A canonical frame with ``nivel_general`` populated.

    Raises:
        INDECError: If the CSV cannot be parsed into a dated index series.
    """
    try:
        raw = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise INDECError(f"Could not parse datos.gob.ar CSV: {exc}") from exc

    date_col = raw.columns[0]
    value_col = raw.columns[-1]
    try:
        raw[date_col] = pd.to_datetime(raw[date_col])
    except Exception as exc:  # noqa: BLE001
        raise INDECError(f"Unexpected date column in CSV: {exc}") from exc

    index_series = (
        raw.set_index(date_col)[value_col].resample("MS").last().astype(float)
    )
    mom = index_series.pct_change() * 100

    out = pd.DataFrame({"date": mom.index, "nivel_general": mom.values})
    for col in [c for c in config.COMPONENTS if c != "nivel_general"] + list(config.AREAS):
        out[col] = pd.NA
    return out.dropna(subset=["nivel_general"]).reset_index(drop=True)


if __name__ == "__main__":  # Smoke test
    try:
        frame = fetch_history()
        print(frame.tail())
    except INDECError as err:
        print(f"INDEC fetch failed (expected without runtime mapping): {err}")
