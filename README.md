# APDCL SLD Portal

Web application for displaying IEC-compliant Single Line Diagrams (SLDs) of 33/11 kV electrical substations, built with Flask, MongoDB Atlas, and SVG-based IEC 60617 symbols.

---

## Features

- **Dynamic SVG SLDs** — IEC 60617 symbols, generated from database; handles single-bus, double-bus, and double-bus-with-coupler topologies
- **Dashboard** — aggregated stats (transformers, feeders, capacity), Leaflet.js map with substation pins, GSS hierarchy tree
- **Excel Import** — parse GECII feeder status Excel (multi-header, multi-sheet); topology auto-inferred from feeder data
- **PDF Report** — full report: SLD + transformer table + feeder/switchgear details
- **Role-based Auth** — Admin / Engineer / Viewer, JWT + bcrypt
- **Light & Dark theme** — Rajdhani font throughout
- **Cloud-ready** — Render.com deployment config included

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3.0, Flask-JWT-Extended, Flask-Bcrypt |
| Database | MongoDB Atlas (PyMongo) |
| Frontend | Jinja2 + vanilla JS + Leaflet.js |
| SLD Engine | Custom SVG generator (IEC 60617) |
| PDF | ReportLab + svglib |
| Excel Parsing | pandas + openpyxl |
| Deployment | Render.com + Gunicorn |

---

## Local Setup

### 1. Clone and install

```bash
git clone <your-repo>
cd sld_app
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set:
#   MONGO_URI  = your MongoDB Atlas connection string
#   JWT_SECRET_KEY = any long random string (min 32 chars)
```

### 3. MongoDB Atlas setup

1. Create a free M0 cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a database user (username + password)
3. Whitelist your IP (or `0.0.0.0/0` for development)
4. Copy the connection string → paste into `MONGO_URI` in `.env`
   - Format: `mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/sld_db?retryWrites=true&w=majority`

### 4. Create admin user

```bash
export FLASK_APP=run.py
flask seed-admin admin admin@yourorg.com yourpassword
```

### 5. Run

```bash
python run.py
# Visit http://localhost:5000
```

---

## Import Excel Data

1. Log in as **Admin** or **Engineer**
2. Navigate to **Upload Data** (top nav)
3. Drop your GECII Feeder Status `.xlsx` file
4. Click **Upload & Import**

**Expected format:** The standard GECII Excel with 3-row merged headers and data from row 4.
- Multiple sheets supported
- Re-uploading for an existing substation **overwrites** its records

---

## User Roles

| Role | Capabilities |
|---|---|
| **Admin** | Create/disable/reset users, upload data, view all |
| **Engineer** | Upload Excel, add/edit entries, view all |
| **Viewer** | View dashboard, SLDs, download PDFs |

---

## SLD Topologies Supported

| Config | Trigger |
|---|---|
| Single bus | 1 transformer, no bus coupler |
| Double bus | 2+ transformers |
| Double bus + coupler | 2+ transformers + `bus_coupler` feeder type detected |
| Ring main / alternate | Multiple 33 kV incomers |

The topology is **automatically inferred** from the feeder list on import.

---

## API Reference

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Public | Login |
| POST | `/api/v1/auth/register` | Admin | Create user |
| GET  | `/api/v1/dashboard/stats` | Any | Aggregated stats |
| GET  | `/api/v1/dashboard/hierarchy` | Any | GSS→SS→Feeder tree |
| GET  | `/api/v1/substations/` | Any | List substations |
| GET  | `/api/v1/substations/<id>` | Any | Full substation detail |
| POST | `/api/v1/substations/` | Eng+ | Create substation |
| GET  | `/api/v1/sld/<id>` | Any | SVG SLD |
| GET  | `/api/v1/sld/<id>/pdf` | Any | PDF report download |
| POST | `/api/v1/upload/excel` | Eng+ | Import Excel/CSV |
| GET  | `/api/v1/users/` | Admin | List users |
| PATCH| `/api/v1/users/<id>` | Admin | Enable/disable/change role |
| POST | `/api/v1/users/<id>/reset-password` | Admin | Reset user password |

---

## Cloud Deployment (Render.com)

1. Push to GitHub
2. New Web Service on Render → connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 120`
5. Add environment variables:
   - `MONGO_URI` — your Atlas URI
   - `JWT_SECRET_KEY` — Render can auto-generate
   - `FLASK_ENV=production`
6. Deploy → visit your `.onrender.com` URL
7. SSH into Render shell and run: `flask seed-admin admin admin@org.com pass`

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `grid_substations` | 132/33 kV GSS source nodes |
| `substations` | 33/11 kV substation master records |
| `transformers` | Per-transformer records |
| `feeders` | All feeder rows (incoming 33kV, 11kV incomer, outgoing, bus coupler) |
| `users` | Auth records (bcrypt hashed passwords) |
| `audit_logs` | All login, upload, and change events |

---

## IEC 60617 Symbol Key

| Symbol | IEC Ref | Used For |
|---|---|---|
| Lightning Arrester | LA | 33kV incoming, transformer HV side |
| Disconnector (Isolator) | — | All voltage levels; with/without earth switch |
| Circuit Breaker (VCB) | — | 33kV and 11kV VCBs |
| Autorecloser | — | Where detected from data |
| Current Transformer | CT | All metered feeders |
| Voltage Transformer | PT/VT | Bus PTs |
| Power Transformer | — | Two interlocked circles (HV red, LV blue) |
| Earth symbol | — | All earth connections (green) |
| Busbar | — | 33kV (thick black) and 11kV (blue) |

**Colour scheme:** 33kV = `#CC2200` (red) | 11kV = `#0055CC` (blue) | Earth = `#006600` (green)
