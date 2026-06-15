"""Data ingestion package.

Each module fetches one external source and returns tidy pandas objects:

- ``indec``  — official IPC history (target + decomposition).
- ``sepa``   — high-frequency supermarket food prices (SEPA / Precios Claros).
- ``fx``     — dólar oficial/blue series (FX passthrough feature).
- ``rem``    — BCRA REM analyst expectations (benchmark).

Modules contain no UI or modeling logic.
"""
