"""INDEC IPC ingestion — real data via the datos.gob.ar Series API.

Fetches the official national IPC index series (base dic-2016) for the four
aggregate components and the COICOP divisions mapped to our thematic areas, then
converts indices to month-over-month percent changes — the canonical frame the
modeling layer consumes.

Source: https://apis.datos.gob.ar/series/api (Series de Tiempo, SSPM / INDEC).
Series IDs verified June 2026 against the live catalog.
"""

from __future__ import annotations

import pandas as pd
import requests

import config

SERIES_API: str = "https://apis.datos.gob.ar/series/api/series/"

# Aggregate components — national monthly index, base dic-2016.
COMPONENT_SERIES: dict[str, str] = {
    "nivel_general": "148.3_INIVELNAL_DICI_M_26",
    "nucleo": "148.3_INUCLEONAL_DICI_M_19",
    "estacional": "148.3_IESTACINAL_DICI_M_25",
    "regulados": "148.3_IREGULANAL_DICI_M_22",
}

# COICOP divisions (national monthly index) mapped to our thematic areas.
AREA_SERIES: dict[str, str] = {
    "alimentos": "146.3_IALIMENNAL_DICI_M_45",      # Alimentos y bebidas no alcohólicas
    "energia_vivienda": "146.3_IVIVIENNAL_DICI_M_52",  # Vivienda, agua, electricidad, comb.
    "transporte": "146.3_ITRANSPNAL_DICI_M_23",
    "indumentaria": "146.3_IPRENDANAL_DICI_M_35",   # Prendas de vestir y calzado
    "salud": "146.3_ISALUDNAL_DICI_M_18",
    "educacion": "146.3_IEDUCACNAL_DICI_M_22",
    "equipamiento": "146.3_IEQUIPANAL_DICI_M_46",   # Equipamiento y mant. del hogar
    "comunicacion": "146.3_ICOMUNINAL_DICI_M_27",
    "recreacion": "146.3_IRECREANAL_DICI_M_31",
    "restaurantes": "146.3_IRESTAUNAL_DICI_M_33",   # Hoteles y restaurantes
    "otros": "146.3_IBIENESNAL_DICI_M_36",          # Bienes y servicios varios
}


class INDECError(RuntimeError):
    """Raised when IPC data cannot be retrieved or parsed."""


def _fetch_series(id_map: dict[str, str]) -> pd.DataFrame:
    """Fetch a group of index series and return them aligned by month.

    Args:
        id_map: Mapping of output column name → datos.gob.ar series id.

    Returns:
        A DataFrame indexed by month with one float index-level column per key.

    Raises:
        INDECError: On network failure or an unexpected response.
    """
    names = list(id_map.keys())
    ids = ",".join(id_map[n] for n in names)
    try:
        resp = requests.get(
            SERIES_API,
            params={"ids": ids, "format": "json", "limit": 1000, "collapse": "month"},
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise INDECError(f"datos.gob.ar Series API request failed: {exc}") from exc

    data = payload.get("data")
    if not data:
        raise INDECError("Series API returned no data.")

    # Response rows are [date, v0, v1, ...] in the order of the requested ids.
    df = pd.DataFrame(data, columns=["date", *names])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").astype(float)
    return df


def fetch_history() -> pd.DataFrame:
    """Fetch the official IPC history and convert it to monthly MoM percent.

    Returns:
        A DataFrame with a ``date`` column (month start) and MoM-percent columns
        for each component in :data:`COMPONENT_SERIES` and area in
        :data:`AREA_SERIES`.

    Raises:
        INDECError: If the data cannot be retrieved.
    """
    components = _fetch_series(COMPONENT_SERIES)
    areas = _fetch_series(AREA_SERIES)
    index_levels = components.join(areas, how="outer").sort_index()

    # Index → month-over-month percent change.
    mom = index_levels.pct_change() * 100.0
    mom = mom.dropna(how="all").reset_index()
    mom = mom[mom["date"] >= "2017-01-01"].copy()
    num_cols = mom.columns.drop("date")
    mom[num_cols] = mom[num_cols].round(2)
    return mom.reset_index(drop=True)


if __name__ == "__main__":  # Smoke test
    frame = fetch_history()
    cols = ["date", "nivel_general", "nucleo", "alimentos"]
    print(frame[cols].tail(6).to_string(index=False))
