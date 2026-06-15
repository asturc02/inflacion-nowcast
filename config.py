"""Configuration and constants for the Inflación Nowcast project.

Loads environment variables from a local ``.env`` file (never committed) and exposes
typed module-level constants shared by the ingestion, modeling, and UI layers. The
Anthropic API key (used only by the optional LLM narrative module) is read from the
environment — never hardcoded.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-ish environment variable.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset.

    Returns:
        ``True`` for "1"/"true"/"yes"/"on" (case-insensitive); else ``False``.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable with a fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- Secrets (environment only) ---------------------------------------------
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS: int = 1024
MAX_RETRIES: int = 3

# --- Paths ------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
IPC_HISTORY_FILE: Path = PROCESSED_DIR / "ipc_history.parquet"
NOWCAST_FILE: Path = PROCESSED_DIR / "nowcast.json"

# --- Data source URLs (verified June 2026) ----------------------------------
# INDEC IPC "cuadros" Excel (nivel general, núcleo, estacional, regulados, divisiones).
INDEC_IPC_XLS_URL: str = (
    "https://www.indec.gob.ar/ftp/cuadros/economia/sh_ipc_aperturas.xls"
)
# datos.gob.ar daily-mirrored IPC series (CSV) — fallback for the historical index.
DATOS_GOB_IPC_CSV_URL: str = (
    "https://infra.datos.gob.ar/catalog/sspm/dataset/145/distribution/"
    "145.3/download/indice-precios-al-consumidor-nivel-general.csv"
)
# SEPA / Precios Claros daily price dump (ZIP of CSVs).
SEPA_DATASET_URL: str = (
    "https://datos.produccion.gob.ar/dataset/sepa-precios"
)
# Dólar: current quotes + historical evolution.
DOLARAPI_URL: str = "https://dolarapi.com/v1/dolares"
BLUELYTICS_EVOLUTION_CSV: str = "https://api.bluelytics.com.ar/v2/evolution.csv"
# BCRA REM (analyst expectations) landing page.
BCRA_REM_URL: str = "https://www.bcra.gob.ar/PublicacionesEstadisticas/Relevamiento_Expectativas_de_Mercado.asp"

# --- Caching / HTTP ---------------------------------------------------------
CACHE_TTL_HOURS: int = _get_int("CACHE_TTL_HOURS", 24)
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": "InflacionNowcast/1.0 (portfolio project) Python-requests",
}
REQUEST_TIMEOUT_SECONDS: int = 30

# --- IPC decomposition components -------------------------------------------
# Aggregate cuts published by INDEC.
COMPONENTS: tuple[str, ...] = ("nivel_general", "nucleo", "estacional", "regulados")

# Thematic areas (grouping of the 12 COICOP divisions) used in the breakdown.
# Keys are internal ids; values are Spanish display labels.
AREAS: dict[str, str] = {
    "alimentos": "Alimentos y bebidas",
    "energia_vivienda": "Energía y vivienda",
    "transporte": "Transporte",
    "indumentaria": "Indumentaria",
    "salud": "Salud",
    "educacion": "Educación",
    "equipamiento": "Equipamiento del hogar",
    "comunicacion": "Comunicación",
    "recreacion": "Recreación y cultura",
    "restaurantes": "Restaurantes y hoteles",
    "otros": "Bienes y servicios varios",
}

# Approximate IPC weights (share of the basket) per area — used to aggregate the
# bottom-up nowcast into the headline. Sum ≈ 1.0. These mirror INDEC's national
# division weights and can be refined from the official ponderadores.
AREA_WEIGHTS: dict[str, float] = {
    "alimentos": 0.268,
    "energia_vivienda": 0.107,
    "transporte": 0.114,
    "indumentaria": 0.090,
    "salud": 0.080,
    "educacion": 0.030,
    "equipamiento": 0.066,
    "comunicacion": 0.034,
    "recreacion": 0.072,
    "restaurantes": 0.107,
    "otros": 0.032,
}

# --- Display ----------------------------------------------------------------
# Dark, terminal-inspired palette (consistent with the Fed dashboard project).
COLORS: dict[str, str] = {
    "bg": "#0D0D0D",
    "surface": "#161616",
    "border": "#2A2A2A",
    "accent": "#00FF88",
    "headline": "#E5E5E5",
    "nucleo": "#22D3EE",
    "estacional": "#F59E0B",
    "regulados": "#EF4444",
    "rem": "#A78BFA",
}

DEBUG: bool = _get_bool("DEBUG", False)
