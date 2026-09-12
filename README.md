# Global Data Harmonizer

A full-stack **data harmonization platform** for socio-economic datasets. It ingests messy,
multi-source CSV exports (World Bank, UN, anything similar), profiles them, cleans and
harmonizes country names, numbers, dates and missing values, resolves duplicate conflicts,
validates the result against configurable thresholds, and stores a canonical **source of truth**
with full transformation lineage and quality scores.

```
dirty CSV ──▶ profile ──▶ clean ──▶ normalize country/numeric/date ──▶ merge + dedup ──▶ validate ──▶ harmonized dataset + quality report
```

---

## Architecture

| Layer | Tech | Location |
| --- | --- | --- |
| **Engine** (pure Python, portable) | Pandas, NumPy, Pydantic | `src/data_harmonizer/` |
| **CLI runner** | argparse, logging w/ job ids | `src/data_harmonizer/pipeline/runner.py` |
| **Backend API** | FastAPI, Supabase (PostgREST + Storage + Auth) | `backend/` |
| **Frontend** | Next.js 15, Tailwind, Recharts, Supabase JS | `frontend/` |
| **Database / Auth / Storage** | Supabase (Postgres + RLS + Storage) | `supabase/migrations/` |
| **Deployment** | Render (API), Vercel (web) | `render.yaml`, `frontend/vercel.json` |

Everything is project-relative — there are **no hardcoded filesystem paths**. The engine runs on
any machine (or container) unchanged.

### Canonical output schema
`country_name  iso_alpha2  iso_alpha3  gdp  population  year  life_expectancy`

Country aliases (e.g. `USA`, `usa`, `U.S.A.`, `United States of America` → `UNITED STATES`/`US`/`USA`)
are data-driven in [`config/country_aliases.json`](config/country_aliases.json) — edit that file, not code.

### Quality score & validation
- **Quality score (0–100)** computed from real metrics: missing values (25), duplicates (10),
  unresolved countries (20), conversion errors (15), out-of-range values (15), schema integrity (15).
- **Validation gate (PASS/FAIL)** thresholds in `HarmonizationConfig`: >30% missing, >5%
  duplicates, >10% unresolved countries, or range violations on GDP/population/life expectancy/year.
- **Every transformation is audited** into a lineage log (`TransformationRecord`s), and
  cross-source numeric disagreements are surfaced as `ConflictRecord`s during merge.

---

## Repository layout

```
backend/               FastAPI app (routers, services, JWT auth via Supabase)
config/                country_aliases.json + engine config
frontend/              Next.js app (auth, dashboard, harmonization workspace)
raw_data/              bundled demo "dirty" datasets
src/data_harmonizer/
  ingestion/           encoding/delimiter-sniffing CSV loader
  transformations/     country, dates, numerics, missing_values, duplicates, schema
  pipeline/            Harmonizer engine + CLI runner
  validation/          PASS/FAIL validation gate
  reporting/           quality report, transformation log, charts
  storage/             SQLite writer (optional CLI output)
supabase/              migrations (schema, RLS, storage buckets, seed helpers)
tests/                 pytest suite incl. golden-fixture regression
scripts/               convenience scripts
```

---

## Quickstart

Prerequisites: **Python 3.11+**, **Node 20+**, and the **Supabase CLI** (for local stack).

### 1. Engine + CLI (no network needed)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,reporting,backend]"

# Run the demo pipeline (validation + SQLite + chart)
.venv/Scripts/python.exe -m data_harmonizer.pipeline.runner --validate --sqlite --chart

# Or via the installed console script
.venv/Scripts/data-harmonize --validate
```

Outputs land in `processed_data/<pipeline_id>/`:
`harmonized_data.csv` · `harmonized_data.db` · `quality_report.json` · `transformation_log.json`
· `pipeline_summary.json` · `pipeline_summary.md` · `final_analytics_chart.png`.

### 2. Local stack (Supabase + API + web)

```bash
# Start Postgres/Auth/Storage
supabase start                      # prints http://127.0.0.1:54321 etc.

cp backend/.env.example backend/.env
# fill in SUPABASE_URL / ANON_KEY / JWT_SECRET from `supabase status`

cp frontend/.env.example frontend/.env.local
# fill in the same keys + NEXT_PUBLIC_API_URL=http://127.0.0.1:8000

# Backend (http://localhost:8000/api/docs)
.venv/Scripts/python.exe -m uvicorn backend.main:app --reload

# Frontend (http://localhost:3000)
cd frontend && npm install && npm run dev
```

Register an account, click **Load demo workspace** to wire up the two bundled datasets,
then open the workspace, toggle which sources to include, and hit **Run pipeline**.

### 3. Tests & lint

```bash
.venv/Scripts/python.exe -m pytest          # 39 tests incl. golden-fixture regression
.venv/Scripts/python.exe -m ruff check src tests backend
```

---

## CLI reference (engine)

```
data-harmonize --input file1.csv --input file2.csv --names A,B \
               --validate --sqlite --chart --config config.json --log-level DEBUG
```

| Flag | Meaning |
| --- | --- |
| `--input` | One or more source CSVs (default: raw_data demo set) |
| `--names` | Comma-separated logical source names |
| `--out` | Output directory (default: `processed_data/<pipeline_id>/`) |
| `--validate` | Run the PASS/FAIL validation gate (exit code 1 on FAIL) |
| `--sqlite` | Also write the SQLite copy of the output |
| `--chart` | Render the quality chart (needs `.[reporting]`) |
| `--config` | JSON file with HarmonizationConfig overrides |
| `--version` | Print version and exit |

---

## Configuring harmonization behavior

`HarmonizationConfig` (in `src/data_harmonizer/config.py`) is a frozen dataclass. Overridable
behaviors include:

- `conflict_policy`: `keep_first_non_null` (merge duplicates, pick first non-null per metric) or
  `keep_first_row`.
- `year_imputation`: `none` (preserve NULL) or `default` + `default_year` (impute AND audit it).
- `missing_imputation`: `none` (preserve NULL) or `mean`/`constant`.
- `thresholds` / `ranges`: validation limits.

---

## Deployment

- **API** → Render. Commit and use the blueprint: Services → Blueprint → `global-data-harmonizer-pipeline`.
  Fill the `SUPABASE_*` secrets from a hosted Supabase project.
- **Web** → Vercel. Import the repo, set **Root Directory** to `frontend`, add the
  `NEXT_PUBLIC_*` env vars.
- **Database** → push migrations to hosted Supabase: `supabase link --project-ref <ref>` then
  `supabase db push`.

---

## License

MIT. This project was built as a reference implementation of a data-engineering platform and is
not affiliated with the World Bank or the UN.