# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Insight 经营分析系统** — A business operations analysis platform for a Product Center head managing 5 business divisions (智能建造、大数据、数字交易、智慧政务、创新业务). Tracks three metrics per division: 合同 (contract), 收入 (revenue), 回款 (payment).

## Development Commands

### Docker (primary workflow)
```bash
docker-compose up --build          # dev with hot reload on both services
docker-compose up -d               # detached
docker-compose logs -f backend     # follow backend logs
docker-compose restart backend     # restart one service after code change that doesn't hot-reload
docker-compose -f docker-compose.prod.yml up --build  # production build
```

### Local (without Docker)
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Access
- Frontend: http://localhost:5173
- Backend API docs (Swagger): http://localhost:8010/docs
- Backend port is mapped **8010→8000** (8000 is occupied by another project on this machine)

## Architecture

### Backend (`backend/`)
FastAPI app with SQLite via SQLModel. All routes go through `main.py` which registers five routers:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `routers/targets.py` | `/api/targets` | Annual targets + monthly breakdown CRUD |
| `routers/actuals.py` | `/api/actuals` | Monthly actual data CRUD |
| `routers/opportunities.py` | `/api/opportunities` | Opportunity pipeline CRUD |
| `routers/dashboard.py` | `/api/dashboard` | Aggregated analytics (no writes) |
| `routers/imports.py` | `/api/import` | File upload handling |

Database initializes at startup (`database.py::init_db`) — creates tables and seeds 5 business units (idempotent). Session dependency: `get_session()` generator injected via `Depends`.

**Dashboard query pattern** — helpers in `dashboard.py` return `dict[(unit_id, metric_type): amount]` for O(1) lookup when assembling response objects:
```python
ytd_a = _ytd_actual(session, year, cur_month)  # {(unit_id, "contract"): 1234.5, ...}
actual = ytd_a.get((unit.id, metric), 0.0)
```
YTD target falls back to `annual_target / 12 * cur_month` when no monthly breakdown exists.

**Import service** (`services/importer.py`) has two opportunity import paths:
- `import_opportunities()` — standard template format (columns: 商机名称, 所属事业部, etc.)
- `import_opportunities_native()` — raw "产品中心商机预测" Excel format with sheets named 合同/收入/回款, merged cells in column A, subtotal rows

`routers/imports.py` auto-detects which path to use by checking if the uploaded `.xlsx` contains all three sheet names.

**Business unit aliases** in `importer.py::UNIT_ALIAS` map variant names to canonical names:
- `智慧建造事业部` → `智能建造事业部`
- `综合事业部` → `创新业务事业部`

**All API responses** follow `ApiResponse` schema: `{ success, message, data }`.

### Frontend (`frontend/src/`)
Vue 3 + Vite SPA. Key files:

- `App.vue` — shell layout (sidebar + topbar). Fetches business units on mount, stores in Pinia.
- `stores/app.js` — single Pinia store holds `year` (global year selector) and `units` list.
- `api/index.js` — single axios instance at `/api` (proxied to backend). Response interceptor unwraps `res.data` so callers receive the inner object directly.
- `router/index.js` — 8 lazy-loaded routes. `/division/:id` takes business unit DB ID.

**ECharts usage**: Each view that renders charts imports only the required ECharts components (tree-shakable). Use `vue-echarts` `<v-chart>` component with `:option` binding and `autoresize`.

**Vite proxy**: In development, `/api/*` proxies to `VITE_BACKEND_URL` (defaults to `http://localhost:8010` locally; set to `http://backend:8000` in Docker via env var in `docker-compose.yml`).

### Data Model Key Points
- `metric_type` is always stored as English: `contract` / `revenue` / `payment`
- Chinese ↔ English mapping lives in `importer.py::METRIC_MAP` and frontend constants
- `MonthlyActual` has a unique constraint on `(year, month, business_unit_id, metric_type)` — imports overwrite, not append
- `ImportBatch.fail_detail` stores a JSON string array of `{row, reason}` objects
- Opportunity `stage`: 线索 → 立项 → 报价 → 签约跟进 → 已完成
- Opportunity `status`: 进行中 / 已赢单 / 已输单 / 已搁置

## Conventions

- Backend private helpers are prefixed `_` (e.g. `_ytd_actual`, `_normalize_unit`)
- Module-level constants in UPPERCASE (`METRIC_MAP`, `UNIT_ALIAS`, `STAGE_VALUES`)
- All timestamps use `datetime.utcnow()`
- Frontend views call API functions from `@/api` — no direct axios calls in components
- Business unit `sort_order` (1–5) controls display order throughout the UI
