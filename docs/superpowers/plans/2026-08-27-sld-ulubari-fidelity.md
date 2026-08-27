# SLD Ulubari Structural Fidelity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two hard-coded SLD renderers with one unified layout-engine renderer that reproduces the 33/11 kV Ulubari reference diagram (sectionalized 33 kV bus + 33 kV coupler, 33 kV outgoing bays, N-transformer / N-section 11 kV bus with data-driven couplers, station transformer, per-bay ratings, in-SVG legend), and embed that SVG as page 1 of the PDF report.

**Architecture:** `SLDGenerator.generate()` runs two pure phases — `_layout(ss, feeders, transformers)` builds a `Scene` of dataclasses (buses, bays, sections, couplers, legend) with all geometry resolved, then `_render(scene)` walks the Scene emitting SVG through stateless `sym_*` helpers. No layout math in `_render`; no SVG in `_layout`. `_layout` is unit-tested with the existing in-memory `FakeDB` (no MongoDB).

**Tech Stack:** Python 3.11, Flask, PyMongo (raw dicts, no ORM), `dataclasses`, ReportLab + svglib for the PDF, pytest with hand-rolled fakes.

**Spec:** `docs/superpowers/specs/2026-08-27-sld-ulubari-fidelity-design.md`

## Global Constraints

- Python 3.11; run tests with `.venv/bin/python -m pytest` (venv pytest is 8.3.3; a global 8.2.2 also exists — always use the venv one).
- No ORM. Documents are plain dicts built by factory functions in `app/models.py`.
- `feeder_type` vocabulary after this change: `incoming_33kv`, `outgoing_33kv`, `transformer_hv`, `station_transformer`, `incomer_11kv`, `outgoing_11kv`, `bus_coupler`. `lilo_33kv` is retired — it must not appear anywhere in `app/` after Task 8.
- Colour scheme is fixed: 33 kV `#CC2200`, 11 kV `#0055CC`, bus `#111111`, earth `#006600`.
- Rating constants live in one module-level `RATINGS` dict in `app/services/sld_generator.py` — no rating literals scattered through the code.
- `SLDGenerator(db).generate(substation_id: str) -> str` signature is unchanged (called from `app/routes/sld.py`).
- `PDFReportGenerator(db).generate(substation_id: str, svg_string: str = None) -> bytes` signature is unchanged (called from `app/routes/sld.py`).
- Commit after every task. Commit messages: `feat:` / `test:` / `refactor:` / `docs:` prefixes; end with the Co-Authored-By trailer used in this repo's history.

---

## File Structure

| File | Responsibility after this plan |
|---|---|
| `app/models.py` | Doc factories; `infer_topology` now emits the section/coupler-aware topology dict |
| `app/services/importer.py` | `_resolve_feeder_type` classifies `outgoing_33kv` and `station_transformer` |
| `app/services/sld_generator.py` | **Rewritten.** `RATINGS`, `sym_*` helpers, `Scene` dataclasses, `_layout`, `_render` |
| `app/services/pdf_generator.py` | Prepends an SVG-snapshot page; reads the new topology keys |
| `app/services/template_generator.py` | Import-note text mentions the new classification rules |
| `app/templates/sld/index.html` | Feeder-type labels, edit `<select>`, topology panel keys |
| `tests/test_models.py` | `infer_topology` new-key assertions |
| `tests/test_importer.py` | `outgoing_33kv` + station-transformer classification |
| `tests/test_sld_generator.py` | **Rewritten.** `_layout` Scene assertions + render smoke tests |
| `tests/test_pdf_generator.py` | **New.** snapshot-page happy path + graceful fallback |

---

## Task 1: `infer_topology` rewrite

**Files:**
- Modify: `app/models.py` (`infer_topology`, lines ~145-173; and the feeder-type comment at line 77)
- Test: `tests/test_models.py` (rewrite the one existing test)

**Interfaces:**
- Consumes: nothing.
- Produces: `infer_topology(feeders: list[dict]) -> dict` with keys exactly:
  `bus_config` (`"single_bus"|"sectionalized_11kv"|"sectionalized_33kv"|"sectionalized_both"`),
  `num_transformers: int`, `num_11kv_sections: int`, `has_11kv_bus_coupler: bool`,
  `has_33kv_bus_coupler: bool`, `has_station_transformer: bool`,
  `incoming_33kv_count: int`, `outgoing_33kv_count: int`, `outgoing_11kv_count: int`.
  A feeder is a 33 kV coupler when `feeder_type == "bus_coupler" and feeder.get("voltage_kv") == 33`; an 11 kV coupler otherwise (coupler with `voltage_kv` 11 or missing).

- [ ] **Step 1: Replace the test file body**

Replace the entire contents of `tests/test_models.py` with:

```python
from app.models import infer_topology


def _f(feeder_type, voltage_kv=11, name="Feeder"):
    return {"feeder_type": feeder_type, "voltage_kv": voltage_kv, "name": name}


def test_infer_topology_single_bus_no_couplers():
    topo = infer_topology([
        _f("incoming_33kv", 33), _f("transformer_hv", 33), _f("outgoing_11kv", 11),
    ])
    assert topo["bus_config"] == "single_bus"
    assert topo["num_transformers"] == 1
    assert topo["num_11kv_sections"] == 1
    assert topo["has_11kv_bus_coupler"] is False
    assert topo["has_33kv_bus_coupler"] is False


def test_infer_topology_counts_33kv_outgoing_feeders():
    topo = infer_topology([
        _f("outgoing_33kv", 33), _f("outgoing_33kv", 33), _f("outgoing_11kv", 11),
    ])
    assert topo["outgoing_33kv_count"] == 2
    assert topo["outgoing_11kv_count"] == 1


def test_infer_topology_sectionalized_11kv_when_11kv_coupler_present():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("transformer_hv", 33),
        _f("bus_coupler", 11, "11kV Bus Coupler"),
    ])
    assert topo["has_11kv_bus_coupler"] is True
    assert topo["has_33kv_bus_coupler"] is False
    assert topo["bus_config"] == "sectionalized_11kv"
    assert topo["num_11kv_sections"] == 2


def test_infer_topology_sectionalized_both_when_both_couplers_present():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("transformer_hv", 33),
        _f("bus_coupler", 33, "33kV Bus Coupler"),
        _f("bus_coupler", 11, "11kV Bus Coupler"),
    ])
    assert topo["bus_config"] == "sectionalized_both"
    assert topo["has_33kv_bus_coupler"] is True
    assert topo["has_11kv_bus_coupler"] is True


def test_infer_topology_coupler_without_voltage_key_counts_as_11kv():
    topo = infer_topology([
        _f("transformer_hv", 33),
        {"feeder_type": "bus_coupler", "name": "Bus Coupler"},  # no voltage_kv
    ])
    assert topo["has_11kv_bus_coupler"] is True
    assert topo["has_33kv_bus_coupler"] is False


def test_infer_topology_flags_station_transformer():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("station_transformer", 33, "Station Tr"),
    ])
    assert topo["has_station_transformer"] is True
    assert topo["num_transformers"] == 1  # station TR does not count as a power TR
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL — `KeyError` on the new keys / assertion errors.

- [ ] **Step 3: Rewrite `infer_topology`**

In `app/models.py`, replace the `infer_topology` function (keep the `# ── Topology inference ──` banner) with:

```python
def infer_topology(feeders: list) -> dict:
    """Derive bus configuration from the feeder list.

    A `bus_coupler` feeder with voltage_kv == 33 is a 33 kV coupler; any other
    `bus_coupler` (voltage_kv 11 or absent) is an 11 kV coupler.
    """
    def _is(ft):
        return [f for f in feeders if f.get("feeder_type") == ft]

    couplers      = _is("bus_coupler")
    has_33_bc     = any(f.get("voltage_kv") == 33 for f in couplers)
    has_11_bc     = any(f.get("voltage_kv") != 33 for f in couplers)
    num_tr        = len(_is("transformer_hv"))
    num_sections  = max(num_tr, 1)

    if has_33_bc and has_11_bc:
        bus_config = "sectionalized_both"
    elif has_33_bc:
        bus_config = "sectionalized_33kv"
    elif has_11_bc:
        bus_config = "sectionalized_11kv"
    else:
        bus_config = "single_bus"

    return {
        "bus_config": bus_config,
        "num_transformers": num_tr,
        "num_11kv_sections": num_sections,
        "has_11kv_bus_coupler": has_11_bc,
        "has_33kv_bus_coupler": has_33_bc,
        "has_station_transformer": bool(_is("station_transformer")),
        "incoming_33kv_count": len(_is("incoming_33kv")),
        "outgoing_33kv_count": len(_is("outgoing_33kv")),
        "outgoing_11kv_count": len(_is("outgoing_11kv")),
    }
```

- [ ] **Step 4: Update the feeder-type comment**

In `app/models.py`, change the comment above `feeder_doc` (line ~77) to:

```python
# feeder_type: "incoming_33kv" | "outgoing_33kv" | "transformer_hv" | "station_transformer"
#            | "incomer_11kv" | "outgoing_11kv" | "bus_coupler"
```

- [ ] **Step 5: Update the substation-doc topology stub**

In `app/models.py`, `substation_doc()` seeds a `"topology"` dict (lines ~43-51) with the old keys. Replace that block with:

```python
        "topology": {
            "bus_config": "single_bus",          # updated by infer_topology()
            "num_transformers": 0,
            "num_11kv_sections": 0,
            "has_11kv_bus_coupler": False,
            "has_33kv_bus_coupler": False,
            "has_station_transformer": False,
            "incoming_33kv_count": 0,
            "outgoing_33kv_count": 0,
            "outgoing_11kv_count": 0,
        },
```

- [ ] **Step 6: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: section/coupler-aware infer_topology; retire lilo_33kv key

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Importer feeder classification

**Files:**
- Modify: `app/services/importer.py` (`_resolve_feeder_type`, lines ~119-133; `FEEDER_TYPE_MAP` docstring context)
- Modify: `app/services/template_generator.py` (note list, line ~129)
- Test: `tests/test_importer.py` (two existing `_resolve_feeder_type` tests + one new)

**Interfaces:**
- Consumes: nothing.
- Produces: `_resolve_feeder_type(name, raw_type, voltage) -> str | None`. New behaviour:
  a name containing `station` / `auxiliary` / `aux` → `"station_transformer"` (wins over
  the `Feeder Type` column); an `"Outgoing Feeder"` at 33 kV → `"outgoing_33kv"` (was
  `"lilo_33kv"`).

- [ ] **Step 1: Update the existing importer tests**

In `tests/test_importer.py`, replace `test_resolve_feeder_type_reclassifies_33kv_outgoing_feeder_as_lilo` with:

```python
def test_resolve_feeder_type_reclassifies_33kv_outgoing_feeder_as_outgoing_33kv():
    # "Outgoing Feeder" at 33kV is a full 33kV bay off the 33kV bus, not an 11kV feeder
    assert _resolve_feeder_type("Chandmari", "Outgoing Feeder", "33kV") == "outgoing_33kv"
```

Add immediately below it:

```python
def test_resolve_feeder_type_detects_station_transformer_by_name():
    # Source data often labels the station TR row as a plain outgoing feeder
    assert _resolve_feeder_type("33kV Station Tr", "Outgoing Feeder", "33kV") == "station_transformer"
    assert _resolve_feeder_type("Auxiliary Transformer", None, "33kV") == "station_transformer"


def test_resolve_feeder_type_station_name_does_not_shadow_bus_coupler():
    # "coupler" override still runs first
    assert _resolve_feeder_type("Station Bus Coupler", "Outgoing Feeder", "11kV") == "bus_coupler"
```

- [ ] **Step 2: Update the integration-count test**

In `tests/test_importer.py`, rename `test_import_splits_33kv_outgoing_feeders_into_lilo` to
`test_import_splits_33kv_outgoing_feeders_into_outgoing_33kv` and change its body to filter on
`f["feeder_type"] == "outgoing_33kv"` (keep the existing count numbers and the
`all(f["voltage_kv"] == 33 ...)` assertion; the local variable `lilo` → `og33`). This test is
skipped unless the sample xlsx exists, so the counts are not verified here — leave them as-is.

- [ ] **Step 3: Run the tests, verify they fail**

Run: `.venv/bin/python -m pytest tests/test_importer.py -k resolve_feeder_type -v`
Expected: FAIL — `outgoing_33kv` / `station_transformer` not returned.

- [ ] **Step 4: Update `_resolve_feeder_type`**

In `app/services/importer.py`, replace `_resolve_feeder_type` with:

```python
_STATION_KEYWORDS = ("station", "auxiliary", " aux", "aux ")


def _resolve_feeder_type(name, raw_type, voltage):
    """Name-based overrides win over the (often mislabelled) Feeder Type column:
    a "coupler" name is always a bus coupler; a "station"/"auxiliary" name is
    always the station transformer. Otherwise use the mapped Feeder Type column,
    else the name/voltage heuristic. An "Outgoing Feeder" at 33 kV is a full
    33 kV bay, not an 11 kV consumer feeder."""
    lname = (name or "").lower()
    if name and "coupler" in lname:
        return "bus_coupler"
    if name and (lname.startswith("aux") or any(k in lname for k in _STATION_KEYWORDS)):
        return "station_transformer"
    if raw_type:
        mapped = FEEDER_TYPE_MAP.get(str(raw_type).strip().lower())
        ftype = mapped if mapped else _classify_feeder(name, voltage)
    else:
        ftype = _classify_feeder(name, voltage)
    if ftype == "outgoing_11kv" and "33" in str(voltage or "").lower():
        return "outgoing_33kv"
    return ftype
```

- [ ] **Step 5: Run the tests, verify they pass**

Run: `.venv/bin/python -m pytest tests/test_importer.py -v`
Expected: PASS (integration tests `skip` if the sample xlsx is absent; unit tests pass).

- [ ] **Step 6: Update the template import-notes**

In `app/services/template_generator.py`, find note item 12 (`"12. Bus coupler rows: ..."`) and
replace it plus add item 13:

```python
        ["12. Bus coupler rows: set Feeder Name to 'Bus Coupler'. Set Feeder Voltage to 33kV for a 33kV bus coupler, otherwise it is treated as an 11kV bus coupler. (Feeder Type is ignored for these rows.)"],
        ["13. A row whose Feeder Name contains 'Station' or 'Auxiliary' is imported as the station transformer. An 'Outgoing Feeder' row at 33kV voltage is imported as a full 33kV outgoing bay."],
```

(If a note 13 already exists, renumber the trailing notes accordingly.)

- [ ] **Step 7: Run the template round-trip test**

Run: `.venv/bin/python -m pytest tests/test_importer.py::test_generated_template_imports_cleanly -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/services/importer.py app/services/template_generator.py tests/test_importer.py
git commit -m "feat: import 33kV outgoing feeders and station transformer types

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: New symbol helpers + `RATINGS`

**Files:**
- Modify: `app/services/sld_generator.py` (add near the other `sym_*` helpers, above `class SLDGenerator`)
- Test: `tests/test_sld_generator.py` — **replace the whole file** with a new symbol-only test module now; Tasks 4-9 append to it.

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `RATINGS: dict[str, str]` with keys `vcb_33`, `vcb_11`, `iso_33`, `iso_11`, `la`, `ct`.
  - `sym_station_transformer(x: int, y: int, label: str = "Station Tr") -> str`
  - `sym_ocef_marker(x: int, y: int) -> str`
  - `sym_bus_coupler_horizontal(x: int, y: int, color: str = "#333333") -> str`
  - existing helpers (`sym_line`, `sym_lightning_arrester`, `sym_isolator`, `sym_vcb`,
    `sym_autorecloser`, `sym_ct`, `sym_bus_pt`, `sym_transformer`, `sym_busbar`,
    `sym_feeder_out`, `sym_bus_coupler_vertical`, `is_autorecloser`) stay and keep their
    current signatures.

- [ ] **Step 1: Replace the test file with a symbol-only module**

Overwrite `tests/test_sld_generator.py` with:

```python
"""SLD generator tests — symbol helpers, then _layout Scene structure, then
render smoke tests. Uses in-memory fakes; no MongoDB."""
import re
import pytest
from bson import ObjectId

from app.services import sld_generator as G
from app.services.sld_generator import SLDGenerator
from app.models import substation_doc, transformer_doc, feeder_doc


# ── Fakes ────────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, docs): self._docs = docs
    def sort(self, key, direction=1):
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self
    def __iter__(self): return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None): self.docs = docs or []
    def find_one(self, filt):
        for d in self.docs:
            if all(d.get(k) == v for k, v in filt.items()):
                return d
        return None
    def find(self, filt):
        return FakeCursor([d for d in self.docs if all(d.get(k) == v for k, v in filt.items())])


class FakeDB:
    def __init__(self, substations=None, feeders=None, transformers=None):
        self.substations = FakeCollection(substations or [])
        self.feeders = FakeCollection(feeders or [])
        self.transformers = FakeCollection(transformers or [])


# ── Symbol helpers ───────────────────────────────────────────────────────
def test_ratings_dict_has_all_keys():
    for k in ("vcb_33", "vcb_11", "iso_33", "iso_11", "la", "ct"):
        assert isinstance(G.RATINGS[k], str) and G.RATINGS[k]


def test_sym_station_transformer_renders_group_and_label():
    out = G.sym_station_transformer(100, 200, label="100 kVA 33/0.4kV Station Tr")
    assert "<g" in out and "</g>" in out
    assert "translate(100,200)" in out
    assert "Station Tr" in out
    assert "#006600" in out  # earth


def test_sym_ocef_marker_contains_text():
    out = G.sym_ocef_marker(0, 0)
    assert "OC/EF" in out
    assert "<g" in out


def test_sym_bus_coupler_horizontal_has_breaker_and_isolators():
    out = G.sym_bus_coupler_horizontal(300, 330)
    assert out.count("<line") >= 3   # iso - vcb - iso across the break
    assert "translate(300" in out or 'x1="300' in out
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'RATINGS'` etc.

- [ ] **Step 3: Add `RATINGS` and the three helpers**

In `app/services/sld_generator.py`, immediately after the module docstring / `AR_KEYWORDS`,
add:

```python
RATINGS = {
    "vcb_33": "1250A, 25kA",
    "vcb_11": "1250A, 25kA",
    "iso_33": "630A, 25kA",
    "iso_11": "630A, 25kA",
    "la":     "30kV, 10kA",
    "ct":     "400/5A",
}
```

After `sym_bus_coupler_vertical` (before `class SLDGenerator`), add:

```python
def sym_station_transformer(x, y, label="Station Tr"):
    lines = label.split("\n")
    text_els = "".join(
        f'<tspan x="20" dy="{0 if i == 0 else 11}" font-size="8">{ln}</tspan>'
        for i, ln in enumerate(lines)
    )
    return f"""<g class="sym-stn-tr" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="-10" stroke="#CC2200" stroke-width="2"/>
    <circle cx="0" cy="0" r="10" fill="white" stroke="#CC2200" stroke-width="2"/>
    <circle cx="0" cy="12" r="10" fill="white" stroke="#888" stroke-width="1.8"/>
    <line x1="0" y1="22" x2="0" y2="28" stroke="#006600" stroke-width="2"/>
    <line x1="-7" y1="28" x2="7" y2="28" stroke="#006600" stroke-width="2"/>
    <line x1="-4" y1="32" x2="4" y2="32" stroke="#006600" stroke-width="1.4"/>
    <text font-weight="600" fill="#333" y="-4">{text_els}</text>
  </g>"""


def sym_ocef_marker(x, y):
    return f"""<g class="sym-ocef" transform="translate({x},{y})">
    <rect x="-2" y="-6" width="18" height="12" fill="white" stroke="#888" stroke-width="1"/>
    <text x="7" y="3" text-anchor="middle" font-size="6.5" fill="#666">OC/EF</text>
    <text x="24" y="3" font-size="7" fill="#888">TVM</text>
  </g>"""


def sym_bus_coupler_horizontal(x, y, color="#333333"):
    """Short horizontal break in a bus: Iso - VCB - Iso, centred on x at height y."""
    return f"""<g class="sym-bc-h" transform="translate({x},{y})">
    <line x1="-34" y1="0" x2="-22" y2="0" stroke="{color}" stroke-width="2"/>
    <line x1="-22" y1="0" x2="-10" y2="-9" stroke="{color}" stroke-width="1.8"/>
    <circle cx="-22" cy="0" r="2.2" fill="{color}"/>
    <rect x="-10" y="-9" width="20" height="18" fill="white" stroke="{color}" stroke-width="2" rx="1"/>
    <line x1="-7" y1="-6" x2="7" y2="6" stroke="{color}" stroke-width="1.4"/>
    <line x1="7" y1="-6" x2="-7" y2="6" stroke="{color}" stroke-width="1.4"/>
    <line x1="10" y1="-9" x2="22" y2="0" stroke="{color}" stroke-width="1.8"/>
    <circle cx="22" cy="0" r="2.2" fill="{color}"/>
    <line x1="22" y1="0" x2="34" y2="0" stroke="{color}" stroke-width="2"/>
    <text x="0" y="22" text-anchor="middle" font-size="8" fill="{color}" font-weight="700">BUS COUPLER</text>
  </g>"""
```

- [ ] **Step 4: Run, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: RATINGS dict + station-transformer/OC-EF/horizontal-coupler symbols

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `Scene` dataclasses + `_layout` core (degenerate case)

**Files:**
- Modify: `app/services/sld_generator.py` (add dataclasses + `LAYOUT` constants + `Y` bands above `class SLDGenerator`; add `_layout` and bay-builder methods to the class; leave the old `generate`/`_render_*` in place for now)
- Test: `tests/test_sld_generator.py` (append)

**Interfaces:**
- Consumes: `RATINGS`, `is_autorecloser` (Task 3).
- Produces:
  - Dataclasses `Equip`, `Bay`, `Bus`, `Section`, `Coupler`, `LegendEntry`, `LegendBox`,
    `TitleBlock`, `Scene` (fields exactly as listed in Step 3).
  - `LAYOUT = {"MARGIN": 80, "BAY_W": 130, "FEEDER_W": 110, "MIN_W": 940}`
  - `Y = {...}` band dict with keys `title, bay33_top, bay33_bot, bus33, tr_top, tr_bot,
    bus11, feed_top, feed_bot, legend`.
  - `SLDGenerator._layout(self, ss: dict, feeders: list[dict], transformers: list[dict]) -> Scene`
  - Helper methods `_bay_33kv(self, feeder, x, segment)`, `_bay_transformer(self, tr, x, segment)`,
    `_bay_11kv_feeder(self, feeder, x)`, `_bay_11kv_incomer(self, tr, x)` each returning a `Bay`.
  - This task's `_layout` handles: title, one `bus33` segment (`coupler_x=None`),
    `bays33` = incomers (sorted by `sequence`) + transformer bays + a synthetic
    `bus_pt_33` bay pinned right; `sections11` = one `Section` per transformer with its
    `outgoing_11kv` feeders (matched by `transformer_id`, round-robin fallback for
    unmatched) as `feeder_bays`; `couplers11 = []`; `legend = None` (Task 9 fills it).

- [ ] **Step 1: Append layout tests**

Add to `tests/test_sld_generator.py`:

```python
# ── _layout: degenerate / single-transformer ─────────────────────────────
def _ss(name="Ulubari", bus_config="single_bus", **kw):
    d = substation_doc(name=name, region="LAR", circle="GEC-II", tnc="T", esd="E",
                       gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
                       gss_primary="132kV Sishugram GSS", **kw)
    d["_id"] = ObjectId()
    d["topology"]["bus_config"] = bus_config
    return d


def _tr(ss, seq, cap=10.0):
    t = transformer_doc(substation_id=ss["_id"], sequence=seq, capacity_mva=cap,
                        make="BHEL", yom=2015)
    t["_id"] = ObjectId()
    return t


def _fd(ss, seq, name, ftype, volt=11, tr=None):
    f = feeder_doc(substation_id=ss["_id"],
                   transformer_id=(tr["_id"] if tr else None),
                   sequence=seq, name=name, voltage_kv=volt, feeder_type=ftype)
    f["_id"] = ObjectId()
    return f


def _build(ss, feeders, transformers):
    db = FakeDB(substations=[ss], feeders=feeders, transformers=transformers)
    gen = SLDGenerator(db)
    scene = gen._layout(ss, sorted(feeders, key=lambda x: x["sequence"]), transformers)
    return db, gen, scene


def test_layout_single_transformer_scene_shape():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 3, "New Ulubari", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 4, "East", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 5, "Rehabari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])

    assert scene.bus33.coupler_x is None
    assert len(scene.bus33.segments) == 1
    assert scene.couplers11 == []
    assert len(scene.sections11) == 1
    kinds = [b.kind for b in scene.bays33]
    assert kinds.count("incomer_33kv") == 1
    assert kinds.count("transformer") == 1
    assert kinds.count("bus_pt_33") == 1
    assert kinds[-1] == "bus_pt_33"  # pinned rightmost
    sec = scene.sections11[0]
    assert [b.label for b in sec.feeder_bays] == ["New Ulubari", "East", "Rehabari"]
    assert scene.title.name == "Ulubari"
    assert re.match(r"\d{2}\.\d{2}\.\d{4}$", scene.title.last_update_str)


def test_layout_unassigned_11kv_feeders_round_robin_across_sections():
    ss = _ss()
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "F1", "outgoing_11kv", 11),   # no transformer_id
        _fd(ss, 4, "F2", "outgoing_11kv", 11),
        _fd(ss, 5, "F3", "outgoing_11kv", 11),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    counts = sorted(len(s.feeder_bays) for s in scene.sections11)
    assert counts == [1, 2]  # 3 feeders split 2/1 across 2 sections


def test_layout_transformer_bay_never_reaches_11kv_band():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [_fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
               _fd(ss, 2, "F1", "outgoing_11kv", 11, tr=t1)]
    _, _, scene = _build(ss, feeders, [t1])
    tr_bay = next(b for b in scene.bays33 if b.kind == "transformer")
    assert tr_bay.x == scene.sections11[0].bus[0] or tr_bay.x >= G.LAYOUT["MARGIN"]
    assert G.Y["tr_bot"] < G.Y["bus11"]
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k layout -v`
Expected: FAIL — `AttributeError: 'SLDGenerator' object has no attribute '_layout'`.

- [ ] **Step 3: Add dataclasses, constants and `_layout`**

In `app/services/sld_generator.py`, add at the top (after `from bson import ObjectId`):

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone


LAYOUT = {"MARGIN": 80, "BAY_W": 130, "FEEDER_W": 110, "MIN_W": 940}

Y = {
    "title": 8, "bay33_top": 74, "bay33_bot": 300, "bus33": 330,
    "tr_top": 366, "tr_bot": 476, "bus11": 524, "feed_top": 560,
    "feed_bot": 664, "legend": 704,
}


@dataclass
class Equip:
    kind: str                       # "la"|"isolator"|"vcb"|"ar"|"ct"|"ocef"
    label: str = ""
    has_earth: bool = False


@dataclass
class Bay:
    kind: str                       # see spec §2.1
    x: int
    label: str = ""
    segment: int = 0
    voltage_kv: int = 33
    equipment: list = field(default_factory=list)
    ref: dict = None


@dataclass
class Bus:
    y: int
    segments: list                  # list[tuple[int, int]]
    coupler_x: int = None


@dataclass
class Section:
    tr_index: int
    bus: tuple                      # (x0, x1, y)
    incomer_bay: Bay
    bus_pt_x: int
    feeder_bays: list = field(default_factory=list)


@dataclass
class Coupler:
    orientation: str                # "h33" | "h11"
    between: tuple
    x: int


@dataclass
class LegendEntry:
    glyph_kind: str
    name: str
    description: str


@dataclass
class LegendBox:
    x: int
    y: int
    w: int
    h: int
    entries: list = field(default_factory=list)


@dataclass
class TitleBlock:
    name: str
    last_update_str: str
    source_str: str


@dataclass
class Scene:
    width: int
    height: int
    title: TitleBlock
    bus33: Bus
    bays33: list
    sections11: list
    couplers11: list
    legend: LegendBox = None
```

Then add these methods to `class SLDGenerator` (above the existing `generate`):

```python
    # ── layout phase ────────────────────────────────────────────────────
    def _layout(self, ss, feeders, transformers):
        M = LAYOUT["MARGIN"]
        by_type = {}
        for f in feeders:
            by_type.setdefault(f["feeder_type"], []).append(f)
        inc33   = sorted(by_type.get("incoming_33kv", []), key=lambda f: f.get("sequence", 0))
        out33   = sorted(by_type.get("outgoing_33kv", []), key=lambda f: f.get("sequence", 0))
        stn     = by_type.get("station_transformer", [])
        trs     = sorted(transformers, key=lambda t: t.get("sequence", 0))

        # feeders -> section index
        tr_id_to_idx = {t["_id"]: i for i, t in enumerate(trs)}
        sec_feeders = [[] for _ in trs] or [[]]
        rr = 0
        for f in sorted(by_type.get("outgoing_11kv", []), key=lambda f: f.get("sequence", 0)):
            idx = tr_id_to_idx.get(f.get("transformer_id"))
            if idx is None:
                idx = rr % len(sec_feeders)
                rr += 1
            sec_feeders[idx].append(f)

        # ---- horizontal sizing ----
        n_sec = max(len(trs), 1)
        sec_widths = [max(1, len(sec_feeders[i])) * LAYOUT["FEEDER_W"] + LAYOUT["FEEDER_W"]
                      for i in range(n_sec)]
        n_bays33 = len(inc33) + len(trs) + len(out33) + len(stn) + 1  # +1 bus PT
        width = max(LAYOUT["MIN_W"],
                    n_bays33 * LAYOUT["BAY_W"] + 2 * M,
                    sum(sec_widths) + 2 * M)

        # ---- 33 kV bays, left -> right ----
        bays33 = []
        x = M + LAYOUT["BAY_W"] // 2
        for f in inc33:
            bays33.append(self._bay_33kv(f, x, 0)); x += LAYOUT["BAY_W"]
        for t in trs:
            bays33.append(self._bay_transformer(t, x, 0)); x += LAYOUT["BAY_W"]
        for f in out33:
            bays33.append(self._bay_33kv(f, x, 0)); x += LAYOUT["BAY_W"]
        for f in stn:
            b = self._bay_33kv(f, x, 0)
            b.kind = "station_transformer"
            b.equipment = [Equip("la", RATINGS["la"]), Equip("isolator", RATINGS["iso_33"])]
            bays33.append(b); x += LAYOUT["BAY_W"]
        bus_pt = Bay(kind="bus_pt_33", x=width - M, label="33kV Bus PT", voltage_kv=33)
        bays33.append(bus_pt)

        bus33 = Bus(y=Y["bus33"], segments=[(M, width - M)], coupler_x=None)

        # ---- 11 kV sections ----
        sections11 = []
        sx = M
        for i in range(n_sec):
            x0, x1 = sx, sx + sec_widths[i]
            tr = trs[i] if i < len(trs) else None
            fx = x0 + LAYOUT["FEEDER_W"]
            fbays = []
            for f in sec_feeders[i]:
                fbays.append(self._bay_11kv_feeder(f, fx)); fx += LAYOUT["FEEDER_W"]
            inc_bay = self._bay_11kv_incomer(tr, x0 + LAYOUT["FEEDER_W"] // 2)
            sections11.append(Section(tr_index=i, bus=(x0, x1, Y["bus11"]),
                                      incomer_bay=inc_bay, bus_pt_x=x0 + 10,
                                      feeder_bays=fbays))
            sx = x1

        # ---- title ----
        updated = ss.get("updated_at") or datetime.now(timezone.utc)
        topo = ss.get("topology", {})
        title = TitleBlock(
            name=ss.get("name", "Substation"),
            last_update_str=updated.strftime("%d.%m.%Y"),
            source_str=f'SOURCE: {ss.get("gss_primary", "—")} · '
                       f'{(topo.get("bus_config") or "single_bus").replace("_", " ").title()}',
        )

        return Scene(width=width, height=Y["legend"], title=title, bus33=bus33,
                     bays33=bays33, sections11=sections11, couplers11=[], legend=None)

    # ── bay builders ───────────────────────────────────────────────────
    def _bay_33kv(self, feeder, x, segment):
        v = "33"
        sg = feeder.get("switchgear", {})
        ar = is_autorecloser(feeder)
        eq = [
            Equip("la", RATINGS["la"]),
            Equip("isolator", RATINGS["iso_33"], has_earth=False),
            Equip("ar" if ar else "vcb",
                  (sg.get("vcb_make") or "VCB") + "\n" + RATINGS["vcb_33"]),
            Equip("ct", feeder.get("meter", {}).get("ctr") or RATINGS["ct"]),
        ]
        if sg.get("oc_ef_relay_type"):
            eq.append(Equip("ocef"))
        kind = "incomer_33kv" if feeder["feeder_type"] == "incoming_33kv" else "outgoing_33kv"
        return Bay(kind=kind, x=x, label=feeder["name"], segment=segment,
                   voltage_kv=33, equipment=eq, ref=feeder)

    def _bay_transformer(self, tr, x, segment):
        cap = tr.get("capacity_mva", "?")
        return Bay(kind="transformer", x=x, segment=segment, voltage_kv=33,
                   label=f'{cap} MVA 33/11kV Pr. Transformer - {tr.get("sequence", "")}',
                   equipment=[Equip("isolator", RATINGS["iso_33"], has_earth=True)],
                   ref=tr)

    def _bay_11kv_feeder(self, feeder, x):
        sg = feeder.get("switchgear", {})
        ar = is_autorecloser(feeder)
        eq = [
            Equip("isolator", RATINGS["iso_11"], has_earth=True),
            Equip("ar" if ar else "vcb",
                  (sg.get("vcb_make") or "VCB") + "\n" + RATINGS["vcb_11"]),
            Equip("ct", feeder.get("meter", {}).get("ctr") or RATINGS["ct"]),
        ]
        return Bay(kind="outgoing_11kv", x=x, label=feeder["name"], voltage_kv=11,
                   equipment=eq, ref=feeder)

    def _bay_11kv_incomer(self, tr, x):
        seq = tr.get("sequence", "") if tr else ""
        return Bay(kind="incomer_11kv", x=x, voltage_kv=11,
                   label=f"11kV I/C-{seq}",
                   equipment=[Equip("vcb", "VCB\n" + RATINGS["vcb_11"]),
                              Equip("ct", RATINGS["ct"])],
                   ref=tr)
```

- [ ] **Step 4: Run, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k layout -v`
Expected: PASS (3 layout tests + earlier symbol tests still pass).

- [ ] **Step 5: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: Scene dataclasses + _layout core for single/degenerate case

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `_layout` — 33 kV outgoing bays + station-transformer bay assertions

**Files:**
- Modify: `app/services/sld_generator.py` (no new code expected — Task 4 already builds `out33`
  and `stn` bays; this task adds the tests that lock the behaviour and fixes `_layout` only if
  they fail)
- Test: `tests/test_sld_generator.py` (append)

**Interfaces:**
- Consumes: `_layout` (Task 4).
- Produces: guarantees that `outgoing_33kv` feeders become `Bay(kind="outgoing_33kv")` with a
  full 4-item equipment stack, and each `station_transformer` feeder becomes exactly one
  `Bay(kind="station_transformer")` placed after the 33 kV outgoing bays and before the
  `bus_pt_33` bay.

- [ ] **Step 1: Append tests**

```python
# ── _layout: 33 kV outgoing + station transformer ────────────────────────
def test_layout_33kv_outgoing_feeder_gets_full_bay():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 3, "33kV Chandmari O/g", "outgoing_33kv", 33),
        _fd(ss, 4, "33kV Paltanbazar O/g", "outgoing_33kv", 33),
        _fd(ss, 5, "New Ulubari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])
    og = [b for b in scene.bays33 if b.kind == "outgoing_33kv"]
    assert [b.label for b in og] == ["33kV Chandmari O/g", "33kV Paltanbazar O/g"]
    assert [e.kind for e in og[0].equipment][:4] == ["la", "isolator", "vcb", "ct"]
    assert og[0].voltage_kv == 33


def test_layout_station_transformer_single_bay_before_bus_pt():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "100 kVA 33/0.4kV Station Tr", "station_transformer", 33),
        _fd(ss, 3, "New Ulubari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])
    kinds = [b.kind for b in scene.bays33]
    assert kinds.count("station_transformer") == 1
    assert kinds.index("station_transformer") == len(kinds) - 2  # just before bus_pt_33
    assert kinds[-1] == "bus_pt_33"


def test_layout_ocef_marker_only_when_relay_data_present():
    ss = _ss()
    t1 = _tr(ss, 1)
    f_with = _fd(ss, 1, "33kV A O/g", "outgoing_33kv", 33)
    f_with["switchgear"]["oc_ef_relay_type"] = "Numerical"
    f_without = _fd(ss, 2, "33kV B O/g", "outgoing_33kv", 33)
    _, _, scene = _build(ss, [f_with, f_without, _fd(ss, 3, "Tr-1 HV", "transformer_hv", 33, tr=t1)], [t1])
    a = next(b for b in scene.bays33 if b.label == "33kV A O/g")
    b = next(b for b in scene.bays33 if b.label == "33kV B O/g")
    assert any(e.kind == "ocef" for e in a.equipment)
    assert not any(e.kind == "ocef" for e in b.equipment)
```

- [ ] **Step 2: Run**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k layout -v`
Expected: PASS. If any fail, adjust `_layout` bay ordering / `_bay_33kv` equipment list to match, then re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sld_generator.py app/services/sld_generator.py
git commit -m "test: lock 33kV outgoing + station-transformer bay layout

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `_layout` — 33 kV bus coupler segmentation

**Files:**
- Modify: `app/services/sld_generator.py` (`_layout` — replace the single-segment `bus33`
  construction with the two-segment branch)
- Test: `tests/test_sld_generator.py` (append)

**Interfaces:**
- Consumes: `_layout` (Task 4).
- Produces: when any `bus_coupler` feeder has `voltage_kv == 33`, `scene.bus33.segments` has
  two `(x0, x1)` tuples and `scene.bus33.coupler_x` is the split x (horizontal centre of the
  diagram, rounded int); each `Bay` in `bays33` (except `bus_pt_33`) has `segment` 0 for the
  first `ceil(k/2)` non-busPT bays in left-to-right order and 1 for the rest; the `bus_pt_33`
  bay has `segment = 1`. With no 33 kV coupler, behaviour is unchanged (one segment,
  `coupler_x = None`, all `segment = 0`).

- [ ] **Step 1: Append tests**

```python
# ── _layout: 33 kV bus coupler ──────────────────────────────────────────
def _ulubari_feeders(ss, trs):
    t1, t2, t3 = trs
    return [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "33kV UG Incomer-2", "incoming_33kv", 33),
        _fd(ss, 3, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 4, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 5, "Tr-3 HV", "transformer_hv", 33, tr=t3),
        _fd(ss, 6, "33kV Chandmari O/g", "outgoing_33kv", 33),
        _fd(ss, 7, "33kV Paltanbazar O/g", "outgoing_33kv", 33),
        _fd(ss, 8, "33kV Kalapahar O/g", "outgoing_33kv", 33),
        _fd(ss, 9, "100 kVA 33/0.4kV Station Tr", "station_transformer", 33),
        _fd(ss, 10, "33kV Bus Coupler", "bus_coupler", 33),
        _fd(ss, 11, "11kV Bus Coupler", "bus_coupler", 11),
        _fd(ss, 12, "New Ulubari", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 13, "East", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 14, "Rehabari", "outgoing_11kv", 11, tr=t2),
        _fd(ss, 15, "Gopinath", "outgoing_11kv", 11, tr=t2),
        _fd(ss, 16, "South Surekha", "outgoing_11kv", 11, tr=t3),
        _fd(ss, 17, "South", "outgoing_11kv", 11, tr=t3),
    ]


def test_layout_no_33kv_coupler_single_segment():
    ss = _ss()
    t1 = _tr(ss, 1)
    _, _, scene = _build(ss, [_fd(ss, 1, "I1", "incoming_33kv", 33),
                              _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1)], [t1])
    assert len(scene.bus33.segments) == 1
    assert scene.bus33.coupler_x is None
    assert all(b.segment == 0 for b in scene.bays33)


def test_layout_33kv_coupler_two_segments_and_split_bays():
    ss = _ss(bus_config="sectionalized_33kv")
    trs = [_tr(ss, 1), _tr(ss, 2), _tr(ss, 3)]
    _, _, scene = _build(ss, _ulubari_feeders(ss, trs), trs)
    assert len(scene.bus33.segments) == 2
    assert scene.bus33.coupler_x is not None
    seg0 = [b for b in scene.bays33 if b.kind != "bus_pt_33" and b.segment == 0]
    seg1 = [b for b in scene.bays33 if b.kind != "bus_pt_33" and b.segment == 1]
    assert len(seg0) >= 1 and len(seg1) >= 1
    assert abs(len(seg0) - len(seg1)) <= 1
    # segments are contiguous and meet at coupler_x
    (a0, a1), (b0, b1) = scene.bus33.segments
    assert a1 <= scene.bus33.coupler_x <= b0 or a1 == b0
```

- [ ] **Step 2: Run, verify the two-segment test fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k "33kv_coupler" -v`
Expected: FAIL — still one segment.

- [ ] **Step 3: Add the coupler branch to `_layout`**

In `_layout`, replace the line
`bus33 = Bus(y=Y["bus33"], segments=[(M, width - M)], coupler_x=None)`
with:

```python
        has_33_bc = any(f.get("voltage_kv") == 33 for f in by_type.get("bus_coupler", []))
        non_pt = [b for b in bays33 if b.kind != "bus_pt_33"]
        if has_33_bc and non_pt:
            split = width // 2
            left_n = (len(non_pt) + 1) // 2           # ceil
            for j, b in enumerate(non_pt):
                b.segment = 0 if j < left_n else 1
            bus_pt.segment = 1
            left_bays  = [b for b in non_pt if b.segment == 0]
            right_bays = [b for b in non_pt if b.segment == 1]
            l1 = max([b.x for b in left_bays], default=split - 40) + 30
            r0 = min([b.x for b in right_bays], default=split + 40) - 30
            bus33 = Bus(y=Y["bus33"],
                        segments=[(M, min(l1, split - 10)), (max(r0, split + 10), width - M)],
                        coupler_x=split)
        else:
            bus33 = Bus(y=Y["bus33"], segments=[(M, width - M)], coupler_x=None)
```

- [ ] **Step 4: Run, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k layout -v`
Expected: PASS (all layout tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: split the 33kV bus into two segments when a 33kV coupler exists

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: `_layout` — 11 kV bus couplers

**Files:**
- Modify: `app/services/sld_generator.py` (`_layout` — populate `couplers11` before the
  `return`)
- Test: `tests/test_sld_generator.py` (append)

**Interfaces:**
- Consumes: `_layout` (Tasks 4, 6).
- Produces: `scene.couplers11` is a list of `Coupler(orientation="h11", between=(k, k+1),
  x=<mid-gap x between sections[k] and sections[k+1]>)`, one per 11 kV `bus_coupler` feeder
  (those with `voltage_kv != 33`), assigned to consecutive section gaps starting at
  `(0, 1)`. The 11 kV sections sit side-by-side at one Y (`Y["bus11"]`), so the coupler is
  **horizontal** (rendered with `sym_bus_coupler_horizontal` in Task 8). If there are more
  11 kV coupler records than section gaps (`len(sections11) - 1`), the extras are ignored.
  Trailing sections with no coupler stay absent from `couplers11` (electrically isolated).

- [ ] **Step 1: Append tests**

```python
# ── _layout: 11 kV bus couplers ─────────────────────────────────────────
def test_layout_two_sections_one_11kv_coupler():
    ss = _ss(bus_config="sectionalized_11kv")
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "11kV Bus Coupler", "bus_coupler", 11),
        _fd(ss, 4, "F1", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 5, "F2", "outgoing_11kv", 11, tr=t2),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    assert len(scene.couplers11) == 1
    c = scene.couplers11[0]
    assert c.orientation == "h11" and c.between == (0, 1)
    s0x1 = scene.sections11[0].bus[1]
    s1x0 = scene.sections11[1].bus[0]
    assert min(s0x1, s1x0) - 5 <= c.x <= max(s0x1, s1x0) + 5


def test_layout_three_sections_one_coupler_leaves_third_isolated():
    ss = _ss(bus_config="sectionalized_both")
    trs = [_tr(ss, 1), _tr(ss, 2), _tr(ss, 3)]
    _, _, scene = _build(ss, _ulubari_feeders(ss, trs), trs)
    assert len(scene.sections11) == 3
    assert [c.between for c in scene.couplers11] == [(0, 1)]  # sections 1-2 coupled, 3 isolated


def test_layout_more_coupler_records_than_gaps_are_ignored():
    ss = _ss()
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "11kV Bus Coupler A", "bus_coupler", 11),
        _fd(ss, 4, "11kV Bus Coupler B", "bus_coupler", 11),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    assert len(scene.couplers11) == 1  # only one gap available
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k "11kv_coupler or isolated or coupler_records" -v`
Expected: FAIL — `couplers11` is empty.

- [ ] **Step 3: Populate `couplers11` in `_layout`**

Just before `return Scene(...)`, add:

```python
        n_11_bc = sum(1 for f in by_type.get("bus_coupler", []) if f.get("voltage_kv") != 33)
        couplers11 = []
        for k in range(min(n_11_bc, max(len(sections11) - 1, 0))):
            gap_x = (sections11[k].bus[1] + sections11[k + 1].bus[0]) // 2
            couplers11.append(Coupler(orientation="h11", between=(k, k + 1), x=gap_x))
```

and change the `return` to pass `couplers11=couplers11` instead of `couplers11=[]`.

- [ ] **Step 4: Run, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: data-driven 11kV bus couplers between consecutive sections

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: `_render` — emit SVG from the Scene; wire `generate`; delete old renderers

**Files:**
- Modify: `app/services/sld_generator.py` (add `_render` + `_svg_header` rewrite; replace
  `generate` body; **delete** `_render_single_bus`, `_render_double_bus`, `_equipment_table`)
- Test: `tests/test_sld_generator.py` (append render smoke tests)

**Interfaces:**
- Consumes: `_layout` (Tasks 4-7), all `sym_*` helpers, `RATINGS`, `Y`.
- Produces:
  - `SLDGenerator.generate(substation_id: str) -> str` — loads docs, calls `_layout`, returns
    `_render(scene)`; returns `self._error_svg("Substation not found")` when the substation is
    missing (unchanged behaviour).
  - `SLDGenerator._render(self, scene: Scene) -> str` — returns a complete
    `<svg …>…</svg>` string containing: the title block (name line, `DATE OF LAST UPDATE`
    line, grey source line), both/one 33 kV bus segment(s) + horizontal coupler when
    `coupler_x` is set, every 33 kV bay stacked between `Y["bay33_top"]` and `Y["bus33"]`,
    transformer bays dropping to `Y["bus11"]`, each 11 kV section bus + its bus PT + incomer
    + feeder bays + rotated feeder-name labels, horizontal 11 kV couplers between sections,
    and `</svg>`.
  - `sym_bus_coupler_vertical` is now unused — **delete it** in this task.
  - `_svg_header(self, title: TitleBlock, w: int, h: int) -> str` — opening `<svg>` +
    `<defs><style>` + white background + dark title bar with the three text lines.
  - The string `lilo` appears nowhere in `app/services/sld_generator.py`.

- [ ] **Step 1: Append render smoke tests**

```python
# ── _render smoke ───────────────────────────────────────────────────────
def test_generate_full_ulubari_svg_smoke():
    ss = _ss(bus_config="sectionalized_both")
    trs = [_tr(ss, 1), _tr(ss, 2), _tr(ss, 3)]
    feeders = _ulubari_feeders(ss, trs)
    db = FakeDB(substations=[ss], feeders=feeders, transformers=trs)
    svg = SLDGenerator(db).generate(str(ss["_id"]))

    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "DATE OF LAST UPDATE" in svg
    assert "ULUBARI" in svg.upper()
    for nm in ["33kV UG Incomer-1", "33kV Chandmari O/g", "New Ulubari",
               "South Surekha", "Station Tr"]:
        assert nm in svg
    assert "BUS COUPLER" in svg
    assert "lilo" not in svg.lower()
    assert "33 kV" in svg or "33KV" in svg.upper()


def test_generate_missing_substation_returns_error_svg():
    db = FakeDB(substations=[], feeders=[], transformers=[])
    svg = SLDGenerator(db).generate(str(ObjectId()))
    assert "Substation not found" in svg


def test_generate_single_transformer_still_renders():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [_fd(ss, 1, "33kV Incomer", "incoming_33kv", 33),
               _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1),
               _fd(ss, 3, "Feeder A", "outgoing_11kv", 11, tr=t1)]
    db = FakeDB(substations=[ss], feeders=feeders, transformers=[t1])
    svg = SLDGenerator(db).generate(str(ss["_id"]))
    assert "Feeder A" in svg and svg.count("<svg") == 1
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k "smoke or missing_substation or single_transformer_still" -v`
Expected: FAIL — current `generate` still routes to the old renderers using the removed
`bus_config` values / old topology keys.

- [ ] **Step 3: Rewrite `generate`, add `_render` + `_svg_header`, delete old renderers**

Replace the `generate` method body with:

```python
    def generate(self, substation_id: str) -> str:
        ss = self.db.substations.find_one({"_id": ObjectId(substation_id)})
        if not ss:
            return self._error_svg("Substation not found")
        feeders = list(self.db.feeders.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))
        transformers = list(self.db.transformers.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))
        scene = self._layout(ss, feeders, transformers)
        return self._render(scene)
```

**Delete** the methods `_render_single_bus`, `_render_double_bus`, and `_equipment_table`
entirely.

Rewrite `_svg_header`:

```python
    def _svg_header(self, title, w, h):
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" id="sld-svg" font-family="Rajdhani,sans-serif">
  <defs><style>
    .lbl33{{font-size:8px;fill:#CC2200}}
    .lbl11{{font-size:8px;fill:#0055CC}}
    .eqlbl{{font-size:7px;fill:#666}}
    .feednm{{font-size:9px;font-weight:600}}
  </style></defs>
  <rect x="1" y="1" width="{w-2}" height="{h-2}" fill="white" stroke="#ccc" stroke-width="1" rx="4"/>
  <rect x="1" y="1" width="{w-2}" height="40" fill="#1a2744"/>
  <text x="{w//2}" y="17" text-anchor="middle" font-size="13" font-weight="700" fill="white" letter-spacing="1">SLD - 33/11kV {title.name.upper()} ELECTRICAL SUB-STATION</text>
  <text x="{w//2}" y="31" text-anchor="middle" font-size="10" font-weight="600" fill="#cbd5e1">DATE OF LAST UPDATE: {title.last_update_str}</text>
  <text x="{w//2}" y="52" text-anchor="middle" font-size="8" fill="#999">{title.source_str}</text>
"""
```

Add `_render` (after `_svg_header`):

```python
    def _render(self, scene):
        p = [self._svg_header(scene.title, scene.width, scene.height)]

        # 33 kV bus segments
        for (x0, x1) in scene.bus33.segments:
            p.append(sym_busbar(x0, scene.bus33.y, x1, "33 kV BUS", "#111111", 33))
        if scene.bus33.coupler_x is not None:
            p.append(sym_bus_coupler_horizontal(scene.bus33.coupler_x, scene.bus33.y))

        # 33 kV bays (above the bus)
        for bay in scene.bays33:
            p.append(self._render_bay_33kv(bay, scene.bus33.y))

        # 11 kV sections
        for sec in scene.sections11:
            x0, x1, y = sec.bus
            p.append(sym_busbar(x0 + 8, y, x1 - 8, f"11 kV BUS - {sec.tr_index + 1}", "#0055CC", 11))
            p.append(sym_bus_pt(sec.bus_pt_x, y - 40, label="11kV Bus PT"))
            p.append(self._render_section_incomer(sec, y))
            for fb in sec.feeder_bays:
                p.append(self._render_bay_11kv(fb, y))

        # 11 kV couplers (horizontal — sections are side-by-side at one Y)
        for c in scene.couplers11:
            p.append(sym_bus_coupler_horizontal(c.x, scene.sections11[c.between[0]].bus[2]))

        if scene.legend:
            p.append(self._render_legend(scene.legend))

        p.append("</svg>")
        return "".join(p)

    # --- render helpers -------------------------------------------------
    def _render_bay_33kv(self, bay, bus_y):
        c = "#CC2200"
        if bay.kind == "bus_pt_33":
            out = [sym_bus_pt(bay.x, bus_y - 44, label="33kV Bus PT"),
                   f'<line x1="{bay.x}" y1="{bus_y}" x2="{bay.x}" y2="{bus_y-4}" stroke="#888" stroke-width="1"/>']
            return "".join(out)
        if bay.kind == "station_transformer":
            out = [f'<text x="{bay.x}" y="{Y["bay33_top"]-6}" text-anchor="middle" class="lbl33">{bay.label[:34]}</text>',
                   sym_line(bay.x, bus_y, bay.x, Y["bay33_top"]+10, color=c),
                   sym_isolator(bay.x, Y["bay33_top"]+30, has_earth=False, color=c, label=RATINGS["iso_33"]),
                   sym_station_transformer(bay.x, Y["bay33_top"]+70, label=bay.label.replace(" ", "\n", 1))]
            return "".join(out)

        top = Y["bay33_top"]
        out = [f'<text x="{bay.x}" y="{top-8}" text-anchor="middle" class="lbl33">{bay.label[:24]}</text>']
        y = top
        step = (bus_y - top) / (len(bay.equipment) + 1)
        for e in bay.equipment:
            y += step
            out.append(self._render_equip(e, bay.x, int(y), c))
        out.append(sym_line(bay.x, top, bay.x, bus_y, color=c))
        return "".join(out)

    def _render_bay_11kv(self, bay, bus_y):
        c = "#0055CC"
        out = [sym_line(bay.x, bus_y, bay.x, Y["feed_top"], color=c)]
        y = Y["feed_top"]
        step = (Y["feed_bot"] - Y["feed_top"]) / (len(bay.equipment) + 1)
        for e in bay.equipment:
            y += step
            out.append(self._render_equip(e, bay.x, int(y), c))
        out.append(sym_feeder_out(bay.x, Y["feed_bot"], bay.label,
                                  voltage_kv=11, is_ar=any(e.kind == "ar" for e in bay.equipment)))
        return "".join(out)

    def _render_section_incomer(self, sec, bus_y):
        bay = sec.incomer_bay
        c = "#0055CC"
        out = [sym_line(bay.x, Y["tr_bot"], bay.x, bus_y, color=c)]
        y = Y["tr_bot"] - 60
        for e in bay.equipment:
            out.append(self._render_equip(e, bay.x, int(y), c)); y += 30
        out.append(f'<text x="{bay.x+14}" y="{Y["tr_bot"]-70}" class="lbl11">{bay.label}</text>')
        return "".join(out)

    def _render_equip(self, e, x, y, c):
        if e.kind == "la":
            return sym_lightning_arrester(x, y, color=c)
        if e.kind == "isolator":
            return sym_isolator(x, y, has_earth=e.has_earth, color=c, label=e.label)
        if e.kind == "vcb":
            return sym_vcb(x, y, label=e.label.replace("\n", " "), color=c)
        if e.kind == "ar":
            return sym_autorecloser(x, y, color=c)
        if e.kind == "ct":
            return sym_ct(x, y, label=e.label or "CT", color="#555")
        if e.kind == "ocef":
            return sym_ocef_marker(x + 12, y)
        return ""

    def _render_legend(self, legend):
        return ""  # filled in Task 9
```

For the transformer bays specifically: `_render_bay_33kv` handles `kind == "transformer"` too —
add this branch near the top of `_render_bay_33kv` (before the generic bay code):

```python
        if bay.kind == "transformer":
            tr = bay.ref or {}
            out = [f'<text x="{bay.x}" y="{Y["bay33_top"]-8}" text-anchor="middle" class="lbl33">{bay.label[:30]}</text>',
                   sym_line(bay.x, bus_y, bay.x, Y["tr_top"]-18, color="#CC2200"),
                   sym_isolator(bay.x, Y["tr_top"], has_earth=True, color="#CC2200", label=RATINGS["iso_33"]),
                   sym_line(bay.x+12, Y["tr_top"]+18, bay.x, Y["tr_top"]+40, color="#CC2200"),
                   sym_transformer(bay.x, Y["tr_top"]+78, label=f'{tr.get("capacity_mva","?")}MVA\n33/11kV'),
                   sym_line(bay.x, Y["tr_top"]+116, bay.x, Y["bus11"], color="#0055CC")]
            return "".join(out)
```

- [ ] **Step 4: Run the full generator test file**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -v`
Expected: PASS (all). If a smoke assertion about a specific feeder name fails, it means a bay
isn't rendered — trace which loop skipped it and fix `_render`.

- [ ] **Step 5: Grep for stragglers**

Run: `grep -rn "lilo\|_render_single_bus\|_render_double_bus\|_equipment_table" app/`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: unified _render walks the Scene; delete single/double-bus renderers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: In-SVG legend box

**Files:**
- Modify: `app/services/sld_generator.py` (`_layout` builds `LegendBox`; `_render_legend`
  draws it; bump `Scene.height`)
- Test: `tests/test_sld_generator.py` (append)

**Interfaces:**
- Consumes: `_layout`, `_render` (Task 8).
- Produces:
  - `_layout` sets `scene.legend = LegendBox(x=MARGIN, y=Y["legend"], w=width-2*MARGIN,
    h=<computed>, entries=[LegendEntry, …])` with **12** entries (LA, Isolator, VCB,
    Auto-Recloser, CT, PT/VT, Power Transformer, Station Transformer, Bus Coupler, Busbar,
    Earth, OC/EF TVM).
  - `scene.height` is `Y["legend"] + legend.h + MARGIN`.
  - `_render_legend(legend) -> str` returns a `<g>` with a bordered `<rect>`, a
    `LEGEND` heading, and one row per entry (glyph placeholder box + bold name + description),
    laid out in 3 columns.

- [ ] **Step 1: Append tests**

```python
# ── legend ─────────────────────────────────────────────────────────────
def test_layout_builds_legend_with_twelve_entries():
    ss = _ss()
    t1 = _tr(ss, 1)
    _, _, scene = _build(ss, [_fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
                              _fd(ss, 2, "F1", "outgoing_11kv", 11, tr=t1)], [t1])
    assert scene.legend is not None
    assert len(scene.legend.entries) == 12
    names = {e.name for e in scene.legend.entries}
    assert {"Vacuum Circuit Breaker", "Bus Coupler", "OC/EF TVM", "Earth"} <= names
    assert scene.height == G.Y["legend"] + scene.legend.h + G.LAYOUT["MARGIN"]


def test_render_includes_legend_text():
    ss = _ss()
    t1 = _tr(ss, 1)
    db = FakeDB(substations=[ss],
                feeders=[_fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
                         _fd(ss, 2, "F1", "outgoing_11kv", 11, tr=t1)],
                transformers=[t1])
    svg = SLDGenerator(db).generate(str(ss["_id"]))
    assert "LEGEND" in svg
    assert "Lightning" in svg and "Auto-Recloser" in svg and "Earthing" in svg
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -k "legend" -v`
Expected: FAIL — `scene.legend is None`.

- [ ] **Step 3: Build the legend in `_layout`**

Add near the end of `_layout` (before building the `Scene`):

```python
        legend_entries = [
            LegendEntry("la", "Lightning / Surge Arrester", "Diverts surge energy to earth"),
            LegendEntry("isolator", "Disconnector (Isolator)", "Off-load isolation; hatched = with earth switch"),
            LegendEntry("vcb", "Vacuum Circuit Breaker", "On-load make / break"),
            LegendEntry("ar", "Auto-Recloser", "Self-reclosing breaker on outgoing feeders"),
            LegendEntry("ct", "Current Transformer", "Metering & protection current sensing"),
            LegendEntry("pt", "Voltage (Potential) Transformer", "Bus voltage sensing / metering"),
            LegendEntry("transformer", "Power Transformer", "33/11 kV; HV winding red, LV blue"),
            LegendEntry("station_transformer", "Station Transformer", "33/0.4 kV auxiliary supply"),
            LegendEntry("coupler", "Bus Coupler", "Links two bus sections"),
            LegendEntry("bus", "Busbar", "33 kV red | 11 kV blue"),
            LegendEntry("earth", "Earth", "Earthing connection"),
            LegendEntry("ocef", "OC/EF TVM", "Over-current / earth-fault protection relay"),
        ]
        legend_rows = (len(legend_entries) + 2) // 3
        legend_h = 24 + legend_rows * 22
        legend = LegendBox(x=M, y=Y["legend"], w=width - 2 * M, h=legend_h, entries=legend_entries)
```

Change the `Scene(...)` construction: `legend=legend`, and
`height=Y["legend"] + legend_h + M`.

- [ ] **Step 4: Implement `_render_legend`**

Replace the stub:

```python
    def _render_legend(self, legend):
        cols = 3
        col_w = legend.w // cols
        out = [f'<g transform="translate({legend.x},{legend.y})">',
               f'<rect x="0" y="0" width="{legend.w}" height="{legend.h}" fill="#f8f9fa" stroke="#ccc" rx="4"/>',
               f'<text x="8" y="15" font-size="9" font-weight="700" fill="#1a2744" letter-spacing="1">LEGEND</text>']
        for i, e in enumerate(legend.entries):
            r, c = divmod(i, cols)
            gx = 10 + c * col_w
            gy = 26 + r * 22
            out.append(f'<rect x="{gx}" y="{gy}" width="16" height="12" fill="white" stroke="#888"/>')
            out.append(f'<text x="{gx+22}" y="{gy+6}" font-size="7.5" font-weight="700" fill="#333">{e.name}</text>')
            out.append(f'<text x="{gx+22}" y="{gy+15}" font-size="6.5" fill="#777">{e.description}</text>')
        out.append("</g>")
        return "".join(out)
```

- [ ] **Step 5: Run the full file**

Run: `.venv/bin/python -m pytest tests/test_sld_generator.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add app/services/sld_generator.py tests/test_sld_generator.py
git commit -m "feat: in-SVG symbol legend below the diagram

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: PDF snapshot page

**Files:**
- Modify: `app/services/pdf_generator.py` (docstring; `generate`; topology-summary table)
- Create: `tests/test_pdf_generator.py`
- Modify: dev environment — `svglib` must be importable (it is pinned in `requirements.txt`
  at `1.5.1` but not currently installed in `.venv`).

**Interfaces:**
- Consumes: `SLDGenerator` output shape (a `<svg …>…</svg>` string); `infer_topology` keys
  (Task 1).
- Produces: `PDFReportGenerator(db).generate(substation_id: str, svg_string: str = None) ->
  bytes` — when `svg_string` is a non-empty SVG, page 1 of the returned PDF is a scaled
  raster of that SVG (via `svglib.svg2rlg` + a reportlab `Drawing`), followed by a
  `PageBreak`, followed by the existing cover/tables. When `svg_string` is falsy or
  `svg2rlg` raises/returns `None`, the snapshot page is skipped and the rest of the report
  is unchanged. No exception escapes for a bad SVG.

- [ ] **Step 1: Install svglib into the venv**

Run: `.venv/bin/python -m pip install "svglib==1.5.1"`
Then: `.venv/bin/python -c "from svglib.svglib import svg2rlg; print('ok')"`
Expected: `ok`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_pdf_generator.py`:

```python
"""PDF report — SVG snapshot page happy path + graceful fallback. Fake DB."""
from bson import ObjectId
from app.services.pdf_generator import PDFReportGenerator
from app.models import substation_doc, transformer_doc, feeder_doc


class FakeCursor(list):
    def sort(self, *a, **k): return self


class FakeCollection:
    def __init__(self, docs=None): self.docs = docs or []
    def find_one(self, filt):
        return next((d for d in self.docs
                     if all(d.get(k) == v for k, v in filt.items())), None)
    def find(self, filt):
        return FakeCursor([d for d in self.docs
                           if all(d.get(k) == v for k, v in filt.items())])


class FakeDB:
    def __init__(self, ss, feeders, trs):
        self.substations = FakeCollection([ss])
        self.feeders = FakeCollection(feeders)
        self.transformers = FakeCollection(trs)


def _fixture():
    ss = substation_doc(name="Ulubari", region="LAR", circle="GEC-II", tnc="T", esd="E",
                        gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
                        gss_primary="132kV Sishugram GSS")
    ss["_id"] = ObjectId()
    t1 = transformer_doc(substation_id=ss["_id"], sequence=1, capacity_mva=10,
                         make="BHEL", yom=2015)
    t1["_id"] = ObjectId()
    f1 = feeder_doc(substation_id=ss["_id"], sequence=1, name="Feeder A",
                    voltage_kv=11, feeder_type="outgoing_11kv")
    f1["_id"] = ObjectId()
    return FakeDB(ss, [f1], [t1]), str(ss["_id"])


VALID_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120" '
             'width="200" height="120"><rect width="200" height="120" fill="#fff"/>'
             '<text x="10" y="60" font-size="10">SLD</text></svg>')


def test_generate_with_valid_svg_produces_pdf_bytes():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, VALID_SVG)
    assert isinstance(out, (bytes, bytearray)) and out[:4] == b"%PDF"


def test_generate_with_broken_svg_still_produces_pdf():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, "<svg>not really <valid")
    assert out[:4] == b"%PDF"


def test_generate_with_no_svg_still_produces_pdf():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, None)
    assert out[:4] == b"%PDF"
```

- [ ] **Step 3: Run, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pdf_generator.py -v`
Expected: `test_generate_with_valid_svg_produces_pdf_bytes` FAILS — the current `generate`
returns a PDF but with **no** snapshot page (the test as written only checks `%PDF`, so it
actually passes today). Before writing code, strengthen that test to prove the page exists:
add `assert out.count(b"/Type /Page") >= 3` (cover + 2 table pages today = ≥3; with the
snapshot ≥4) — no, page-count parsing is brittle. Instead assert on a marker only the
snapshot path can produce: after implementing, page 1 is the drawing. Keep the test as the
three `%PDF` smoke checks **plus** this: patch `svg2rlg` to a sentinel and assert it is
called —

```python
def test_valid_svg_is_passed_through_svg2rlg(monkeypatch):
    import app.services.pdf_generator as P
    calls = []
    real = P.svg2rlg
    def spy(arg):
        calls.append(arg)
        return real(arg)
    monkeypatch.setattr(P, "svg2rlg", spy)
    db, sid = _fixture()
    P.PDFReportGenerator(db).generate(sid, VALID_SVG)
    assert len(calls) == 1
```

This test fails now with `AttributeError: module ... has no attribute 'svg2rlg'`.

- [ ] **Step 4: Add the snapshot page**

In `app/services/pdf_generator.py`:

1. Line 2 — change `Pure ReportLab, no svglib.` → `ReportLab + svglib (SVG snapshot page).`
2. Line 51 — change the `generate` docstring `"""svg_string ignored — we generate native
   ReportLab content."""` → `"""Page 1 is a snapshot of `svg_string` (skipped if absent or
   unconvertible); the rest is native ReportLab content."""`
3. After the existing imports (around line 21), add:

```python
try:
    from svglib.svglib import svg2rlg
except Exception:                     # pragma: no cover
    svg2rlg = None
```

4. Add this helper method to `PDFReportGenerator` (e.g. just above `generate`):

```python
    def _svg_snapshot_flowables(self, svg_string, max_w, max_h):
        """Return [Drawing, PageBreak] for the SVG, or [] on any failure."""
        if not svg_string or svg2rlg is None:
            return []
        try:
            drawing = svg2rlg(io.StringIO(svg_string))
            if drawing is None or not drawing.width or not drawing.height:
                return []
            scale = min(max_w / drawing.width, max_h / drawing.height, 1.0)
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            return [drawing, PageBreak()]
        except Exception:
            return []
```

   `io` is already imported (line 17); `PageBreak` is already imported (the `from
   reportlab.platypus import (...)` block includes it).

5. At line 89 the flowable list is created as `story = []`. Immediately **after** line 90
   (`usable_w = page_w - 32*mm`), insert:

```python
        story += self._svg_snapshot_flowables(svg_string, page_w - 30*mm, page_h - 30*mm)
```

   (`page_w`, `page_h` are already bound at line 62. This puts the snapshot before the
   cover content that starts at line 93.)

6. Lines 133-138 — the `topo_data` rows reference `topo.get("has_bus_coupler")` and the old
   counts. Replace those three rows with:

```python
            ["Bus Configuration", bus_config,
             "11 kV Sections", _s(topo.get("num_11kv_sections"))],
            ["33 kV Bus Coupler", "Yes" if topo.get("has_33kv_bus_coupler") else "No",
             "11 kV Bus Coupler", "Yes" if topo.get("has_11kv_bus_coupler") else "No"],
            ["Station Transformer", "Yes" if topo.get("has_station_transformer") else "No",
             "11 kV Outgoing Feeders", _s(topo.get("outgoing_11kv_count"))],
```

   (Same 4-column shape as the existing rows — `Table(topo_data, colWidths=...)` at line 140
   is unchanged.)

- [ ] **Step 5: Run, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pdf_generator.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Confirm the route still works end-to-end (smoke)**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (all suites; importer integration tests may `skip`).

- [ ] **Step 7: Commit**

```bash
git add app/services/pdf_generator.py tests/test_pdf_generator.py
git commit -m "feat: embed the SLD SVG as page 1 of the PDF report

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Frontend — feeder-type labels, edit select, topology panel

**Files:**
- Modify: `app/templates/sld/index.html` (the `typeLabel` map; the `#edit-feeder-type`
  `<select>`; the `#topo-info` template literal)

**Interfaces:**
- Consumes: the API `/api/v1/substations/<id>` response — `feeder.feeder_type` values now
  include `outgoing_33kv` and `station_transformer` (never `lilo_33kv`); `substation.topology`
  now has the Task 1 keys.
- Produces: no JS API surface; visual only. Verified by manual check.

- [ ] **Step 1: Update the `typeLabel` map**

In the `<script>` block, in `loadSubstationInfo`, the `typeLabel` object: replace the
`lilo_33kv:` line with:

```javascript
      outgoing_33kv: '<span class="badge badge-33">33kV OUT</span>',
```

(keep the `station_transformer:` line as-is).

- [ ] **Step 2: Update the edit `<select>`**

In the feeder-edit modal, `<select id="edit-feeder-type">`: change
`<option value="lilo_33kv">33kV LILO</option>` to
`<option value="outgoing_33kv">33kV Outgoing</option>`.

- [ ] **Step 3: Update the topology panel**

In `loadSubstationInfo`, the `document.getElementById('topo-info').innerHTML = ...` template
literal: replace the "Bus Coupler" and "33kV LILO Taps" rows with:

```html
      <span style="color:var(--text-sub)">11 kV Sections</span><span>${topo.num_11kv_sections||0}</span>
      <span style="color:var(--text-sub)">11 kV Bus Coupler</span><span>${topo.has_11kv_bus_coupler ? '✅ Yes' : 'No'}</span>
      <span style="color:var(--text-sub)">33 kV Bus Coupler</span><span>${topo.has_33kv_bus_coupler ? '✅ Yes' : 'No'}</span>
      <span style="color:var(--text-sub)">33 kV O/g Feeders</span><span style="color:var(--accent33);font-weight:600">${topo.outgoing_33kv_count||0}</span>
```

Leave the `num_transformers` and `incoming_33kv_count` rows unchanged; keep the
`bus_config` badge row (it now shows e.g. `sectionalized both`).

- [ ] **Step 4: Manual verification**

Start the app (`.venv/bin/python run.py`), open a substation SLD page. Confirm:
the SLD image shows the new title block + legend; the topology panel shows the new rows with
no `undefined`; opening the feeder-edit modal shows "33kV Outgoing" in the type dropdown.
(If no DB data is available, at minimum confirm the page renders without a JS console error.)

- [ ] **Step 5: Commit**

```bash
git add app/templates/sld/index.html
git commit -m "feat: SLD page — 33kV outgoing feeder type + section-aware topology panel

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: Full-suite verification + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md` (Architecture section — the SLD generator description)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS. Importer integration tests that need `~/Downloads/GEC - I substation master
data compiled.xlsx` may `SKIP` — that is acceptable. No `FAIL`, no `ERROR`.

- [ ] **Step 2: Grep the whole repo for retired identifiers**

Run: `grep -rn "lilo\|_render_single_bus\|_render_double_bus\|bus_config.*double_bus\|has_bus_coupler" app/ tests/`
Expected: no matches (the only `lilo` allowed is the unrelated substation text field
`lilo_info` in `models.py`, `import_schema.py`, `importer.py`, `pdf_generator.py`, and the
`substations.py` allow-list — verify each remaining hit is `lilo_info`, not `lilo_33kv`).

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, in the **Services** list, replace the `sld_generator.py` bullet with:

```markdown
- `sld_generator.py` (`SLDGenerator`) — two pure phases: `_layout(ss, feeders, transformers)`
  builds a `Scene` of dataclasses (33 kV bus with optional 33 kV coupler, ordered 33 kV bays,
  one 11 kV `Section` per transformer, data-driven 11 kV couplers, legend); `_render(scene)`
  walks it emitting SVG via stateless `sym_*` helpers. `_layout` is unit-tested with the
  in-memory `FakeDB`. Rating constants in the module-level `RATINGS` dict. Colours: 33 kV
  `#CC2200`, 11 kV `#0055CC`, bus `#111111`, earth `#006600`.
```

Also update the topology sentence: `infer_topology()` now returns `bus_config` ∈
`{single_bus, sectionalized_11kv, sectionalized_33kv, sectionalized_both}` plus
section/coupler counts.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — unified SLD layout engine

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes (for the executor — informational)

- **Spec coverage:** §1.1 feeder types → T1/T2; §1.2 importer → T2; §1.4 infer_topology →
  T1; §2 layout engine → T4-T9; §3.1 symbols → T3; §3.2 RATINGS → T3/T4; §3.3 title → T8;
  §3.4 legend → T9; §3.5 remove table → T8; §4 PDF → T10; §5.1 frontend → T11; §5.2 tests →
  every task; §5.3 template notes → T2.
- **Geometry constants** (`Y`, `LAYOUT`) are first-draft values; the executor may tune the
  pixel numbers so bays don't visually overlap, as long as the asserted *relationships*
  (`Y["tr_bot"] < Y["bus11"]`, contiguous bus segments, legend below everything) hold.
- **`pdf_generator.generate` internals**: the plan assumes a `story`/`elements` flowable
  list built before `doc.build(...)`. Read lines 50-140 first and bind to the real variable
  name; the snapshot flowables must be prepended, not appended.
- **svglib fidelity risk** (spec §7): if `svg2rlg` chokes on the real generated SVG (not the
  toy test SVG), the fallback returns `[]` and the report still builds — acceptable for this
  plan; a follow-up can raster via a headless renderer if higher fidelity is needed.
