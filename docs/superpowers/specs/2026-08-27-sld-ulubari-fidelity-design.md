# SLD Generator — Ulubari Structural Fidelity

**Date:** 2026-08-27
**Status:** Approved for planning
**Reference:** `~/Downloads/SLD Ulubari DSS.pdf` (33/11 kV Ulubari Electrical Sub-Station)

## Goal

Replace the two current SLD renderers (`_render_single_bus`, `_render_double_bus`) with
**one unified renderer** able to reproduce the Ulubari reference diagram:

- Sectionalized 33 kV bus with an optional **33 kV bus coupler**.
- **33 kV outgoing feeder bays** (full CT / VCB / isolator / LA bays off the 33 kV bus).
- **N power transformers**, each feeding its **own 11 kV bus section** (N sections),
  each with an 11 kV incomer VCB and its own 11 kV bus PT.
- **11 kV bus couplers** between consecutive sections, driven by data — a section with
  no coupler record stays electrically isolated (the Ulubari TR-3 case).
- A **100 kVA 33/0.4 kV station transformer** bay off the 33 kV bus.
- Per-equipment nameplate ratings (data where available, standard constants otherwise).
- Reference-style title block + a symbol **legend** rendered inside the SVG.
- The SVG snapshot embedded as page 1 of the PDF report.

A 1-transformer substation is the degenerate case of the unified renderer: one 33 kV
incomer bay, one transformer, one full-width 11 kV section, no couplers.

## Non-goals

- No new import columns for ratings (breaking capacity, isolator/LA current ratings are
  rendered as fixed constants).
- No explicit `bus_groups` config — 11 kV sectioning is inferred from `transformer_id`
  links and `bus_coupler` records only.
- No change to the PDF's existing cover/tables beyond prepending the snapshot page.
- No physical-position fidelity: bay order along the 33 kV bus is deterministic by
  category + sequence, not the literal geographic bay order of any given site.

---

## 1. Data model & import

### 1.1 Feeder type vocabulary (`models.py`)

Retire `lilo_33kv`. Add `outgoing_33kv` and `station_transformer`.

| `feeder_type`        | Meaning                          | Rendered as |
|----------------------|----------------------------------|-------------|
| `incoming_33kv`      | 33 kV source incomer             | Full bay above 33 kV bus |
| `outgoing_33kv`      | 33 kV outgoing feeder (was LILO) | Full bay above 33 kV bus |
| `transformer_hv`     | Transformer HV connection        | Transformer bay below 33 kV bus |
| `station_transformer`| 33/0.4 kV auxiliary supply       | Short station-TR bay below 33 kV bus |
| `incomer_11kv`       | 11 kV incomer (transformer LV)   | Per-section incomer bay |
| `outgoing_11kv`      | 11 kV outgoing feeder            | Per-section feeder bay |
| `bus_coupler`        | Bus coupler (33 or 11 kV)        | Coupler between two bus segments/sections |

- `feeder_doc()` default `feeder_type` stays `"outgoing_11kv"`; update the module comment
  listing valid types.
- No schema change to the stored feeder document shape.

### 1.2 `importer._resolve_feeder_type(name, raw_type, voltage)`

Current order: coupler-name override → mapped column value → name/voltage heuristic →
33 kV-outgoing reclassification.

New order (two additions, both name-based overrides that run **before** the column map,
matching the existing `"coupler"` override pattern):

1. `name` contains `coupler` → `bus_coupler`  *(unchanged)*
2. **NEW:** `name` contains `station` / `auxiliary` / `aux` → `station_transformer`
3. mapped `raw_type` via `FEEDER_TYPE_MAP`, else `_classify_feeder(name, voltage)`
4. **CHANGED:** if result is `outgoing_11kv` and voltage mentions `33` → `outgoing_33kv`
   (was `lilo_33kv`)

`_classify_feeder` already returns `station_transformer` for station/aux names, so the
heuristic path is consistent; the new step 2 just makes it win when the `Feeder Type`
column says something else (source data mislabels these rows).

### 1.3 Bus-coupler voltage

No change needed. `feeder_doc.voltage_kv` is already set from the `Feeder Voltage`
column (`re.search(r"(\d+)", ...)`, default `11`). Downstream:

- `bus_coupler` with `voltage_kv == 33` → 33 kV bus coupler.
- `bus_coupler` with `voltage_kv == 11` (default) → 11 kV bus coupler.

### 1.4 `models.infer_topology(feeders)`

Reworked return dict (keys consumed by the frontend topology panel and the PDF
topology summary):

```python
{
  "bus_config":            "single_bus" | "sectionalized_11kv"
                           | "sectionalized_33kv" | "sectionalized_both",
  "num_transformers":       int,
  "num_11kv_sections":      int,   # == num_transformers (min 1)
  "has_11kv_bus_coupler":   bool,
  "has_33kv_bus_coupler":   bool,
  "has_station_transformer":bool,
  "incoming_33kv_count":    int,
  "outgoing_33kv_count":    int,
  "outgoing_11kv_count":    int,
}
```

`bus_config` derivation:

| 33 kV coupler | 11 kV coupler | `bus_config` |
|:---:|:---:|---|
| no  | no  | `single_bus` |
| no  | yes | `sectionalized_11kv` |
| yes | no  | `sectionalized_33kv` |
| yes | yes | `sectionalized_both` |

Removed keys: `lilo_33kv_count`. `has_bus_coupler` is replaced by the two
voltage-specific flags — grep for consumers (PDF `pdf_generator.py:136`, frontend
`sld/index.html`) and update them (section 5).

---

## 2. Layout engine (`sld_generator.py`, full rewrite)

`SLDGenerator.generate(substation_id)` → single path:

```
ss, feeders, transformers = load()
scene = self._layout(ss, feeders, transformers)   # pure, no SVG, no Mongo
return self._render(scene)                          # Scene -> SVG string
```

### 2.1 Scene structure (the `_layout` output)

Plain dataclasses / dicts — chosen for direct unit assertions:

```
Scene:
  width: int
  height: int
  title: TitleBlock(name, last_update_str, source_str)
  bus33: Bus(y, segments=[(x0, x1), ...], coupler_x: int | None)
  bays33: list[Bay]        # ordered left -> right, drawn ABOVE bus33
  sections11: list[Section] # one per transformer, left -> right, drawn BELOW transformers
  couplers11: list[Coupler]
  legend: LegendBox(x, y, w, h, entries=[LegendEntry(glyph_kind, name, description), ...])

Bay:
  kind: "incomer_33kv" | "outgoing_33kv" | "transformer" | "station_transformer" | "bus_pt_33"
  x: int
  label: str                       # feeder / transformer name (top of bay)
  segment: int                     # 0 or 1 — which 33 kV bus segment it hangs off
  equipment: list[Equip]           # top -> bottom: LA, isolator, VCB|AR, CT, ocef marker...
  ref: dict | None                 # source feeder/transformer doc (for ratings, AR flag)

Section:
  tr_index: int
  bus: (x0, x1, y)
  incomer_bay: Bay-like            # 11 kV I/C VCB + CT rising to the transformer
  bus_pt_x: int
  feeder_bays: list[Bay]           # kind "outgoing_11kv", drawn BELOW the section bus

Coupler:
  orientation: "h33" | "v11"
  # h33: between bus33 segments, at x == bus33.coupler_x
  # v11: between sections[i] and sections[i+1], vertical stack Iso(ES)->VCB->Iso(ES)
  between: (int, int)
  x: int
```

### 2.2 Horizontal layout rules

- **Bay pitch**: `BAY_W = 130`. Feeder-bay pitch inside an 11 kV section: `FEEDER_W = 110`.
- **33 kV bay order**: `incoming_33kv` (by `sequence`) → `transformer_hv` bays (by tr
  `sequence`) → `outgoing_33kv` (by `sequence`) → `station_transformer` → a synthetic
  `bus_pt_33` bay pinned at the far right.
- **11 kV section order**: transformers by `sequence`. Section width =
  `max(1, len(feeder_bays)) * FEEDER_W` (plus padding for the incomer + bus PT).
- **Diagram width** = `max(MIN_W, n_bays33 * BAY_W + 2*MARGIN, Σ section widths + 2*MARGIN)`.
  Sections and 33 kV bays are then centre-distributed across that width.
- **33 kV bus coupler**: if any `bus_coupler` feeder has `voltage_kv == 33`, `bus33` has
  two segments split at the horizontal centre with `coupler_x` at that split; bays are
  assigned `segment = 0` for the first `ceil(n/2)` bays (in the order above) and
  `segment = 1` for the rest, and each segment's `(x0, x1)` spans its bays. Otherwise a
  single segment `(MARGIN, width - MARGIN)`, `coupler_x = None`.
- **11 kV bus couplers**: `k`-th 11 kV `bus_coupler` feeder → `Coupler(between=(k, k+1))`
  placed at the mid-gap x between `sections[k]` and `sections[k+1]`. If there are fewer
  coupler records than section gaps, the trailing gaps get none (sections isolated).

### 2.3 Vertical layout (fixed Y bands)

| Band | Purpose |
|---|---|
| `Y.title` | title block (in dark bar) |
| `Y.bay33_top … Y.bay33_bot` | 33 kV bay equipment stack (LA, iso, VCB, CT, OC/EF) |
| `Y.bus33` | 33 kV busbar line |
| `Y.tr_top … Y.tr_bot` | transformer HV isolator → transformer symbol → LV lead |
| `Y.bus11` | 11 kV section busbars (all sections share this Y) |
| `Y.feed_top … Y.feed_bot` | 11 kV feeder bay stack + rotated feeder-name labels |
| `Y.legend` | legend box |

`height = Y.legend + legend.h + MARGIN`.

Station-transformer bays occupy `Y.tr_top … Y.bus33 + short` only (never reach `Y.bus11`).

### 2.4 `_render(scene)` — emits SVG

Walks the Scene and concatenates `sym_*` output. No layout math here. Order:
`_svg_header` → 33 kV bus segments + coupler → 33 kV bays → transformer bays →
11 kV section buses + bus PTs → 11 kV couplers → 11 kV feeder bays → legend → `</svg>`.

---

## 3. Symbols (`sym_*` helpers)

Stateless module-level functions, reviewed individually against the reference.

### 3.1 New / changed helpers

- **`sym_station_transformer(x, y, label)`** — single winding circle + `33/0.4 kV`
  caption + earth symbol. Smaller than `sym_transformer`.
- **`sym_ocef_marker(x, y)`** — small boxed `OC/EF TVM` tag placed beside VCB/CT in a bay
  when the feeder's `switchgear.oc_ef_relay_type` is set (or always, for 33 kV bays, to
  match the reference — decide during implementation; default: show when relay data present).
- **`sym_isolator`** — already supports `has_earth`; reference "w/out Earth Switch"
  line isolators pass `has_earth=False`, transformer/feeder isolators pass `has_earth=True`.
- **`sym_bus_coupler_horizontal(x, y_bus, ...)`** — for the 33 kV coupler (Iso–VCB–Iso
  across a short horizontal break). Keep `sym_bus_coupler_vertical` for 11 kV.
- **`sym_feeder_out`** — unchanged shape; used for both 33 kV (red) and 11 kV (blue) arrows.

### 3.2 Ratings — "data where available, constants for the rest"

Module-top dict, single edit point:

```python
RATINGS = {
    "vcb_33":  "1250A, 25kA",
    "vcb_11":  "1250A, 25kA",
    "iso_33":  "630A, 25kA",
    "iso_11":  "630A, 25kA",
    "la":      "30kV, 10kA",
    "ct":      "400/5A",
}
```

Label composition per bay:

| Symbol | Label text |
|---|---|
| VCB | `f"{feeder.switchgear.vcb_make or 'VCB'}\n{RATINGS['vcb_33'|'vcb_11']}"` |
| Isolator | `RATINGS["iso_33" | "iso_11"]` |
| CT | `feeder.meter.ctr or RATINGS["ct"]` |
| LA | `RATINGS["la"]` |
| Transformer | `f"{capacity_mva} MVA 33/11kV Pr. Transformer - {sequence}"` |
| Station TR | `f"{capacity} kVA 33/0.4kV Station Tr"` |

Auto-recloser detection: unchanged `is_autorecloser(feeder)`; an AR bay draws
`sym_autorecloser` instead of `sym_vcb`.

### 3.3 Title block (`_svg_header`)

Keep the dark bar. Three centred lines:

```
SLD - 33/11kV {NAME} ELECTRICAL SUB-STATION
DATE OF LAST UPDATE: {ss.updated_at:%d.%m.%Y}
SOURCE: {gss_primary} · {bus_config as spaced title case}      (small, grey)
```

### 3.4 Legend box

Bordered panel below the diagram, inside the viewBox so it survives PNG/PDF export.
~3 columns; each entry = a small glyph (reuse the `sym_*` helper at reduced scale) +
bold name + one-line description:

| Glyph | Name | Description |
|---|---|---|
| LA | Lightning / Surge Arrester | Diverts surge energy to earth |
| Isolator | Disconnector (Isolator) | Off-load isolation; hatched = with earth switch |
| VCB | Vacuum Circuit Breaker | On-load make/break |
| AR | Auto-Recloser | Self-reclosing breaker on outgoing feeders |
| CT | Current Transformer | Metering & protection current sensing |
| PT | Voltage (Potential) Transformer | Bus voltage sensing / metering |
| Transformer | Power Transformer | 33/11 kV; HV winding red, LV blue |
| Station TR | Station Transformer | 33/0.4 kV auxiliary supply |
| Coupler | Bus Coupler | Links two bus sections |
| Bus | Busbar | 33 kV red · 11 kV blue |
| Earth | Earth | Earthing connection |
| OC/EF | OC/EF TVM | Over-current / earth-fault protection relay |

### 3.5 Removed

`_equipment_table` and its call — deleted (the PDF keeps its own tables).

---

## 4. PDF snapshot page (`pdf_generator.py`)

- `generate(substation_id, svg_string)` already receives the SVG. Stop ignoring it.
- Prepend a **page 1 snapshot**: `svglib.svg2rlg` on the SVG string → a `Drawing`,
  uniformly scaled to fit the A3-landscape content box, wrapped in a `KeepTogether`,
  followed by `PageBreak`; existing cover/tables follow unchanged.
- Update the module docstring ("no svglib" is now false).
- The topology-summary table (`pdf_generator.py:~131-138`) reads `topo["bus_config"]`,
  `topo["has_station_transformer"]`, `topo["outgoing_11kv_count"]` — still present; also
  swap the removed `has_bus_coupler` for the two new flags and add
  `num_11kv_sections`.
- **Fallback:** if `svg2rlg` raises or returns `None`, log a warning and skip the
  snapshot page — the rest of the report still renders.

---

## 5. Frontend & tests

### 5.1 `templates/sld/index.html`

- `typeLabel` map: replace `lilo_33kv` entry with `outgoing_33kv`
  (`<span class="badge badge-33">33kV OUT</span>`); keep `station_transformer`.
- Edit-feeder `<select>`: `lilo_33kv` option → `outgoing_33kv` ("33kV Outgoing");
  keep `station_transformer`.
- Topology panel: `lilo_33kv_count` → `outgoing_33kv_count` (label "33 kV O/g Feeders");
  add rows "11 kV Sections" (`num_11kv_sections`) and "33 kV Bus Coupler"
  (`has_33kv_bus_coupler`); relabel existing coupler row "11 kV Bus Coupler".
- The static HTML legend strip above the canvas can stay as a quick colour key
  (33 kV / 11 kV / Earth); the detailed legend now lives in the SVG.

### 5.2 Tests

`test_sld_generator.py` — **rewritten** around `_layout()` using the existing
`FakeDB`/`FakeCollection`/`FakeCursor` helpers. Scenarios:

1. **1-TR simple** — 1 `incoming_33kv`, 1 transformer, 3 `outgoing_11kv`.
   Assert: `len(scene.sections11) == 1`, `scene.bus33.coupler_x is None`,
   `scene.couplers11 == []`, one `bus_pt_33` bay, feeder names in rendered SVG.
2. **2-TR + 11 kV coupler** — 2 transformers, one 11 kV `bus_coupler`.
   Assert: 2 sections, `len(scene.couplers11) == 1` with `between == (0, 1)`,
   `bus_config == "sectionalized_11kv"`.
3. **Ulubari shape** — 3 transformers; 2 `incoming_33kv`; 3 `outgoing_33kv`;
   1 `station_transformer`; one 33 kV `bus_coupler`; one 11 kV `bus_coupler`.
   Assert: `len(scene.bays33)` counts (2 incomers + 3 tr + 3 outgoing + 1 station
   + 1 bus_pt), `scene.bus33.coupler_x is not None`, 2 segments,
   `len(scene.sections11) == 3`, `len(scene.couplers11) == 1` (sections 0-1 coupled,
   section 2 isolated), station-TR bay present and never reaches `Y.bus11`,
   `bus_config == "sectionalized_both"`.
4. **Render smoke** — for scenario 3, `svg = SLDGenerator(db).generate(id)`;
   assert every feeder name appears, `"DATE OF LAST UPDATE"` present,
   legend markers (`"Lightning"`, `"Bus Coupler"`, `"OC/EF"`) present,
   `"<svg"` well-formed, no `lilo` string anywhere.

`test_models.py` — `infer_topology` test updated to the new key set
(`outgoing_33kv_count`, `num_11kv_sections`, `has_11kv_bus_coupler`,
`has_33kv_bus_coupler`, `bus_config` value).

`test_importer.py`:
- `test_resolve_feeder_type_reclassifies_33kv_outgoing_feeder_as_lilo` →
  rename, assert `"outgoing_33kv"`.
- New `test_resolve_feeder_type_detects_station_transformer_by_name`
  (`_resolve_feeder_type("33kV Station Tr", "Outgoing Feeder", "33kV") == "station_transformer"`).
- Integration counts (`SAMPLE_FILE`, skipped when absent):
  `test_import_splits_33kv_outgoing_feeders_into_lilo` → renamed, `feeder_type == "outgoing_33kv"`.

### 5.3 `template_generator.py`

- Note #12 wording: bus-coupler rows — mention that a `Feeder Voltage` of `33kV` makes
  it a 33 kV coupler.
- Add a note: a 33 kV "Outgoing Feeder" row renders as a full 33 kV bay; a feeder whose
  name contains "Station"/"Auxiliary" is auto-classified as the station transformer.

---

## 6. File-change summary

| File | Change |
|---|---|
| `app/models.py` | feeder-type comment; `infer_topology` rewrite |
| `app/services/importer.py` | `_resolve_feeder_type` — station override, `outgoing_33kv` |
| `app/services/sld_generator.py` | **full rewrite** — `_layout` + `_render` + new `sym_*` |
| `app/services/pdf_generator.py` | prepend SVG snapshot page; topology-table keys |
| `app/services/template_generator.py` | note text |
| `app/templates/sld/index.html` | `typeLabel`, `<select>`, topology panel keys |
| `tests/test_sld_generator.py` | full rewrite |
| `tests/test_models.py` | new `infer_topology` keys |
| `tests/test_importer.py` | `outgoing_33kv`, station-TR test |

## 7. Risks

- **Auto-layout vs. real bay order** — the generated 33 kV bay order is by category, not
  the site's physical order; accepted per non-goals. If a site needs exact order, a
  future `sequence`-only sort or an explicit position column can be added.
- **`svg2rlg` fidelity** — svglib doesn't render every SVG feature (some text/tspan
  positioning, `letter-spacing`). The snapshot page is a best-effort raster of the
  diagram; the graceful-skip fallback covers hard failures. Verify against a real
  substation during implementation.
- **Existing SLD appearance changes for every substation** — expected (unified renderer).
  No stored data migration needed; `infer_topology` re-runs on next import or feeder edit,
  and `generate()` recomputes from feeders each call, so stale `topology` docs only affect
  the frontend panel until the next `refresh_substation_topology()`.
