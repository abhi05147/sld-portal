# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements-dev.txt        # runtime deps + pytest
python run.py                              # dev server on :5000 (debug)
pytest                                     # run all tests
pytest tests/test_sld_generator.py -k lilo # single file / single test

# create initial admin (needs FLASK_APP=run.py and a live MONGO_URI)
flask seed-admin <username> <email> <password>
```

Requires `.env` with `MONGO_URI` and `JWT_SECRET_KEY` (see `.env.example`). Python 3.11.

Unit tests for `sld_generator` and `importer` use in-memory fakes (see `FakeDB` in `tests/test_sld_generator.py`) — no MongoDB needed. `tests/test_importer.py` references a local sample `.xlsx` path that may be absent.

## Architecture

Flask + PyMongo app that turns tabular substation data into IEC 60617 single-line diagrams and PDF reports. No ORM — documents are plain dicts built by factory functions in `app/models.py`.

**Request flow:** `run.py` → `app/__init__.py:create_app()` wires extensions (`mongo`, `jwt`, `bcrypt`), registers blueprints under `/api/v1/*`, and creates Mongo indexes on startup. `views_bp` (no prefix) serves Jinja pages; all `/api/v1/*` blueprints return JSON/SVG/PDF and are guarded by `@jwt_required()` + a `get_jwt()["role"]` check (`admin` > `engineer` > `viewer`).

**Data model** (`app/models.py`): collections `grid_substations`, `substations`, `transformers`, `feeders`, `users`, `audit_logs`. A substation owns transformers and feeders by `substation_id`. `feeder_type` is the key discriminator: `incoming_33kv` | `outgoing_33kv` | `transformer_hv` | `station_transformer` | `incomer_11kv` | `outgoing_11kv` | `bus_coupler`.

**Topology is derived, never stored by hand.** `infer_topology(feeders)` computes `bus_config` ∈ `{single_bus, sectionalized_11kv, sectionalized_33kv, sectionalized_both}` plus section/coupler counts (`num_11kv_sections`, `has_11kv_bus_coupler`, `has_33kv_bus_coupler`, `has_station_transformer`, `outgoing_33kv_count`). Call `refresh_substation_topology()` (`app/routes/helpers.py`) after any feeder mutation so the stored `substation.topology` stays in sync. The SLD and PDF generators branch on `bus_config`.

**Services** (`app/services/`):
- `import_schema.py` — the canonical ordered `FIELD_HEADERS` (52 columns) + `REQUIRED_FIELDS`. Single source of truth shared by importer and template generator; changing the Excel layout means editing only this file.
- `importer.py` (`ExcelImporter`) — header-driven: matches header text to fields order-independently, one row per feeder with substation/transformer details repeated on the block's first row. Re-importing a substation **overwrites** its records.
- `template_generator.py` — writes `FIELD_HEADERS` + one sample row into a downloadable `.xlsx`.
- `sld_generator.py` (`SLDGenerator`) — two pure phases: `_layout(ss, feeders, transformers)`
  builds a `Scene` of dataclasses (33 kV bus with optional 33 kV coupler, ordered 33 kV bays,
  one 11 kV `Section` per transformer, data-driven 11 kV couplers, legend); `_render(scene)`
  walks it emitting SVG via stateless `sym_*` helpers. `_layout` is unit-tested with the
  in-memory `FakeDB`. Rating constants in the module-level `RATINGS` dict. Colours: 33 kV
  `#CC2200`, 11 kV `#0055CC`, bus `#111111`, earth `#006600`.
- `pdf_generator.py` (`PDFReportGenerator`) — pure ReportLab multi-page report; receives the already-rendered SVG string.

**Frontend:** server-rendered Jinja templates in `app/templates/` + vanilla JS; `static/` holds no local assets (Leaflet etc. via CDN).

## Deployment

Render.com (`render.yaml`): `gunicorn run:app`. Setting `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars makes `run.py:_auto_seed()` create an admin on boot.
