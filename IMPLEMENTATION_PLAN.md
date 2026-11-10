# Weather-Aware Truck Routing: Implementation Plan

React + Django app that helps a truck driver choose the safest route based on weather, load weight and travel time.

**Deliverables:** GitHub repository, hosted application, 5–10 min Loom walkthrough.

**Scoring:** 40% routes, weather, risk and recommendation logic · 40% UI, map and heatmap smoothness · 15% code quality · 5% docs and walkthrough. The brief says to prioritize correctness and clarity over extra features, so anything it doesn't ask for is left out.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Django 5.2 LTS + Django REST Framework | Required by the brief. Stateless JSON API, API keys stay on the server |
| Frontend | React + TypeScript + Vite | Required by the brief. Typed API contract |
| Map | MapLibre GL JS + OpenFreeMap Positron tiles | WebGL rendering, tiles need no API key, and a quiet base map leaves risk as the strongest color |
| Interface | Downshift, native range slider, Tailwind 4 | Compared by measured bundle size. three.js and deck.gl were left out because they add weight and put the slider's frame budget at risk without serving a required feature. Motion and Lucide turned out to be unnecessary: two CSS animations and drawn SVG shapes covered the need |
| Design | Printed "design annual" language, recorded in `DESIGN.md` | Chosen by the owner: professional, and not a generic dashboard |
| Routing and geocoding | TomTom Routing and Search APIs | Real truck mode, vehicle weight, up to 5 alternatives, future `departAt` |
| Weather | Open-Meteo forecast API | No key, hourly data, many locations per request |
| Tests | pytest (backend), Vitest (frontend logic) | Risk and ranking rules are fully unit tested |
| Hosting | Vercel (frontend) + Render (backend) | Simple deploys. Render's free tier sleeps, so wake it before the Loom or a review |

Confirmed before choosing:

- TomTom docs: `travelMode=truck`, `vehicleWeight` in kg, `maxAlternatives` 0–5, `departAt`. The docs warn that **fewer alternatives may be returned**, so the app needs a fallback (commit 5).
- Open-Meteo live call: comma-separated coordinates return one result per location, `rain`, `showers` and `snowfall` come back in inches, wind in mph, and `timezone=auto` returns each location's timezone.
- Open-Meteo response headers: each location costs 1 call, whatever the forecast length up to 14 days. The free limits are 600 calls a minute, 5,000 an hour and 10,000 a day, so caching matters and a heatmap has to stay within a few hundred points.

Still to confirm at deploy time:

- Current TomTom free-tier numbers, since its pricing changed in July 2026.

## Core logic

### Risk classification

Each checkpoint gets a level for wind, rain and snow. The load rules are applied to wind, and the worst of the three is the checkpoint's level.

| Level (score) | Wind mph | Rain in/hr | Snow in/hr |
|---|---|---|---|
| Low (0) | < 25 | < 0.10 | < 0.5 |
| Moderate (1) | 25 to < 35 | 0.10 to < 0.25 | 0.5 to < 1.0 |
| High (2) | 35 to < 45 | 0.25 to < 0.50 | 1.0 to < 2.0 |
| Severe (3) | 45 to < 55 | 0.50 to 1.00 | 2.0 to 3.0 |
| No Travel (4) | ≥ 55 | > 1.00 | > 3.0 |

Load rules:

- Wind ≥ 55 mph: No Travel for any load.
- Wind 45–54 mph and load > 30,000 lb: No Travel.
- Wind 35–44 mph and load > 40,000 lb: Severe.

### Weather at the truck's arrival time

- Forecast is looked up at the checkpoint's **ETA**, not the departure time.
- Rain is `rain + showers`, because Open-Meteo reports convective showers separately and using `rain` alone would under-report storms.
- Precipitation uses the hour that contains the ETA. Open-Meteo stamps each total at the end of its hour, so a 10:30 ETA reads the 11:00 value. Wind is an instant value and is interpolated between hours.
- All times are handled in UTC. Departure is entered in the origin's local time, and ETAs are shown in each checkpoint's local time.
- Missing weather is **never treated as Low**. The request fails with a clear error, or the departure is rejected if the trip runs past the forecast window.

### Checkpoints and miles

- Checkpoints sit at the origin, every N miles (10, 25 or 50, chosen by the user), and the destination.
- Each checkpoint covers half the gap on either side, so the per-level miles add up exactly to the route length.
- ETAs follow the route's own timing between maneuvers rather than assuming constant speed.

### Recommendation

Routes are compared strictly in this order, and the first difference decides:

1. Fewest No Travel miles (see assumption 3)
2. Fewest Severe miles
3. Fewest High miles
4. Lowest distance-weighted average risk (rounded to 2 decimals)
5. Shortest travel time

If every route has No Travel miles, the app says no route is safe at that departure instead of presenting one as recommended.

### Three routes

Request 2 alternatives from TomTom. If fewer than 3 distinct routes come back, re-request through a waypoint offset to each side of the trip's midpoint and keep routes that differ meaningfully from the others. If 3 still can't be found (some short trips have no real alternative), show what exists and say so.

### Heatmap (the performance-critical piece)

- Backend builds a grid along the corridor of all routes, spaced evenly in Web Mercator, and sends the risk level per cell for hours 0–48 as one compact payload. Risk is calculated only on the backend, using the same engine and the entered load.
- Frontend draws all 49 frames to bitmaps once, up front. Moving the slider only swaps which bitmap is drawn to a MapLibre canvas source: **no network request and no GeoJSON reprocessing per step**.
- Grid cells sit on a fixed lattice and forecasts are cached, so trips can share cells. Each cell costs one Open-Meteo call, so the finest lattice (0.125° to 2°) that fits within 300 cells is used: short trips get a detailed grid and cross-country trips a coarser one.
- Each frame is a string with one character per corridor cell, so all 49 frames come to about 10 KB. Hours the forecast doesn't reach are marked and left blank on the map, never shown as Low.
- The heatmap loads separately from the routes, so routes appear first.
- Target: under 16 ms per slider step. Measured in commit 14 on the production build: a real drag across all 49 hours produced no frame over 50 ms and no input event over 16 ms, each step's script took at most 0.2 ms, and the slider made no network requests.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/geocode?q=` | Address autocomplete proxy |
| `GET /api/timezone?lat=&lon=` | The origin's timezone, so the form can show and default to its local time |
| `POST /api/trips/plan` | Origin, destination, departure, load, interval → routes, checkpoints, summaries, recommendation |
| `POST /api/heatmap` | Route corridor lines from the trip plan, departure, load → grid and 49 hourly frames |

## Commit-by-commit plan

Each step leaves the project working, with tests passing where there is logic to test.

| # | Commit | Contents |
|---|---|---|
| 1 | `chore: initialize repository` | `.gitignore`, `.env.example`, README stub, this plan |
| 2 | `feat(backend): scaffold Django API` | Project, DRF, env-based settings, CORS, health endpoint, pytest |
| 3 | `feat(risk): add weather risk engine` | Thresholds, load rules, tests on every boundary value |
| 4 | `feat(risk): add route recommendation` | Mile totals, average risk, ranking, tie-break tests |
| 5 | `feat(routing): add TomTom routing and geocoding` | Clients, 3-route fallback, de-duplication, tests on saved responses |
| 6 | `feat(routing): add checkpoint sampling and ETAs` | 10/25/50-mile sampling along the route, ETA calculation, tests |
| 7 | `feat(weather): add Open-Meteo client` | Batched requests, caching, retries, ETA lookup, tests |
| 8 | `feat(api): add trip planning endpoint` | Ties it together, validation, clear error responses |
| 9 | `feat(api): add corridor heatmap endpoint` | Grid generation, 49 hourly frames, compact payload |
| 10 | `feat(frontend): scaffold React app and map` | Vite, TypeScript, MapLibre, typed API client, layout |
| 11 | `feat(frontend): add trip form` | Autocomplete, departure, load, interval, validation |
| 12 | `feat(frontend): show routes and checkpoints` | Route lines, risk-colored checkpoints, ETAs, summaries, recommended route |
| 13 | `feat(frontend): add heatmap and forecast slider` | Bitmap frames, canvas layer, 0–48 h slider, legend |
| 14 | `perf(frontend): polish states and performance` | Loading, error and No Travel states, mobile layout, measured slider timing, final design review, `DESIGN.md` |
| 15 | `chore: add deployment config` | Vercel and Render config, production settings |
| 16 | `docs: complete README` | Setup, architecture, assumptions, hosted link, Loom link |

**Workflow for each step:** I implement and test it, stage only that step's files with `git add`, and give you the exact commit and push commands. I never commit or push. I start the next step after you confirm.

## Assumptions (also documented in the README)

1. **"Every 10 / 25 / 50 miles"** is a user-selectable interval, defaulting to 25.
2. **Band edges:** the rain and snow tables overlap at their edges (for example 0.25 is in both Moderate and High). The value moves to the higher band. The exceptions are 1.00 in/hr rain and 3.0 in/hr snow, which stay Severe because No Travel is written as strictly greater.
3. **No Travel ranks worse than Severe.** The brief's ranking doesn't mention it, but a route with No Travel miles can't be better than one with only Severe miles.
4. **Wind** means sustained wind at 10 m, not gusts.
5. **Slider hour 0 is the departure time.** The label shows the actual date and time.
6. **Load rules use the entered load weight.** For truck-legal routing, TomTom receives load plus an assumed 33,000 lb empty truck, converted to kg.
7. **ETAs are drive time only.** Mandatory driver rest breaks aren't modeled.
8. **Trucks are capped at 65 mph.** Without a cap, TomTom assumes road speed limits (up to 78 mph on tested routes), which would read the weather too early on long trips.
9. **Address search covers the US, Canada and Mexico**, matching the brief's miles and pounds.
10. **Forecasts cover 14 days from today.** A trip that would still be driving after that is rejected rather than scored with missing weather.
11. **Departures up to 15 minutes in the past are accepted,** because the form defaults to the current time. Anything older is rejected.
12. **Heatmap detail depends on trip length,** to stay within the free weather API's limits. Cells range from about 7 miles on short trips to about 100 miles coast to coast.

## Needed from you

- An empty GitHub repository (no README or license), before commit 1 is pushed.
- A TomTom API key from developer.tomtom.com, before commit 5. It goes in your local `.env`, which is never committed.
- Vercel and Render accounts, before commit 15.
