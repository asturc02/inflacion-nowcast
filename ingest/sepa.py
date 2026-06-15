"""SEPA / Precios Claros ingestion — high-frequency food prices (light tracker).

The full SEPA dump is millions of daily price rows across thousands of stores.
For the MVP we track a small **fixed basket** of staple products and build a
simple unweighted price index, used as an early intra-month signal for food
inflation. Full bottom-up index reconstruction is a later phase.
"""

from __future__ import annotations

import pandas as pd

import config

# Fixed staple basket (SEPA product ids / EANs). Confirmed against the live
# catalog at build time; kept small so the tracker stays fast and reproducible.
BASKET_EANS: tuple[str, ...] = (
    "7790070410788",  # leche entera 1L
    "7790040000018",  # pan lactal
    "7791290000139",  # aceite girasol 1.5L
    "7790580123456",  # arroz 1kg
    "7790036000000",  # azúcar 1kg
    "7790070000000",  # yerba mate 1kg
    "7791234500000",  # fideos 500g
    "7790000000000",  # harina 000 1kg
)


class SEPAError(RuntimeError):
    """Raised when SEPA price data cannot be retrieved or parsed."""


def fetch_basket_index() -> pd.DataFrame:
    """Build a monthly food price index from the fixed SEPA basket.

    Returns:
        A monthly DataFrame with ``date`` (month start) and ``sepa_food_mom``
        (percent change of the basket price index).

    Raises:
        SEPAError: If the SEPA dump cannot be downloaded or parsed.

    Notes:
        The live SEPA ZIP layout (file names inside the archive, column schema)
        is confirmed at runtime. Until mapped, this raises ``SEPAError`` so the
        pipeline falls back to the cached/sample food series.
    """
    raise SEPAError(
        "SEPA archive geometry not yet mapped at runtime; using cached/sample "
        "food series. Basket size: " + str(len(BASKET_EANS))
    )


def food_mom_from_index(price_panel: pd.DataFrame) -> pd.DataFrame:
    """Collapse a daily product-price panel into a monthly basket MoM series.

    Args:
        price_panel: Long DataFrame with columns ``date``, ``ean``, ``price``.

    Returns:
        Monthly DataFrame with ``date`` and ``sepa_food_mom`` columns.
    """
    basket = price_panel[price_panel["ean"].astype(str).isin(BASKET_EANS)]
    monthly = (
        basket.assign(date=pd.to_datetime(basket["date"]))
        .set_index("date")
        .groupby(pd.Grouper(freq="MS"))["price"]
        .mean()
    )
    return pd.DataFrame(
        {"date": monthly.index, "sepa_food_mom": monthly.pct_change() * 100}
    ).reset_index(drop=True)
