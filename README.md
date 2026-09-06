# UK Energy Grid Simulator

An interactive what-if simulator for the UK electricity grid. Adjust how much
generation comes from each source (and what it costs) and see whether the
resulting mix would meet demand across a full year, what it would cost, and
how much CO2 it would emit.

## How it works

The backend simulates 365 days, each split into a 12-hour "day" period and a
12-hour "night" period (730 periods total):

- **Solar** (field + rooftop) only generates during the day, with a fixed
  seasonal profile (much more in summer than winter). Rooftop is capped at an
  estimate of usable UK roof area.
- **Nuclear** generates flat output year-round, day and night.
- **Onshore/offshore wind** use seasonal average wind capacity factors (higher
  in winter) plus day-to-day intermittency, generated once from a fixed random
  seed so the "weather" doesn't change when you move a price slider - only
  when you change capacity does the delivered output change. Offshore wind's
  price grows a separate, displayed, grid-distribution cost as its capacity
  increases.
- **Gas** cost is driven by a fuel commodity price slider, converted to a
  £/MWh electricity price via a fixed plant efficiency.
- **Biomass** and four **interconnectors** (France, Norway, Belgium,
  Netherlands) are dispatched in merit order (cheapest price first) to fill
  any gap between demand and must-run generation (nuclear/wind/solar).
- **Enhanced geothermal** (EGS) is modelled like nuclear: flat baseload,
  unaffected by weather or season, reflecting technology that can be sited
  almost anywhere rather than only on natural hot springs.
- **Tidal power** is fully predictable but not flat - output follows the
  ~14.77 day spring/neap tidal cycle (bigger tides, more power, around
  new/full moon), generated deterministically rather than randomly like wind.
- **The Morocco solar link** is a single very long subsea HVDC cable (styled
  on the proposed Xlinks Morocco-UK project) that imports Moroccan
  solar/wind + storage. It's dispatched like an interconnector, and folds
  into the "Interconnectors" category on the charts.
- **Batteries** (short-duration) and **other storage** (pumped-hydro-like,
  long-duration) charge from surplus generation and discharge to cover
  shortfalls, in that priority order.
- **Curtailment** happens when surplus generation can't be absorbed by
  storage; the curtailed generator is still paid for the lost output.
- **Demand** follows a seasonal baseline (higher in winter, split ~58%
  day/42% night) plus four adjustable electrification levers: heat pumps
  (winter-weighted), EVs (mostly overnight charging), industry (flat), and
  air conditioning (May-September, daytime only).

All figures (capacities, costs, capacity factors, demand growth) are
illustrative approximations of the mid-2020s UK grid for an educational
tool - not official statistics.

Five presets are included alongside the "current mix" default:
**No fossils, no new nuclear**, **Renewables only**, **Nuclear
renaissance**, and **Dash for Gas** (renewables, biomass, interconnectors
and storage all retired; gas capacity expanded so gas supplies ~80% of
demand, with existing nuclear providing the rest) - each a starting point
you can then fine-tune with the sliders.

## Project layout

```
backend/   FastAPI + Python simulation engine
frontend/  React + TypeScript + recharts UI
```

## Running locally

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run the test suite with `pytest` from the `backend/` directory.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`, so run the
backend first. Then open the printed local URL (default
`http://127.0.0.1:5173`).

### Production build

```bash
cd frontend
npm run build
```

Serve the built `frontend/dist` behind any static host, with the FastAPI app
reachable at `/api`.
