# UK Energy Grid Simulator

An interactive what-if simulator for the UK electricity grid. Adjust how much
generation comes from each source (and what it costs) and see whether the
resulting mix would meet demand across a full year, what it would cost, and
how much CO2 it would emit.

## How it works

The backend simulates 365 days, each split into 24 hourly periods (8,760
periods total):

- **Solar** (field + rooftop) follows a realistic intraday curve derived from
  solar geometry: sunrise, sunset, and day length shift with the season (and
  with latitude, see below), so winter days have a short midday-centred
  window of output and summer days a much longer one. The same astronomical
  daily-total calibration as before is preserved exactly - only *when within
  the day* that total is delivered has changed. Rooftop is capped at an
  estimate of usable UK roof area. A latitude toggle lets you compare the
  UK's actual latitude (~51.5°N) against the latitude of Madrid/New York
  (~40°N) or Houston (~30°N) - the same installed panels deliver more energy
  at a lower latitude, both because of a higher midday sun angle and,
  especially, a much smaller winter slump. This is derived from the standard
  astronomical formula for daily extraterrestrial irradiation (solar
  declination + day-length/sun-angle integral), so it captures the pure
  geometric effect of latitude only - it deliberately excludes the extra
  boost Madrid/Houston get in reality from being drier and less cloudy than
  the UK, consistent with solar's "ignore weather" simplification elsewhere.
- **Nuclear** generates flat output year-round, hour by hour.
- **Onshore/offshore wind** use seasonal average wind capacity factors (higher
  in winter) plus hour-to-hour intermittency with realistic persistence (an
  autocorrelated random walk, so windy/calm spells last for several hours
  rather than the capacity factor jumping independently every hour),
  generated once from a fixed random seed so the "weather" doesn't change
  when you move a price slider - only when you change capacity does the
  delivered output change. Offshore wind's price grows a separate, displayed,
  grid-distribution cost as its capacity increases.
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
- **Hydro** (natural flow / run-of-river, not pumped storage) follows the
  same seasonal shape as wind - more output in the wet winter months, less
  in summer - but deterministically rather than randomly.
- **Batteries** (short-duration), **vehicle-to-grid (V2G)** (medium-duration),
  and **pumped storage hydro** (long-duration) charge from surplus generation
  and discharge to cover shortfalls, in that priority order. V2G has no
  capacity slider of its own - its energy pool scales with the "Electrify
  cars / transport" demand slider (the size of the electrified car fleet),
  and a participation slider sets what share of that fleet's batteries are
  actually available to the grid (bundling opt-in rate, plugged-in
  availability, and allowed depth-of-discharge into one number). Its power
  rating comes from a typical bidirectional home charger (7kW), so a car's
  battery divided by its charger's power gives a fixed ~8.6h duration,
  regardless of fleet size or participation. At hourly resolution, a
  storage type's power rating is a real constraint on discharge - a
  short-duration battery with plenty of charge can still be capped at its
  rated power for an hour, rather than always being able to empty its whole
  state of charge in one period the way it could at the old 12-hour-block
  resolution.
- **Curtailment** happens when surplus generation can't be absorbed by
  storage; the curtailed generator is still paid for the lost output. A
  shortfall works the other way round: when generation, storage and imports
  together can't cover demand, the gap shows up as unmet demand, both as a
  headline reliability banner and as a day-by-day chart beneath the supply
  chart.
- **Demand** follows a seasonal baseline (higher in winter) shaped across
  each day with a realistic hourly curve (an overnight trough, morning ramp,
  and evening peak), plus four adjustable electrification levers each with
  their own intraday shape: heat pumps (winter-weighted, morning/evening
  heating ramps), EVs (mostly overnight charging), industry (a daytime shift
  pattern), and air conditioning (May-September, afternoon-peaking).

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

`--reload` is a development convenience (it watches source files and restarts
on change) - see "Deploying" below for a production launch command.

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

## Deploying

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Don't use `--reload` in production - it adds file-watching overhead and is
meant for local development only. Pick a worker count suited to the host
(the simulation itself is cheap - a few hundred milliseconds per request - so
this is about handling concurrent requests, not CPU-bound work per request).

Two things worth setting explicitly for a public deployment:

- **CORS**: the API allows all origins (`*`) by default, since there's no
  auth or user data here - just a stateless calculator. Set the
  `ALLOWED_ORIGINS` environment variable to a comma-separated list (e.g.
  `https://example.com,https://www.example.com`) to restrict which sites can
  call it from a browser.
- **Reverse proxy**: the frontend calls the backend at the relative path
  `/api`, which only works if your deployment routes that path to the
  backend (e.g. an nginx `location /api { proxy_pass ... }` block, or a
  platform's built-in path-based routing). If frontend and backend are
  deployed to entirely separate origins without such a proxy, requests to
  `/api/*` will 404.
