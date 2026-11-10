# Clearhaul: Weather-Aware Truck Routing

A React + Django web app that helps a truck driver choose the safest route for a trip, based on weather, load weight and travel time.

You enter an origin, destination, departure date and time, and load weight. The app finds up to three truck routes, reads the forecast for the hour the truck will reach each checkpoint, scores the risk with load-specific wind rules, and recommends a route. A weather heatmap along the trip corridor has a 0–48 hour forecast slider.

| | |
|---|---|
| **Live app** | https://clearhaul-routing.vercel.app |
| **API** | https://weather-aware-truck-routing-ruby.vercel.app/api/health |
| **Walkthrough** | _Loom link to be added_ |

The first request after a quiet period can take a few seconds while the backend starts.

## Contents

- [How a route is chosen](#how-a-route-is-chosen)
- [Architecture](#architecture)
- [API](#api)
- [Running locally](#running-locally)
- [Tests](#tests)
- [Deployment](#deployment)
- [Assumptions](#assumptions)
- [Limitations](#limitations)
- [Project documents](#project-documents)

## How a route is chosen

### 1. Routes

TomTom truck routing is asked for the best route plus 2 alternatives, using the truck's weight and departure time. TomTom sometimes returns fewer, so the app then re-routes through a point offset to each side of the trip's midpoint and keeps only routes that differ meaningfully from the ones it has. Some short trips have no real alternative. The app then shows the routes that exist and says so.

### 2. Checkpoints and arrival times

Checkpoints sit at the origin, every 10, 25 or 50 miles (chosen by the user, default 25), and at the destination. Each checkpoint covers half the distance to its neighbors on each side, so the miles per risk level add up exactly to the route's length.

Each checkpoint's ETA follows TomTom's own timing along the route, not a constant speed.

### 3. Weather at the ETA

Weather comes from Open-Meteo and is read **at each checkpoint's ETA**, not at departure.

- **Wind** is the sustained 10 m wind, interpolated between hours.
- **Rain** is `rain + showers`, for the hour that contains the ETA. Open-Meteo reports convective showers separately, so using `rain` alone would under-report storms.
- **Snow** is `snowfall`, for the hour that contains the ETA.

Missing weather is never treated as Low. If the forecast doesn't cover the whole trip, the departure is rejected with a clear message.

### 4. Risk per checkpoint

Wind, rain and snow are each given a level, and the checkpoint takes the worst of the three.

| Level (score) | Wind mph | Rain in/hr | Snow in/hr |
|---|---|---|---|
| Low (0) | < 25 | < 0.10 | < 0.5 |
| Moderate (1) | 25 to < 35 | 0.10 to < 0.25 | 0.5 to < 1.0 |
| High (2) | 35 to < 45 | 0.25 to < 0.50 | 1.0 to < 2.0 |
| Severe (3) | 45 to < 55 | 0.50 to 1.00 | 2.0 to 3.0 |
| No Travel (4) | ≥ 55 | > 1.00 | > 3.0 |

Load rules apply to wind:

- Wind ≥ 55 mph: No Travel for any load.
- Wind 45–54 mph with a load over 30,000 lb: No Travel.
- Wind 35–44 mph with a load over 40,000 lb: Severe.

### 5. Recommendation

Routes are compared in this order, and the first difference decides:

1. Fewest No Travel miles
2. Fewest Severe miles
3. Fewest High miles
4. Lowest distance-weighted average risk (0 to 4, rounded to 2 decimals)
5. Shortest travel time

The app explains the deciding reason in plain words, for example "Weather risk matches Route B, and this route is 2 h 37 min faster." If every route has No Travel miles, no route is recommended and the app says that no route is safe at that departure.

### 6. Corridor heatmap

The backend lays a grid over the corridor around all routes and scores every cell for each hour from 0 to 48 after departure, using the same risk rules and the entered load.

- **Grid:** cells sit on a fixed Web Mercator lattice. The finest spacing that fits in 300 cells is used, from about 7 miles on short trips to about 100 miles coast to coast.
- **Payload:** each hour is a string with one character per cell (`0`–`4`, or `-` where the forecast has no data). All 49 hours together come to about 10 KB.
- **Drawing:** the frontend draws all 49 hours to bitmaps once. Moving the slider only swaps which bitmap a MapLibre canvas source shows, with no network request and no GeoJSON rebuild.
- **Measured speed:** on the production build, a drag across all 49 hours produced no frame over 50 ms and no input event over 16 ms. Each step's script took at most 0.2 ms.
- **Missing forecast:** cells without a forecast are left blank, never painted as Low.

## Architecture

```
Browser (React, MapLibre)
   │  JSON over HTTPS
   ▼
Django REST API (stateless, no database)
   ├── TomTom Routing API    truck routes with departure time and weight
   ├── TomTom Search API     address autocomplete, worldwide
   └── Open-Meteo API        hourly forecasts, cached for 15 minutes
```

API keys stay on the server, and the browser only talks to the Django API. Nothing is stored: every trip is calculated per request.

The trip plan and the heatmap are separate requests, so routes appear first and the heatmap fills in after.

### Backend (`backend/`)

| Package | Responsibility |
|---|---|
| `risk/` | Risk thresholds and load rules (`classification.py`), mile totals and ranking (`recommendation.py`). Pure functions, no I/O |
| `routing/` | TomTom client (`tomtom.py`), the three-route fallback (`options.py`), checkpoint sampling and ETAs (`checkpoints.py`), and geometry helpers |
| `weather/` | Open-Meteo client with batching, retries and caching (`open_meteo.py`), and reading a forecast at a given time (`forecast.py`) |
| `trips/` | Joins the pieces: `planner.py` builds a trip plan, `heatmap.py` builds the corridor grid and hourly frames |
| `api/` | Views, request validation, request limits, and errors returned as `{"error": "..."}` |
| `config/` | Settings from environment variables, production security settings |

The risk and ranking code knows nothing about HTTP or providers. The planner takes the routing and weather clients as arguments, so tests swap in fakes.

### Frontend (`frontend/src/`)

| Folder | Responsibility |
|---|---|
| `api/` | Typed API client and response types |
| `trip/` | Trip form: address search, departure in the origin's local time, load, checkpoint interval, validation |
| `results/` | Verdict, route comparison, checkpoint details, and number formatting |
| `map/` | MapLibre map, route and checkpoint layers, and the heatmap canvas layer |
| `forecast/` | Heatmap loading, frame drawing and the 0–48 h slider |
| `risk/` | Risk levels, colors and road-sign glyphs |
| `components/` | App shell: top bar, map frame, recommendation seal, error boundary |

Every risk level has its own shape as well as its own color (circle, triangle, square, diamond, octagon), so risk never relies on color alone. The design system is described in [DESIGN.md](DESIGN.md).

### Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.14, Django 5.2 LTS, Django REST Framework, httpx |
| Frontend | React 19, TypeScript, Vite, Tailwind 4, Downshift |
| Map | MapLibre GL JS with OpenFreeMap Positron tiles (no key needed) |
| Routing and search | TomTom Routing and Search APIs |
| Weather | Open-Meteo forecast API (no key needed) |
| Tests | pytest with pytest-django, Vitest |
| Hosting | Vercel, as two projects from this repository |

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/geocode?q=` | Address suggestions |
| `GET /api/timezone?lat=&lon=` | The origin's time zone, so departure can be entered in local time |
| `POST /api/trips/plan` | Trip plan: routes, checkpoints, risk, ETAs, summaries and the recommendation |
| `POST /api/heatmap` | Corridor grid and 49 hourly risk frames |

Example trip plan request. `departure` is the local time at the origin, without an offset:

```json
{
  "origin": { "lat": 41.8781, "lon": -87.6298 },
  "destination": { "lat": 39.7392, "lon": -104.9903 },
  "departure": "2026-11-12T08:00",
  "load_lb": 42000,
  "interval_miles": 25
}
```

The response gives `recommended_route_id` (or `null` when no route is safe), `ranked_route_ids`, and for each route its distance, duration, arrival, `miles_by_risk`, `average_risk`, geometry and checkpoints. The heatmap request takes the `corridor` line of each route, the `departure` returned by the plan, and the load.

Errors come back as `{"error": "A clear message."}` with a matching HTTP status.

## Running locally

You need Python 3.14, Node 22.12 or later, and a free TomTom API key from [developer.tomtom.com](https://developer.tomtom.com).

1. Create the environment file at the repository root and fill in `DJANGO_SECRET_KEY` and `TOMTOM_API_KEY`:

   ```bash
   cp .env.example .env
   ```

   Both the backend and the frontend read this one file. A secret key can be generated with:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

2. Start the backend at http://localhost:8000:

   ```bash
   cd backend
   python3.14 -m venv .venv
   .venv/bin/pip install -r requirements-dev.txt
   .venv/bin/python manage.py runserver
   ```

3. In a second terminal, start the frontend at http://localhost:5173:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

The frontend must run on port 5173, because that's the origin the backend allows by default.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

```bash
cd frontend && npm test
```

```bash
cd frontend && npm run typecheck
```

- **Backend (407 tests):** every risk boundary value and load rule, every ranking tie-break, the route fallback and de-duplication against saved TomTom responses, checkpoint spacing and ETAs, forecast lookup at the ETA, missing-forecast handling, heatmap grid sizing, request validation, request limits and error responses. Tests never call TomTom or Open-Meteo.
- **Frontend (103 tests):** form validation and local-time handling, the API client and its errors, map data, the recommendation reason, heatmap frame drawing, and number formatting.

## Deployment

Both parts run on Vercel as two projects from this repository.

| Project | Root directory | Environment variables |
|---|---|---|
| Backend | `backend` | `DJANGO_SECRET_KEY`, `TOMTOM_API_KEY`, `CORS_ALLOWED_ORIGINS` (the frontend's address) |
| Frontend | `frontend` | `VITE_API_BASE_URL` (the backend's address) |

- **Backend:** Vercel detects Django through `manage.py` and serves `config/wsgi.py` as a Python function (`backend/vercel.json`, Python version in `backend/.python-version`). The deployment's own `vercel.app` hostnames are added to `ALLOWED_HOSTS` automatically.
- **Production settings:** with `DJANGO_DEBUG` unset, Django redirects HTTP to HTTPS and sends HSTS and frame protection headers. CORS allows only the frontend's address.
- **Frontend:** a static Vite build. `frontend/vercel.json` caches the hashed assets for a year and adds security headers. `VITE_API_BASE_URL` is built into the bundle, so changing it needs a redeploy.

## Assumptions

1. **"Every 10 / 25 / 50 miles"** is an interval the user chooses. The default is 25.
2. **Band edges:** the rain and snow tables overlap at their edges (for example 0.25 in/hr is in both Moderate and High). The value goes to the higher band. The exceptions are 1.00 in/hr rain and 3.0 in/hr snow, which stay Severe, because No Travel is written as strictly greater.
3. **No Travel ranks worse than Severe.** The brief's ranking doesn't mention it, but a route with No Travel miles can't be better than one with only Severe miles.
4. **Wind** means sustained wind at 10 m, not gusts.
5. **Slider hour 0 is the departure time.** The label shows the actual date and time.
6. **Load rules use the entered load weight.** For truck-legal routing, TomTom receives the load plus an assumed 33,000 lb empty truck, converted to kg.
7. **ETAs are drive time only.** Mandatory driver rest breaks aren't modeled.
8. **Trucks are capped at 65 mph.** Without a cap, TomTom assumes road speed limits (up to 78 mph on tested routes), which would read the weather too early on long trips.
9. **Address search covers every country.** Places outside the US show their country, because many place names repeat across countries (Islamabad, Pakistan and Islamabad, India). Units stay in miles, pounds, mph and inches per hour, as in the brief.
10. **Forecasts cover 14 days from today.** A trip that would still be driving after that is rejected rather than scored with missing weather.
11. **Departures up to 15 minutes in the past are accepted,** because the form defaults to the current time. Anything older is rejected.
12. **Heatmap detail depends on trip length,** to stay within the free weather API's limits. Cells range from about 7 miles on short trips to about 100 miles coast to coast.
13. **Each connection has request limits** (60 trip plans and 60 heatmaps an hour, plus generous limits for address search), so that a public link can't use up the TomTom and Open-Meteo quotas.

## Limitations

- **Free weather quota:** Open-Meteo's free tier allows 600 calls a minute and 10,000 a day, and each checkpoint or heatmap cell location costs one call. Several long trips in the same minute can reach that limit, and the app then asks the user to try again shortly.
- **Per-instance cache:** forecasts are cached in memory for 15 minutes on each server instance, so a cold start begins with an empty cache.
- **Startup delay:** the first request after a quiet period waits for the serverless backend to start.
- **Forecast, not observation:** risk is only as good as the forecast, and forecasts further out are less certain.

## Project documents

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): the plan, build order and decisions
- [PRODUCT.md](PRODUCT.md): users, purpose and product principles
- [DESIGN.md](DESIGN.md): the visual design system
