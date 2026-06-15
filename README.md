# 📊 Inflación Nowcast — Argentina

> A **nowcasting** system that estimates Argentina's current-month CPI inflation
> *before* the official INDEC release — decomposed into **headline vs core** and by
> **area** (food, energy, transport, …) — and benchmarks the estimate against the BCRA
> analyst consensus (REM). Interactive dashboard, Spanish UI, dark terminal aesthetic.

![Dashboard screenshot placeholder](docs/screenshot.png)

---

## ✨ What it does

- **Decomposes** official INDEC inflation: *nivel general*, *núcleo* (core), *estacional*,
  *regulados*, and 11 thematic areas.
- **Nowcasts** the unpublished month using leading indicators — FX pass-through (dólar),
  high-frequency supermarket food prices (SEPA / Precios Claros), seasonality, and the
  REM consensus.
- **Backtests** the model with an expanding-window, out-of-sample procedure and compares
  it head-to-head against the **REM analyst consensus** and a **seasonal-naïve** baseline
  (MAE / RMSE).
- **Explains** each nowcast in plain Spanish via an optional LLM module ("Lectura del mes").

> The public demo runs on a **synthetic but realistic** dataset (committed) that mirrors
> Argentina's 2021–2026 path, so the dashboard renders with zero setup. Wire in the live
> sources for real data.

---

## 🧱 Architecture

```
          ┌──────────────┐
          │    app.py    │  Streamlit UI only (Spanish, dark theme)
          └──────┬───────┘
                 │ reads artifacts
                 ▼
        ┌──────────────────┐
        │   pipeline.py    │  ingest → features → nowcast → cache
        └───┬───────┬──────┘
            │       │
   ┌────────▼──┐ ┌──▼─────────┐
   │  ingest/  │ │ features.py│  lags, seasonality, FX/REM/SEPA merge
   │ indec sepa│ │  model.py  │  Ridge nowcast + baselines + backtest
   │  fx  rem  │ └────────────┘
   └───────────┘
                 │ optional
                 ▼
           narrative.py        LLM "Lectura del mes" (Anthropic)

   data/processed/  ipc_history.parquet · nowcast.json   (committed demo)
   config.py        sources, IPC weights, area mapping, API key
```

**Separation of concerns:** UI only in `app.py`; ingestion only in `ingest/`; modeling
only in `features.py` / `model.py`; AI only in `narrative.py`.

---

## 📦 Data sources

| Source | Role | Access |
|--------|------|--------|
| **INDEC IPC** | Target + decomposition | indec.gob.ar Excel; datos.gob.ar CSV mirror |
| **SEPA / Precios Claros** | High-frequency food prices | datos.produccion.gob.ar daily ZIPs |
| **Dólar (Bluelytics)** | FX pass-through feature | api.bluelytics.com.ar |
| **BCRA REM** | Analyst consensus (benchmark) | bcra.gob.ar monthly publication |

---

## 🚀 Setup & run

```bash
git clone https://github.com/<your-username>/inflacion-nowcast.git
cd inflacion-nowcast

python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)

pip install -r requirements.txt
python pipeline.py --sample        # generate the demo artifacts
python -m streamlit run app.py
```

Optional — enable the LLM "Lectura del mes":
```bash
copy .env.example .env             # set ANTHROPIC_API_KEY=sk-ant-...
```

---

## 🔬 Methodology (MVP)

- **Targets:** monthly MoM % for *nivel general* and *núcleo*, plus per-area.
- **Features:** own lag(1), seasonal lag(12), month dummies, dólar MoM (oficial & blue),
  SEPA food MoM, REM expectation.
- **Models:** regularized **Ridge** nowcast vs **seasonal-naïve** and the **REM** consensus.
- **Validation:** expanding-window rolling backtest; report MAE / RMSE for all three.
- **Bottom-up:** per-area nowcasts aggregated by INDEC division weights into the headline;
  core excludes *estacional* + *regulados*.

---

## 🛠️ Skills demonstrated

- **Time-series econometrics & forecasting** — nowcasting, seasonal decomposition, rolling backtests.
- **Data engineering** — multi-source ingestion (INDEC, SEPA, BCRA, FX), caching, parquet.
- **Machine learning** — scikit-learn pipelines, regularization, out-of-sample evaluation.
- **Data visualization** — interactive Plotly on a custom dark theme.
- **AI integration** — Anthropic Claude for automated plain-language interpretation.
- **Software architecture** — clean module separation, type hints, docstrings, no secrets in code.

---

## 👤 Author

**Cristopher Astur** — Freelance Economist | UBA | Python · SQL · AI Integrations

## ⚠️ Disclaimer

Portfolio / educational project. The public demo uses synthetic data; nowcasts are model
estimates, **not** official statistics or financial advice.
