# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated, with the owner approving the recommendation: React, TypeScript, Vite, MapLibre GL JS with OpenFreeMap tiles, Downshift, a native range input for the forecast slider, and Tailwind 4. three.js and deck.gl were considered and left out because they add weight and risk to the map's frame budget without serving a required feature. Motion and Lucide were approved too, but the finished interface needed only two CSS animations and a handful of drawn shapes, so neither was added. The backend is Django REST Framework.

## Users

Truck dispatchers at a desk comparing routes before sending a truck out, and drivers on a phone or tablet before a trip. Both matter equally, so neither desktop nor mobile is an afterthought.

The product is also an engineering assessment. Its reviewers evaluate routes, weather, risk and recommendation logic (40%), UI, map and heatmap smoothness and performance (40%), code quality (15%), and documentation and walkthrough (5%).

## Product Purpose

Helps a truck driver choose the safest route for a specific trip, based on weather, load weight and travel time. The user enters origin, destination, departure date and time, and load weight. The app generates up to three routes, reads the weather at each checkpoint for the time the truck will be there, scores the risk, recommends the best route, and shows a weather heatmap along the trip corridor with a 0–48 hour forecast slider.

Success means the user can see within seconds which route to take and why, and can trust the answer.

## Positioning

Clearhaul reads the forecast for the hour the truck will actually reach each checkpoint, applies load-specific wind rules, and ranks routes by the miles exposed to each risk level. It answers "which route should this truck take at this time", not "what is the weather".

## Operating Context

Routes come from TomTom truck routing and weather from Open-Meteo. A cold trip plan takes about 3 to 12 seconds, mostly waiting on those services, so waiting is a normal part of the flow. The heatmap loads separately after the routes. Open-Meteo's free limits can be reached by several long trips in a minute, and the app then tells the user to try again in a minute.

## Capabilities and Constraints

- Checkpoint interval of 10, 25 or 50 miles, default 25.
- Risk levels, worst to best: No Travel, Severe, High, Moderate, Low.
- Ranking: fewest No Travel miles, fewest Severe miles, fewest High miles, lowest average risk, shortest travel time. If every route has No Travel miles, no route is recommended.
- Some trips have fewer than three distinct routes. The app shows what exists and says so.
- If no route respects the road closures planned for the departure, routes are shown without them, with a warning to check closures near both ends.
- Departure is entered in the origin's local time, and ETAs are shown in each checkpoint's local time.
- Forecasts cover 14 days from today. Heatmap hours beyond the forecast are left blank and never shown as Low.
- Address search covers every country, and places outside the US show their country. Units are miles, pounds, mph and inches per hour.
- A trip uses at most 450 weather checks across its routes. When the chosen interval needs more, the form names the interval that fits.
- Moving the forecast slider must take under 16 ms per step, with no network request.
- The brief says to prioritize correctness and clarity over extra features.

## Brand Commitments

- Name: Clearhaul, with "Weather-aware truck routing" as its description.
- The design language must be professional.
- It must not look like a generic AI dashboard, and it must not be too dense to read.

## Evidence on Hand

Live data from the running backend. There are no customers, testimonials, benchmarks or partner logos, and none may be invented.

## Product Principles

1. The answer comes first: which route, and why, before any supporting detail.
2. Risk is never softened. Missing weather is never presented as safe, and when no route is safe the app says so.
3. Every number can be traced to a checkpoint, a time and a rule.
4. Smoothness is a feature: the map and slider never stall.
5. Show what the brief asks for, and do that fully, before adding anything else.

## Accessibility & Inclusion

Risk levels must never rely on color alone, because they are safety information. All controls work by keyboard and touch, and motion respects the reduced-motion setting.
