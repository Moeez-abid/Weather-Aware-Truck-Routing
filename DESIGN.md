---
name: Clearhaul
description: Weather-aware truck routing, set as a printed plate.
colors:
  ground: "#f5f4f6"
  ground-warm: "#faf6f5"
  ground-cool: "#eef3ef"
  field: "#fbfbfc"
  ink: "#16181a"
  ink-hover: "#33363a"
  ink-muted: "#5a5d62"
  hairline: "#c9c7c4"
  seal: "#dcddf3"
  alert: "#a8201a"
  route-other: "#8b8e93"
  risk-low: "#2f8f66"
  risk-moderate: "#e0ab00"
  risk-high: "#e36f12"
  risk-severe: "#c4232b"
  risk-no-travel: "#3b1150"
typography:
  display:
    fontFamily: "Host Grotesk Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "3.25rem"
    fontWeight: 400
    lineHeight: 1.02
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Host Grotesk Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "Host Grotesk Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "tnum"
  small:
    fontFamily: "Host Grotesk Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Geist Mono Variable, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.1em"
rounded:
  none: "0px"
spacing:
  stack: "20px"
  section: "24px"
  gutter: "24px"
  gutter-wide: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    height: "48px"
    padding: "0 24px"
  button-primary-hover:
    backgroundColor: "{colors.ink-hover}"
    textColor: "{colors.ground}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.small}"
    rounded: "{rounded.none}"
    height: "36px"
    padding: "0 12px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    height: "48px"
    padding: "0 12px"
  segment-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    height: "48px"
  row-selected:
    backgroundColor: "{colors.seal}"
    textColor: "{colors.ink}"
  tag-recommended:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "2px 6px"
---

# Design System: Clearhaul

## Overview

**Creative North Star: "The Registered Plate"**

Clearhaul is set like a plate section in a printed design annual. The page is near-white uncoated stock, ink is near-black, and structure comes from one-pixel hairlines rather than boxes and shadows. The map is the plate: framed by a hairline, held by registration marks at its corners, and stamped with a periwinkle seal when a route is recommended. Everything a driver or dispatcher needs to decide sits in a single ruled column beside it.

The system is deliberately quiet so that risk can be loud. The base map is a near-monochrome grey, the interface is ink and paper, and the only strong colors on screen are the five risk levels. Density stays moderate: the verdict is the largest type on the page, supporting numbers sit in plain rows, and nothing competes with the answer.

The owner chose this world for a professional tool that must not look like a generic AI dashboard and must not be too dense to read.

**Key Characteristics:**
- Near-white ground that drifts warm at the top left and cool at the bottom right, so it reads as paper rather than a flat fill.
- One grotesque typeface for everything, with a monospace face only for labels and measures.
- Square corners, one-pixel hairlines, and no decorative shadows.
- Risk is the only strong color, and every risk level also has its own shape.
- One authored motion: results settle into place once when a plan arrives.

## Colors

A restrained ink-and-paper palette with one periwinkle accent, and a five-step risk scale that owns all strong color.

### Primary
- **Plate Ink** (`ink`): text, the primary button, the selected route line, selected segments and the recommended tag. Hover deepens to **Pressed Ink** (`ink-hover`).

### Secondary
- **Seal Periwinkle** (`seal`): the recommendation stamp, the selected route row, and highlighted search results. It marks the current choice and nothing else.

### Neutral
- **Uncoated Stock** (`ground`): the page, the panel, map placeholders and popups.
- **Warm Drift** (`ground-warm`) and **Cool Drift** (`ground-cool`): the soft radial drift at opposite corners of the page.
- **Field White** (`field`): the inside of text inputs, a step lighter than the page.
- **Hairline Grey** (`hairline`): every rule, border, divider, tick and the dot pattern.
- **Muted Ink** (`ink-muted`): secondary text, labels, hints and placeholders, at about 6:1 contrast on the ground.
- **Alternate Route Grey** (`route-other`): routes that are not selected.
- **Alert Red** (`alert`): validation and failure messages, with the field border to match.

### Risk scale
- **Low** (`risk-low`), **Moderate** (`risk-moderate`), **High** (`risk-high`), **Severe** (`risk-severe`) and **No Travel** (`risk-no-travel`). Used for checkpoint markers, the risk bar, legends and the heatmap. In the heatmap their opacity rises with severity (Low 0.12, Moderate 0.5, High 0.62, Severe 0.72, No Travel 0.82), so a calm corridor stays a faint wash.

### Named Rules
**The Risk Owns Color Rule.** Strong color means risk. Interface chrome stays ink, hairline and paper; the periwinkle seal is the only other accent, and it only marks the current choice.

**The Shape Before Color Rule.** Every risk level is drawn with its own road-sign shape: circle for Low, yield triangle for Moderate, square for High, warning diamond for Severe, and a stop octagon with a white bar for No Travel. Color is never the only signal.

**The Blank Is Not Low Rule.** Where the forecast has no data, the map is left transparent and the legend says so. Missing weather is never painted with the Low color.

## Typography

**Display, Body and Title Font:** Host Grotesk Variable (with the system sans as fallback)
**Label Font:** Geist Mono Variable (with the system monospace as fallback)

**Character:** One neutral grotesque carries the whole interface at large and small sizes, with hierarchy made by scale rather than by switching faces. The monospace face appears only in small uppercase labels, where it reads as printed measurement.

### Hierarchy
- **Display** (400, 3.25rem on wide screens and 2.5rem on phones, line height 1.02, tracking -0.025em): the page's one heading, either the question before a trip or the verdict after it, such as "Take Route A".
- **Title** (500, 1.25rem): route names in the comparison list and the wordmark.
- **Body** (400, 1.0625rem, line height 1.55): explanations, inputs and the reason for the recommendation. Numbers use tabular figures throughout.
- **Small** (400, 0.875rem): supporting facts, weather readings, legends and messages.
- **Label** (Geist Mono, 400, 0.75rem, tracking 0.1em, uppercase): field labels, section headings, the service status and the slider's hour label.

### Named Rules
**The Mono For Measures Rule.** Monospace is only for labels, statuses and measured values. Sentences, headings and buttons with long text are never set in it.

**The One Heading Rule.** A view has one display-size heading, and it states the answer or the question. Everything else steps down to title or body.

## Layout

On wide screens the page is a fixed-height workspace: a 56px top bar with a hairline below, then a ruled column of 24rem to 30rem on the left and the map plate filling the rest. The column scrolls on its own and the map never moves. Gutters are 32px on wide screens and 24px on phones, fields are 20px apart, and sections are 24px apart.

On phones the map plate comes first. Before a trip it takes about 38% of the screen height; once there are routes it grows to about 66%, with the forecast slider below it, and the column scrolls underneath. Nothing scrolls sideways at 375px.

The forecast slider and legend sit under the map plate, outside its frame. The left column's empty space below the form is filled with the dot pattern rather than left blank.

## Elevation & Depth

The system is flat. Depth comes from hairline frames and tonal steps (field white on stock, periwinkle for selection), not shadows. The one exception is the checkpoint popup, which floats over the map and uses a soft ambient shadow (`0 6px 18px rgb(22 24 26 / 0.14)`) so it separates from map detail.

### Named Rules
**The Hairline Rule.** Group things with one-pixel rules and a single shared border. Never stack cards, and never add a shadow to something that does not float over the map.

## Shapes

Corners are square everywhere: buttons, inputs, segments, rows, tags, map controls and popups have no radius. Circles appear only where they carry meaning: the Low risk glyph, the trip's start and end markers, and the recommendation seal. Registration marks are thin crosshairs, 16px across, centered on each corner of the map plate.

## Components

### Buttons
- **Shape:** square (0px).
- **Primary:** filled Plate Ink with Uncoated Stock text in the uppercase monospace label style, 48px tall and full width in the form.
- **Hover / Focus:** hover deepens to Pressed Ink; focus shows a 2px ink outline offset by 2px. While a plan is loading the label reads "Comparing routes…" and the button is disabled.
- **Secondary:** transparent with a hairline border and small body text, 36px tall, such as "Edit trip". The border darkens to ink on hover.

### Inputs / Fields
- **Style:** Field White inside a one-pixel hairline border, square, 48px tall, with an uppercase monospace label above.
- **Focus:** the border turns to ink and the 2px focus outline sits on the border.
- **Error:** the border turns Alert Red and the message sits directly below in Alert Red. Focus moves to the first field with a problem.
- **Address search:** suggestions open in an ink-bordered list attached to the field, with Seal Periwinkle on the highlighted row and messages for searching, no matches and failure.

### Segmented choice
Three equal segments inside one hairline border, divided by hairlines. The selected segment is filled Plate Ink with Stock text; others take a periwinkle tint on hover.

### Route rows
One hairline box holds every route, separated by rules. Each row is a pressable button showing the route name, a Recommended tag, drive time, miles and arrival, a proportional risk bar, and per-level miles with their glyphs. The selected row is filled Seal Periwinkle.

### Map plate
The map sits inside a hairline frame with registration marks at its corners. Routes are drawn as ink for the selected route and Alternate Route Grey for the rest, with a white casing under the selected line. Route letters are square ink-bordered markers that fill with ink when selected. Checkpoints are the risk glyphs, drawn larger on the selected route and with the worst risk drawn on top.

### Recommendation seal
A periwinkle disc, 96px across, set half off the plate's top-left corner on wide screens. The words "Recommended" run around the ring in the label face and the route letter sits in the center. It is still: it never spins.

### Forecast slider
A one-pixel ink track with a square ink thumb (12px by 28px), above a ruler with ticks every 6 hours and labels every 12. The current hour and its local time sit beside it in the label and body styles, and the legend sits below.

## Do's and Don'ts

### Do:
- **Do** keep the verdict as the largest type on screen, in the display style.
- **Do** pair every risk color with its shape, in the map, lists and legends.
- **Do** frame the map as a plate with hairlines and registration marks.
- **Do** use Seal Periwinkle only for the current choice and the recommendation stamp.
- **Do** keep motion to state changes: results settle in once (220ms, from 40% opacity and 8px down), and a thin bar sweeps while a plan loads. Both stop under the reduced-motion setting.

### Don't:
- **Don't** add color to the interface beyond ink, hairline, paper, the seal and the risk scale.
- **Don't** round corners on controls or containers.
- **Don't** use shadows except on content that floats over the map.
- **Don't** use monospace for headings or sentences.
- **Don't** add labels above headings, numbered section markers or icon-and-heading card grids.
- **Don't** animate anything on the forecast slider's path. Each step only swaps a prepared image.
