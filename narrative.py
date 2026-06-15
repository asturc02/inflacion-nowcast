"""Optional LLM narrative — a plain-language "Lectura del mes" of the nowcast.

Reuses the Anthropic pattern from the Fed-sentiment project (client, exponential
backoff, defensive parsing). Disabled gracefully when no API key is configured.
"""

from __future__ import annotations

import time
from typing import Any

import config

SYSTEM_PROMPT = """Sos un analista macroeconómico argentino experto en inflación.
A partir de los datos del nowcast (estimación de inflación del mes en curso antes
de la publicación oficial del INDEC), escribí una lectura breve y clara para un
público no especializado. Máximo 4 oraciones. Mencioná: el número estimado, cómo
se compara con el consenso REM y el último dato oficial, y los principales
drivers (tipo de cambio, alimentos, regulados/estacionales). No uses jerga
innecesaria. Respondé solo con el texto, sin encabezados."""


class NarrativeError(RuntimeError):
    """Raised when the narrative cannot be generated."""


def is_available() -> bool:
    """Report whether the LLM narrative can run (API key present)."""
    return bool(config.ANTHROPIC_API_KEY)


def _build_prompt(nowcast: dict[str, Any]) -> str:
    """Render the nowcast dict into a compact Spanish prompt.

    Args:
        nowcast: The nowcast result dict from the pipeline.

    Returns:
        A user-message string summarizing the figures for the model.
    """
    areas = nowcast.get("areas", {})
    top = sorted(areas.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_str = ", ".join(f"{config.AREAS.get(a, a)} {v:.1f}%" for a, v in top)
    return (
        f"Mes: {nowcast.get('target_month_label')}\n"
        f"Nowcast nivel general: {nowcast.get('headline')}% "
        f"(rango {nowcast.get('band_low')}–{nowcast.get('band_high')}%)\n"
        f"Núcleo: {nowcast.get('core')}%\n"
        f"Consenso REM: {nowcast.get('rem_headline')}%\n"
        f"Último dato oficial: {nowcast.get('last_official')}%\n"
        f"Rubros con mayor suba estimada: {top_str}"
    )


def generate_reading(nowcast: dict[str, Any]) -> str:
    """Generate the Spanish "Lectura del mes" for a nowcast.

    Args:
        nowcast: The nowcast result dict.

    Returns:
        The generated narrative text.

    Raises:
        NarrativeError: If no API key is set or the call fails after retries.
    """
    if not is_available():
        raise NarrativeError(
            "ANTHROPIC_API_KEY no configurada. Agregala al archivo .env para "
            "habilitar la lectura automática."
        )

    import anthropic  # Imported lazily so the app runs without the SDK installed.

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = _build_prompt(nowcast)

    last_error: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        try:
            message = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=config.ANTHROPIC_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in message.content if b.type == "text").strip()
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_error = exc
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise NarrativeError(f"Falló la generación tras {config.MAX_RETRIES} intentos: {last_error}")
