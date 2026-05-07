"""
SVG Single-Line Diagram Generator — IEC 60617 compliant symbols.

Layout engine:
  - Reads substation topology + feeders from DB
  - Places IEC symbols on a grid
  - Outputs a self-contained SVG string

Colour scheme (IEC practice):
  33kV : #CC2200  (red)
  11kV : #0055CC  (blue)
  Bus  : #111111  (black)
  Earth: #006600  (green)
  Equip: #333333  (dark grey)
"""
from bson import ObjectId


# ── IEC SVG Symbol Library ───────────────────────────────────────────────────

def sym_lightning_arrester(x, y, color="#CC2200"):
    """IEC 60617-3: Lightning arrester — triangle pointing down + earth line."""
    return f"""
  <g class="sym-la" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="-8" stroke="{color}" stroke-width="2"/>
    <polygon points="0,-8 -7,8 7,8" fill="none" stroke="{color}" stroke-width="1.8"/>
    <line x1="0" y1="8" x2="0" y2="18" stroke="{color}" stroke-width="2"/>
    <line x1="-6" y1="18" x2="6" y2="18" stroke="#006600" stroke-width="2"/>
    <line x1="-4" y1="21" x2="4" y2="21" stroke="#006600" stroke-width="1.5"/>
    <line x1="-2" y1="24" x2="2" y2="24" stroke="#006600" stroke-width="1"/>
  </g>"""


def sym_isolator(x, y, has_earth=False, color="#CC2200"):
    """IEC 60617: Disconnector (isolator) — open contact symbol."""
    earth = ""
    if has_earth:
        earth = f"""
    <line x1="5" y1="5" x2="5" y2="15" stroke="#006600" stroke-width="1.8"/>
    <line x1="-1" y1="15" x2="11" y2="15" stroke="#006600" stroke-width="1.8"/>
    <line x1="1" y1="18" x2="9" y2="18" stroke="#006600" stroke-width="1.3"/>
    <line x1="3" y1="21" x2="7" y2="21" stroke="#006600" stroke-width="1"/>"""
    return f"""
  <g class="sym-iso" transform="translate({x},{y})">
    <line x1="0" y1="-15" x2="0" y2="-5" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="-5" r="2" fill="{color}"/>
    <line x1="0" y1="-5" x2="10" y2="5" stroke="{color}" stroke-width="1.8"/>
    <circle cx="10" cy="5" r="2" fill="none" stroke="{color}" stroke-width="1.5"/>
    <line x1="10" y1="5" x2="10" y2="15" stroke="{color}" stroke-width="2"/>{earth}
  </g>"""


def sym_vcb(x, y, label="VCB", color="#CC2200"):
    """IEC 60617: Circuit breaker — square with diagonal cross."""
    return f"""
  <g class="sym-vcb" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <rect x="-10" y="-10" width="20" height="20" fill="white" stroke="{color}" stroke-width="2"/>
    <line x1="-8" y1="-8" x2="8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="8" y1="-8" x2="-8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="0" y1="10" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
    <text x="14" y="5" font-family="Rajdhani,sans-serif" font-size="9" fill="#333">{label}</text>
  </g>"""


def sym_autorecloser(x, y, color="#CC2200"):
    """Autorecloser — circle with A label."""
    return f"""
  <g class="sym-ar" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="-12" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="0" r="12" fill="white" stroke="{color}" stroke-width="2"/>
    <text x="0" y="5" text-anchor="middle" font-family="Rajdhani,sans-serif"
          font-size="12" font-weight="700" fill="{color}">A</text>
    <line x1="0" y1="12" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
  </g>"""


def sym_ct(x, y, label="CT", color="#333333"):
    """IEC 60617: Current transformer — oval on line with label."""
    return f"""
  <g class="sym-ct" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
    <ellipse cx="0" cy="0" rx="10" ry="6" fill="white" stroke="{color}" stroke-width="1.8"/>
    <text x="14" y="4" font-family="Rajdhani,sans-serif" font-size="8" fill="#555">{label}</text>
  </g>"""


def sym_bus_pt(x, y, label="PT", color="#333333"):
    """Bus PT / VT — wound symbol."""
    return f"""
  <g class="sym-pt" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="-4" r="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    <circle cx="0" cy="4" r="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    <line x1="0" y1="11" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
    <line x1="0" y1="20" x2="0" y2="26" stroke="#006600" stroke-width="1.8"/>
    <line x1="-5" y1="26" x2="5" y2="26" stroke="#006600" stroke-width="1.8"/>
    <line x1="-3" y1="29" x2="3" y2="29" stroke="#006600" stroke-width="1.3"/>
    <text x="12" y="4" font-family="Rajdhani,sans-serif" font-size="8" fill="#555">{label}</text>
  </g>"""


def sym_transformer(x, y, label="10MVA\n33/11kV", color_hv="#CC2200", color_lv="#0055CC"):
    """IEC 60617: Power transformer — two interlocked circles."""
    lines = label.split("\\n")
    text_els = "".join(
        f'<tspan x="{x + 50}" dy="{14 if i else 0}" font-size="10">{ln}</tspan>'
        for i, ln in enumerate(lines)
    )
    return f"""
  <g class="sym-tr" transform="translate({x},{y})">
    <line x1="0" y1="-30" x2="0" y2="-18" stroke="{color_hv}" stroke-width="2.5"/>
    <circle cx="0" cy="-6" r="13" fill="white" stroke="{color_hv}" stroke-width="2.2"/>
    <circle cx="0" cy="8" r="13" fill="white" stroke="{color_lv}" stroke-width="2.2"/>
    <line x1="0" y1="21" x2="0" y2="30" stroke="{color_lv}" stroke-width="2.5"/>
    <line x1="-6" y1="36" x2="6" y2="36" stroke="#006600" stroke-width="2"/>
    <line x1="-4" y1="39" x2="4" y2="39" stroke="#006600" stroke-width="1.5"/>
    <line x1="-2" y1="42" x2="2" y2="42" stroke="#006600" stroke-width="1"/>
    <line x1="0" y1="30" x2="0" y2="36" stroke="#006600" stroke-width="2"/>
    <text font-family="Rajdhani,sans-serif" font-weight="600" fill="#333333">
      {text_els}
    </text>
  </g>"""


def sym_earth(x, y, color="#006600"):
    return f"""
  <g class="sym-earth" transform="translate({x},{y})">
    <line x1="0" y1="-8" x2="0" y2="0" stroke="{color}" stroke-width="2"/>
    <line x1="-8" y1="0" x2="8" y2="0" stroke="{color}" stroke-width="2"/>
    <line x1="-5" y1="4" x2="5" y2="4" stroke="{color}" stroke-width="1.5"/>
    <line x1="-2" y1="8" x2="2" y2="8" stroke="{color}" stroke-width="1"/>
  </g>"""


def sym_feeder_arrow(x, y, name, voltage_kv=11):
    """Outgoing feeder terminal with arrow and label."""
    color = "#0055CC" if voltage_kv == 11 else "#CC2200"
    return f"""
  <g class="sym-feeder-out" transform="translate({x},{y})">
    <line x1="0" y1="0" x2="0" y2="30" stroke="{color}" stroke-width="2"/>
    <polygon points="0,38 -6,26 6,26" fill="{color}"/>
    <text x="10" y="20" font-family="Rajdhani,sans-serif" font-size="10"
          fill="{color}" font-weight="600">{name}</text>
  </g>"""


def sym_busbar(x1, y, x2, label="", color="#111111"):
    """Horizontal busbar."""
    lbl = f'<text x="{x1}" y="{y - 6}" font-family="Rajdhani,sans-serif" font-size="9" fill="#555">{label}</text>' if label else ""
    return f"""
  <g class="sym-bus">
    {lbl}
    <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="5" stroke-linecap="round"/>
  </g>"""


def sym_bus_coupler(x, y, color="#333333"):
    """Bus coupler VCB between two buses."""
    return f"""
  <g class="sym-bc" transform="translate({x},{y})">
    <line x1="0" y1="-15" x2="0" y2="-8" stroke="{color}" stroke-width="2"/>
    <rect x="-8" y="-8" width="16" height="16" fill="white" stroke="{color}" stroke-width="2"/>
    <line x1="-6" y1="-6" x2="6" y2="6" stroke="{color}" stroke-width="1.5"/>
    <line x1="6" y1="-6" x2="-6" y2="6" stroke="{color}" stroke-width="1.5"/>
    <line x1="0" y1="8" x2="0" y2="15" stroke="{color}" stroke-width="2"/>
    <text x="12" y="4" font-family="Rajdhani,sans-serif" font-size="8" fill="#555">BC</text>
  </g>"""


# ── SLD Layout Engine ─────────────────────────────────────────────────────────

class SLDGenerator:
    def __init__(self, db):
        self.db = db

    def generate(self, substation_id: str) -> str:
        """Return complete SVG string for the given substation."""
        ss = self.db.substations.find_one({"_id": ObjectId(substation_id)})
        if not ss:
            return self._error_svg("Substation not found")

        feeders = list(
            self.db.feeders.find({"substation_id": ObjectId(substation_id)}).sort("sequence", 1)
        )
        transformers = list(
            self.db.transformers.find({"substation_id": ObjectId(substation_id)}).sort("sequence", 1)
        )

        topo = ss.get("topology", {})
        bus_config = topo.get("bus_config", "single_bus")

        if bus_config in ("double_bus_coupler", "double_bus"):
            return self._render_double_bus(ss, feeders, transformers, topo)
        else:
            return self._render_single_bus(ss, feeders, transformers, topo)

    # ── Single Bus Layout ─────────────────────────────────────────────────────

    def _render_single_bus(self, ss, feeders, transformers, topo):
        outgoing = [f for f in feeders if f["feeder_type"] == "outgoing_11kv"]
        incoming_33 = [f for f in feeders if f["feeder_type"] == "incoming_33kv"]
        num_out = max(len(outgoing), 1)
        num_tr = max(len(transformers), 1)

        col_w = 120
        total_w = max(800, (num_out + num_tr + 1) * col_w + 100)
        total_h = 700
        cx = total_w // 2

        svg_parts = [self._svg_header(ss, total_w, total_h)]

        # 33kV Incoming section (top)
        svg_parts.append(f'<text x="{cx}" y="28" text-anchor="middle" class="section-label-33">33 kV INCOMING</text>')
        in_feeder = incoming_33[0] if incoming_33 else None
        in_name = in_feeder["name"] if in_feeder else "33 kV INCOMER"
        svg_parts.append(f'<text x="{cx}" y="52" text-anchor="middle" class="feeder-label-33">{in_name}</text>')

        # Incoming cable
        svg_parts.append(f'<line x1="{cx}" y1="55" x2="{cx}" y2="80" stroke="#CC2200" stroke-width="2.5"/>')
        # LA
        svg_parts.append(sym_lightning_arrester(cx - 40, 95))
        svg_parts.append(f'<line x1="{cx}" y1="80" x2="{cx}" y2="95" stroke="#CC2200" stroke-width="2.5"/>')
        # 33kV Isolator with ES
        svg_parts.append(sym_isolator(cx, 115, has_earth=True))
        # 33kV VCB
        svg_parts.append(sym_vcb(cx, 165, label="33kV VCB"))
        # CT
        svg_parts.append(sym_ct(cx, 210, label="33kV CT"))
        # Bus PT tap
        svg_parts.append(sym_bus_pt(cx + 40, 230, label="Bus PT"))

        # 33kV Bus
        bus_y = 250
        svg_parts.append(sym_busbar(50, bus_y, total_w - 50, label="33 kV BUS"))
        svg_parts.append(f'<line x1="{cx}" y1="230" x2="{cx}" y2="{bus_y}" stroke="#CC2200" stroke-width="2.5"/>')

        # Transformers
        tr_spacing = col_w
        tr_start_x = cx - ((num_tr - 1) * tr_spacing) // 2
        tr_positions = []

        for i, tr in enumerate(transformers):
            tx = tr_start_x + i * tr_spacing
            cap = tr.get("capacity_mva", "?")
            lbl = f'{cap}MVA\n33/11kV'
            svg_parts.append(f'<line x1="{tx}" y1="{bus_y}" x2="{tx}" y2="{bus_y + 20}" stroke="#CC2200" stroke-width="2.5"/>')
            # HV Isolator
            svg_parts.append(sym_isolator(tx, bus_y + 35, has_earth=True))
            # Transformer
            svg_parts.append(sym_transformer(tx, bus_y + 75, label=lbl))
            tr_positions.append(tx)

        # 11kV Bus
        bus_11_y = bus_y + 180
        svg_parts.append(sym_busbar(50, bus_11_y, total_w - 50, label="11 kV BUS", color="#0055CC"))

        # Connect transformers to 11kV bus
        for tx in tr_positions:
            svg_parts.append(f'<line x1="{tx}" y1="{bus_y + 145}" x2="{tx}" y2="{bus_11_y}" stroke="#0055CC" stroke-width="2.5"/>')
            svg_parts.append(sym_vcb(tx, bus_y + 155, label="11kV VCB", color="#0055CC"))

        # 11kV Bus PT
        svg_parts.append(sym_bus_pt(50, bus_11_y - 15, label="11kV Bus PT", color="#333333"))

        # Outgoing 11kV feeders
        out_spacing = max(col_w, (total_w - 100) // max(num_out, 1))
        out_start_x = 80 + out_spacing // 2
        svg_parts.append(f'<text x="{cx}" y="{bus_11_y + 16}" text-anchor="middle" class="section-label-11">11 kV OUTGOING FEEDERS</text>')

        for i, fd in enumerate(outgoing):
            fx = out_start_x + i * out_spacing
            svg_parts.append(f'<line x1="{fx}" y1="{bus_11_y}" x2="{fx}" y2="{bus_11_y + 20}" stroke="#0055CC" stroke-width="2"/>')
            svg_parts.append(sym_isolator(fx, bus_11_y + 35, has_earth=True, color="#0055CC"))
            svg_parts.append(sym_vcb(fx, bus_11_y + 70, label="VCB", color="#0055CC"))
            svg_parts.append(sym_ct(fx, bus_11_y + 110, label="CT", color="#333333"))
            svg_parts.append(sym_feeder_arrow(fx, bus_11_y + 140, fd["name"][:20], voltage_kv=11))

        svg_parts.append(self._equipment_table(ss, feeders, transformers, total_w, bus_11_y + 220))
        svg_parts.append("</svg>")
        return "".join(svg_parts)

    # ── Double Bus with Coupler Layout ────────────────────────────────────────

    def _render_double_bus(self, ss, feeders, transformers, topo):
        outgoing = [f for f in feeders if f["feeder_type"] == "outgoing_11kv"]
        incoming_33 = [f for f in feeders if f["feeder_type"] == "incoming_33kv"]
        num_out = max(len(outgoing), 1)
        num_tr = len(transformers)

        total_w = max(900, num_out * 110 + 200)
        total_h = 820
        cx = total_w // 2

        svg_parts = [self._svg_header(ss, total_w, total_h)]

        # 33kV incoming
        for i, inc in enumerate(incoming_33[:2]):
            ix = cx - 80 + i * 160
            svg_parts.append(f'<text x="{ix}" y="28" text-anchor="middle" class="feeder-label-33">{inc["name"][:22]}</text>')
            svg_parts.append(f'<line x1="{ix}" y1="32" x2="{ix}" y2="55" stroke="#CC2200" stroke-width="2.5"/>')
            svg_parts.append(sym_lightning_arrester(ix - 35, 70))
            svg_parts.append(sym_isolator(ix, 90, has_earth=True))
            svg_parts.append(sym_vcb(ix, 140, label="VCB"))
            svg_parts.append(sym_ct(ix, 185))

        # 33kV Bus
        bus_y = 210
        svg_parts.append(sym_busbar(50, bus_y, total_w - 50, label="33 kV BUS"))
        for i in range(min(2, len(incoming_33))):
            ix = cx - 80 + i * 160
            svg_parts.append(f'<line x1="{ix}" y1="205" x2="{ix}" y2="{bus_y}" stroke="#CC2200" stroke-width="2.5"/>')

        # Two transformers
        tr_x = [cx - 100, cx + 100]
        for i, tr in enumerate(transformers[:2]):
            tx = tr_x[i]
            cap = tr.get("capacity_mva", "?")
            svg_parts.append(f'<line x1="{tx}" y1="{bus_y}" x2="{tx}" y2="{bus_y + 18}" stroke="#CC2200" stroke-width="2.5"/>')
            svg_parts.append(sym_isolator(tx, bus_y + 32, has_earth=True))
            svg_parts.append(sym_transformer(tx, bus_y + 72, label=f"{cap}MVA\n33/11kV"))

        # 11kV Double Bus
        bus11a_y = bus_y + 180
        bus11b_y = bus_y + 205
        svg_parts.append(sym_busbar(50, bus11a_y, cx - 10, label="11kV BUS-1", color="#0055CC"))
        svg_parts.append(sym_busbar(cx + 10, bus11b_y, total_w - 50, label="11kV BUS-2", color="#0055CC"))
        # Bus coupler
        svg_parts.append(sym_bus_coupler(cx, (bus11a_y + bus11b_y) // 2))

        for i, tr in enumerate(transformers[:2]):
            tx = tr_x[i]
            svg_parts.append(f'<line x1="{tx}" y1="{bus_y + 145}" x2="{tx}" y2="{bus11a_y if i == 0 else bus11b_y}" stroke="#0055CC" stroke-width="2.5"/>')
            svg_parts.append(sym_vcb(tx, bus_y + 160, label="11kV VCB", color="#0055CC"))

        # Outgoing feeders
        out_bus_y = bus11b_y + 10
        out_spacing = max(100, (total_w - 100) // max(num_out, 1))
        out_start = 60 + out_spacing // 2

        svg_parts.append(f'<text x="{cx}" y="{out_bus_y + 18}" text-anchor="middle" class="section-label-11">11 kV OUTGOING FEEDERS</text>')
        for i, fd in enumerate(outgoing):
            fx = out_start + i * out_spacing
            bus_ref_y = bus11a_y if i < num_out // 2 else bus11b_y
            svg_parts.append(f'<line x1="{fx}" y1="{bus_ref_y}" x2="{fx}" y2="{out_bus_y + 25}" stroke="#0055CC" stroke-width="2"/>')
            svg_parts.append(sym_isolator(fx, out_bus_y + 40, has_earth=True, color="#0055CC"))
            svg_parts.append(sym_vcb(fx, out_bus_y + 76, label="VCB", color="#0055CC"))
            svg_parts.append(sym_ct(fx, out_bus_y + 115, color="#333"))
            svg_parts.append(sym_feeder_arrow(fx, out_bus_y + 145, fd["name"][:18]))

        svg_parts.append(self._equipment_table(ss, feeders, transformers, total_w, out_bus_y + 225))
        svg_parts.append("</svg>")
        return "".join(svg_parts)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _svg_header(self, ss, w, h):
        name = ss.get("name", "Substation")
        gss = ss.get("gss_primary", "")
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"
     width="{w}" height="{h}" id="sld-svg"
     font-family="Rajdhani,sans-serif">
  <defs>
    <style>
      .section-label-33 {{ font-size:12px; font-weight:700; fill:#CC2200; letter-spacing:1px; }}
      .section-label-11 {{ font-size:12px; font-weight:700; fill:#0055CC; letter-spacing:1px; }}
      .feeder-label-33  {{ font-size:10px; fill:#CC2200; }}
      .feeder-label-11  {{ font-size:10px; fill:#0055CC; }}
      .tbl-head {{ font-size:9px; font-weight:700; fill:white; }}
      .tbl-cell {{ font-size:8px; fill:#333; }}
    </style>
  </defs>
  <!-- Border -->
  <rect x="1" y="1" width="{w-2}" height="{h-2}" fill="white" stroke="#ccc" stroke-width="1" rx="4"/>
  <!-- Title block -->
  <rect x="1" y="1" width="{w-2}" height="18" fill="#1a2744" rx="4"/>
  <text x="{w//2}" y="13" text-anchor="middle"
        font-family="Rajdhani,sans-serif" font-size="11" font-weight="700" fill="white" letter-spacing="1">
    SINGLE LINE DIAGRAM — 33/11 kV {name.upper()} | SOURCE: {gss}
  </text>
"""

    def _equipment_table(self, ss, feeders, transformers, width, y_start):
        """Equipment summary table at bottom of SLD."""
        rows = []
        for tr in transformers:
            rows.append((
                f"Power Transformer {tr['sequence']}",
                f"{tr.get('capacity_mva', '-')} MVA",
                tr.get("make", "-"),
                str(tr.get("yom", "-")),
                f"Max Load: {tr.get('max_loading_mw', '-')} MW",
            ))
        for fd in feeders:
            if fd["feeder_type"] not in ("outgoing_11kv", "incoming_33kv"):
                continue
            sg = fd.get("switchgear", {})
            mt = fd.get("meter", {})
            rows.append((
                fd["name"][:25],
                f"{fd['voltage_kv']} kV",
                sg.get("vcb_make", "-") or "-",
                str(sg.get("year_commissioned", "-") or "-"),
                f"Meter: {mt.get('number', '-') or '-'} | CTR: {mt.get('ctr', '-') or '-'}",
            ))

        row_h = 14
        tbl_h = len(rows) * row_h + 20
        cols = [0, 180, 250, 310, 370, width - 20]
        headers = ["Equipment", "Rating", "Make", "YOM", "Meter / Notes"]

        parts = [f'<g transform="translate(20,{y_start})">']
        parts.append(f'<rect x="0" y="0" width="{width - 40}" height="{tbl_h}" fill="#f8f9fa" stroke="#ddd" rx="3"/>')
        parts.append(f'<rect x="0" y="0" width="{width - 40}" height="16" fill="#1a2744" rx="3"/>')

        for i, h in enumerate(headers):
            parts.append(f'<text x="{cols[i] + 4}" y="12" class="tbl-head">{h}</text>')

        for r, row_data in enumerate(rows):
            ry = 16 + r * row_h
            bg = "#ffffff" if r % 2 == 0 else "#f0f4ff"
            parts.append(f'<rect x="0" y="{ry}" width="{width - 40}" height="{row_h}" fill="{bg}"/>')
            for c, cell in enumerate(row_data):
                parts.append(f'<text x="{cols[c] + 4}" y="{ry + 10}" class="tbl-cell">{cell}</text>')

        parts.append("</g>")
        return "".join(parts)

    def _error_svg(self, msg):
        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 100">
  <text x="200" y="50" text-anchor="middle" fill="red" font-family="Rajdhani,sans-serif">{msg}</text>
</svg>'''
