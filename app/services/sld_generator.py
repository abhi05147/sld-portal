"""
SVG Single-Line Diagram Generator — IEC 60617 compliant symbols.
Based on MES Likabali SS layout.

Colour scheme:
  33kV : #CC2200  (red)
  11kV : #0055CC  (blue)
  Bus  : #111111  (black)
  Earth: #006600  (green)
"""
from bson import ObjectId

AR_KEYWORDS = {"autorecloser", "auto recloser", "tavrida", "noja", "schneider ar"}

def is_autorecloser(feeder: dict) -> bool:
    if feeder.get("is_autorecloser"):
        return True
    sg = feeder.get("switchgear", {})
    for field in ("vcb_type", "vcb_make", "panel_make"):
        val = str(sg.get(field) or "").lower()
        if any(kw in val for kw in AR_KEYWORDS):
            return True
    return False


def sym_line(x1, y1, x2, y2, color="#CC2200", w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"/>'


def sym_lightning_arrester(x, y, color="#CC2200"):
    return f"""<g class="sym-la" transform="translate({x},{y})">
    <line x1="0" y1="-22" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <polygon points="0,-10 -8,8 8,8" fill="none" stroke="{color}" stroke-width="1.8"/>
    <line x1="0" y1="8" x2="0" y2="16" stroke="{color}" stroke-width="2"/>
    <line x1="-7" y1="16" x2="7" y2="16" stroke="#006600" stroke-width="2.2"/>
    <line x1="-5" y1="20" x2="5" y2="20" stroke="#006600" stroke-width="1.6"/>
    <line x1="-2.5" y1="24" x2="2.5" y2="24" stroke="#006600" stroke-width="1"/>
    <text x="10" y="2" font-size="8" fill="#888">LA</text>
  </g>"""


def sym_isolator(x, y, has_earth=False, color="#CC2200", label=""):
    earth = ""
    if has_earth:
        earth = """<line x1="6" y1="8" x2="6" y2="18" stroke="#006600" stroke-width="1.8"/>
    <line x1="0" y1="18" x2="12" y2="18" stroke="#006600" stroke-width="1.8"/>
    <line x1="2" y1="22" x2="10" y2="22" stroke="#006600" stroke-width="1.3"/>
    <line x1="4" y1="26" x2="8" y2="26" stroke="#006600" stroke-width="1"/>"""
    lbl = f'<text x="14" y="4" font-size="8" fill="#888">{label}</text>' if label else ""
    return f"""<g class="sym-iso" transform="translate({x},{y})">
    <line x1="0" y1="-18" x2="0" y2="-6" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="-6" r="2.5" fill="{color}"/>
    <line x1="0" y1="-6" x2="12" y2="6" stroke="{color}" stroke-width="1.8"/>
    <circle cx="12" cy="6" r="2.5" fill="none" stroke="{color}" stroke-width="1.5"/>
    <line x1="12" y1="6" x2="12" y2="18" stroke="{color}" stroke-width="2"/>
    {earth}{lbl}
  </g>"""


def sym_vcb(x, y, label="VCB", color="#CC2200"):
    return f"""<g class="sym-vcb" transform="translate({x},{y})">
    <line x1="0" y1="-22" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <rect x="-10" y="-10" width="20" height="20" fill="white" stroke="{color}" stroke-width="2" rx="1"/>
    <line x1="-8" y1="-8" x2="8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="8" y1="-8" x2="-8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="0" y1="10" x2="0" y2="22" stroke="{color}" stroke-width="2"/>
    <text x="14" y="4" font-size="9" fill="#555" font-weight="600">{label}</text>
  </g>"""


def sym_autorecloser(x, y, label="AR", color="#CC2200"):
    return f"""<g class="sym-ar" transform="translate({x},{y})">
    <line x1="0" y1="-26" x2="0" y2="-14" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="0" r="14" fill="white" stroke="{color}" stroke-width="2"/>
    <text x="0" y="5" text-anchor="middle" font-size="13" font-weight="700" fill="{color}">A</text>
    <line x1="0" y1="14" x2="0" y2="26" stroke="{color}" stroke-width="2"/>
    <text x="18" y="4" font-size="9" fill="#555" font-weight="600">{label}</text>
  </g>"""


def sym_ct(x, y, label="CT", color="#555555"):
    return f"""<g class="sym-ct" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
    <ellipse cx="0" cy="0" rx="10" ry="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    <text x="13" y="4" font-size="8" fill="#888">{label}</text>
  </g>"""


def sym_bus_pt(x, y, label="Bus PT", color="#555"):
    return f"""<g class="sym-pt" transform="translate({x},{y})">
    <line x1="0" y1="-8" x2="0" y2="-2" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="5" r="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    <circle cx="0" cy="16" r="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    <line x1="0" y1="23" x2="0" y2="30" stroke="#006600" stroke-width="1.8"/>
    <line x1="-6" y1="30" x2="6" y2="30" stroke="#006600" stroke-width="1.8"/>
    <line x1="-4" y1="34" x2="4" y2="34" stroke="#006600" stroke-width="1.4"/>
    <line x1="-2" y1="38" x2="2" y2="38" stroke="#006600" stroke-width="1"/>
    <text x="10" y="12" font-size="8" fill="#888">{label}</text>
  </g>"""


def sym_transformer(x, y, label="2.5MVA\n33/11kV"):
    lines = label.split("\n")
    text_els = "".join(
        f'<tspan x="38" dy="{0 if i==0 else 14}" font-size="10">{ln}</tspan>'
        for i, ln in enumerate(lines)
    )
    return f"""<g class="sym-tr" transform="translate({x},{y})">
    <line x1="0" y1="-38" x2="0" y2="-20" stroke="#CC2200" stroke-width="2.5"/>
    <circle cx="0" cy="-8" r="13" fill="white" stroke="#CC2200" stroke-width="2.2"/>
    <circle cx="0" cy="8" r="13" fill="white" stroke="#0055CC" stroke-width="2.2"/>
    <line x1="0" y1="21" x2="0" y2="38" stroke="#0055CC" stroke-width="2.5"/>
    <line x1="0" y1="38" x2="0" y2="44" stroke="#006600" stroke-width="2"/>
    <line x1="-7" y1="44" x2="7" y2="44" stroke="#006600" stroke-width="2"/>
    <line x1="-5" y1="48" x2="5" y2="48" stroke="#006600" stroke-width="1.5"/>
    <line x1="-2.5" y1="52" x2="2.5" y2="52" stroke="#006600" stroke-width="1"/>
    <text font-weight="600" fill="#333" y="-6">{text_els}</text>
  </g>"""


def sym_busbar(x1, y, x2, label="", color="#111111", voltage=33):
    c = "#CC2200" if voltage == 33 else "#0055CC"
    lbl = f'<text x="{x1}" y="{y-8}" font-size="10" font-weight="700" fill="{c}" letter-spacing="0.5">{label}</text>' if label else ""
    return f"""<g class="sym-bus">{lbl}
    <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>
  </g>"""


def sym_feeder_out(x, y, name, voltage_kv=11, is_ar=False):
    color = "#0055CC" if voltage_kv == 11 else "#CC2200"
    ar_badge = (f'<rect x="-12" y="18" width="24" height="12" fill="{color}" rx="3"/>'
                f'<text x="0" y="28" text-anchor="middle" font-size="8" fill="white" font-weight="700">AR</text>') if is_ar else ""
    return f"""<g class="sym-feeder" transform="translate({x},{y})">
    <line x1="0" y1="0" x2="0" y2="32" stroke="{color}" stroke-width="2"/>
    <polygon points="0,40 -7,28 7,28" fill="{color}"/>
    {ar_badge}
    <text x="0" y="60" text-anchor="middle" font-size="9" fill="{color}" font-weight="600"
          transform="rotate(-35,0,55)">{name[:20]}</text>
  </g>"""


def sym_bus_coupler_vertical(x, y_bus1, y_bus2, color="#333333"):
    """
    Vertical bus coupler: Bus1 → Iso(ES) → VCB → Iso(ES) → Bus2
    Matches MES Likabali layout exactly.
    """
    gap    = y_bus2 - y_bus1
    iso1_y = y_bus1 + gap * 0.25
    vcb_y  = y_bus1 + gap * 0.5
    iso2_y = y_bus1 + gap * 0.75

    return f"""<g class="sym-bc" transform="translate({x},0)">
    <text x="22" y="{int(vcb_y)}" font-size="9" fill="{color}" font-weight="700">BUS COUPLER</text>
    <!-- Bus1 to Iso1 -->
    <line x1="0" y1="{y_bus1}" x2="0" y2="{int(iso1_y)-18}" stroke="{color}" stroke-width="2"/>
    <!-- Isolator 1 with ES -->
    <g transform="translate(0,{int(iso1_y)})">
      <line x1="0" y1="-18" x2="0" y2="-6" stroke="{color}" stroke-width="2"/>
      <circle cx="0" cy="-6" r="2.5" fill="{color}"/>
      <line x1="0" y1="-6" x2="12" y2="6" stroke="{color}" stroke-width="1.8"/>
      <circle cx="12" cy="6" r="2.5" fill="none" stroke="{color}" stroke-width="1.5"/>
      <line x1="12" y1="6" x2="12" y2="18" stroke="{color}" stroke-width="2"/>
      <line x1="12" y1="10" x2="22" y2="10" stroke="#006600" stroke-width="1.8"/>
      <line x1="22" y1="6" x2="22" y2="18" stroke="#006600" stroke-width="1.8"/>
      <line x1="18" y1="22" x2="26" y2="22" stroke="#006600" stroke-width="1.3"/>
      <line x1="20" y1="26" x2="24" y2="26" stroke="#006600" stroke-width="1"/>
    </g>
    <!-- Iso1 to VCB -->
    <line x1="6" y1="{int(iso1_y)+18}" x2="6" y2="{int(vcb_y)-10}" stroke="{color}" stroke-width="2"/>
    <!-- VCB -->
    <g transform="translate(6,{int(vcb_y)})">
      <rect x="-10" y="-10" width="20" height="20" fill="white" stroke="{color}" stroke-width="2" rx="1"/>
      <line x1="-8" y1="-8" x2="8" y2="8" stroke="{color}" stroke-width="1.5"/>
      <line x1="8" y1="-8" x2="-8" y2="8" stroke="{color}" stroke-width="1.5"/>
      <text x="-8" y="16" font-size="8" fill="{color}" font-weight="600">BC VCB</text>
    </g>
    <!-- VCB to Iso2 -->
    <line x1="6" y1="{int(vcb_y)+10}" x2="6" y2="{int(iso2_y)-18}" stroke="{color}" stroke-width="2"/>
    <!-- Isolator 2 with ES -->
    <g transform="translate(6,{int(iso2_y)})">
      <line x1="0" y1="-18" x2="0" y2="-6" stroke="{color}" stroke-width="2"/>
      <circle cx="0" cy="-6" r="2.5" fill="{color}"/>
      <line x1="0" y1="-6" x2="12" y2="6" stroke="{color}" stroke-width="1.8"/>
      <circle cx="12" cy="6" r="2.5" fill="none" stroke="{color}" stroke-width="1.5"/>
      <line x1="12" y1="6" x2="12" y2="18" stroke="{color}" stroke-width="2"/>
      <line x1="12" y1="10" x2="22" y2="10" stroke="#006600" stroke-width="1.8"/>
      <line x1="22" y1="6" x2="22" y2="18" stroke="#006600" stroke-width="1.8"/>
      <line x1="18" y1="22" x2="26" y2="22" stroke="#006600" stroke-width="1.3"/>
      <line x1="20" y1="26" x2="24" y2="26" stroke="#006600" stroke-width="1"/>
    </g>
    <!-- Iso2 to Bus2 -->
    <line x1="18" y1="{int(iso2_y)+18}" x2="18" y2="{y_bus2}" stroke="{color}" stroke-width="2"/>
  </g>"""


class SLDGenerator:
    def __init__(self, db):
        self.db = db

    def generate(self, substation_id: str) -> str:
        ss = self.db.substations.find_one({"_id": ObjectId(substation_id)})
        if not ss:
            return self._error_svg("Substation not found")
        feeders = list(self.db.feeders.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))
        transformers = list(self.db.transformers.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))
        topo = ss.get("topology", {})
        bus_config = topo.get("bus_config", "single_bus")
        if bus_config in ("double_bus_coupler", "double_bus"):
            return self._render_double_bus(ss, feeders, transformers, topo)
        return self._render_single_bus(ss, feeders, transformers, topo)

    def _render_single_bus(self, ss, feeders, transformers, topo):
        outgoing = [f for f in feeders if f["feeder_type"] == "outgoing_11kv"]
        incoming = [f for f in feeders if f["feeder_type"] == "incoming_33kv"]
        lilo     = [f for f in feeders if f["feeder_type"] == "lilo_33kv"]
        num_out  = max(len(outgoing), 2)
        num_tr   = max(len(transformers), 1)
        num_lilo = len(lilo)
        margin   = 80
        col_w    = 110
        tr_col_w = 180

        tr_zone_w   = num_tr * tr_col_w
        lilo_zone_w = num_lilo * col_w
        combined_zone_w = tr_zone_w + lilo_zone_w
        total_w  = max(860, num_out * col_w + margin * 2, combined_zone_w + margin * 2)
        cx       = total_w // 2
        zone_x0  = cx - combined_zone_w // 2
        tr_start = zone_x0 + tr_col_w // 2
        lilo_x0  = zone_x0 + tr_zone_w

        Y = dict(
            top=60, la=95, iso1=134, vcb33=178, ct33=218,
            bus33=254, iso_tr=290, tr=350, vcb11=430,
            ct11=460, bus11=496, iso_out=532, vcb_out=574,
            ct_out=614, feeder=644,
            iso_lilo=290, vcb_lilo=332, ct_lilo=372, feeder_lilo=402,
        )
        total_h = Y["feeder"] + 100 + 200 + len(feeders) * 14
        p = [self._svg_header(ss, total_w, total_h)]

        inc_name = incoming[0]["name"] if incoming else "33 kV INCOMER"
        p.append(f'<text x="{cx}" y="{Y["top"]-12}" text-anchor="middle" class="lbl33">{inc_name}</text>')
        p.append(sym_line(cx, Y["top"], cx, Y["la"]-22))
        p.append(sym_lightning_arrester(cx-44, Y["la"]))
        p.append(f'<line x1="{cx-44}" y1="{Y["la"]-22}" x2="{cx}" y2="{Y["la"]-22}" stroke="#CC2200" stroke-width="1.5" stroke-dasharray="4,2"/>')
        p.append(sym_line(cx, Y["la"]-22, cx, Y["iso1"]-18))
        p.append(sym_isolator(cx, Y["iso1"], has_earth=True, label="800A,10kA"))
        p.append(sym_line(cx+12, Y["iso1"]+18, cx, Y["vcb33"]-22))
        p.append(sym_vcb(cx, Y["vcb33"], label="33kV VCB"))
        p.append(sym_line(cx, Y["vcb33"]+22, cx, Y["ct33"]-20))
        p.append(sym_ct(cx, Y["ct33"], label="33kV CT"))
        p.append(sym_bus_pt(cx+55, Y["bus33"]-40, label="33kV Bus PT"))
        p.append(f'<line x1="{cx}" y1="{Y["bus33"]}" x2="{cx+55}" y2="{Y["bus33"]}" stroke="#888" stroke-width="1.2" stroke-dasharray="3,2"/>')
        p.append(sym_line(cx, Y["ct33"]+20, cx, Y["bus33"]))
        p.append(sym_busbar(margin, Y["bus33"], total_w-margin, "33 kV BUS", "#111111", 33))

        for i, tr in enumerate(transformers):
            tx  = tr_start + i*tr_col_w
            cap = tr.get("capacity_mva", "?")
            p.append(sym_line(tx, Y["bus33"], tx, Y["iso_tr"]-18, color="#CC2200"))
            p.append(sym_isolator(tx, Y["iso_tr"], has_earth=True, color="#CC2200", label="800A,25kA"))
            p.append(sym_line(tx+12, Y["iso_tr"]+18, tx, Y["tr"]-38, color="#CC2200"))
            p.append(sym_transformer(tx, Y["tr"], label=f"{cap}MVA\n33/11kV"))
            p.append(sym_line(tx, Y["tr"]+38, tx, Y["vcb11"]-22, color="#0055CC"))
            p.append(sym_vcb(tx, Y["vcb11"], label="11kV VCB", color="#0055CC"))
            p.append(sym_line(tx, Y["vcb11"]+22, tx, Y["ct11"]-20, color="#0055CC"))
            p.append(sym_ct(tx, Y["ct11"], label="11kV CT", color="#555"))
            p.append(sym_line(tx, Y["ct11"]+20, tx, Y["bus11"], color="#0055CC"))

        if lilo:
            lilo_cx = lilo_x0 + lilo_zone_w // 2
            p.append(f'<text x="{lilo_cx}" y="{Y["bus33"]+18}" text-anchor="middle" class="lbl33" font-size="9">33kV LILO TAPS</text>')
        for i, fd in enumerate(lilo):
            lx = lilo_x0 + i*col_w + col_w//2
            ar = is_autorecloser(fd)
            c  = "#CC2200"
            p.append(sym_line(lx, Y["bus33"], lx, Y["iso_lilo"]-18, color=c))
            p.append(sym_isolator(lx, Y["iso_lilo"], has_earth=True, color=c, label="800A,13kA"))
            p.append(sym_line(lx+12, Y["iso_lilo"]+18, lx, Y["vcb_lilo"]-(26 if ar else 22), color=c))
            p.append(sym_autorecloser(lx, Y["vcb_lilo"], color=c) if ar else sym_vcb(lx, Y["vcb_lilo"], label="VCB", color=c))
            p.append(sym_line(lx, Y["vcb_lilo"]+22, lx, Y["ct_lilo"]-20, color=c))
            p.append(sym_ct(lx, Y["ct_lilo"], color="#555"))
            p.append(sym_line(lx, Y["ct_lilo"]+20, lx, Y["feeder_lilo"], color=c))
            p.append(sym_feeder_out(lx, Y["feeder_lilo"], fd["name"], 33, ar))

        p.append(sym_busbar(margin, Y["bus11"], total_w-margin, "11 kV BUS", "#0055CC", 11))
        p.append(sym_bus_pt(margin-10, Y["bus11"]-40, label="11kV Bus PT"))
        p.append(f'<line x1="{margin-10}" y1="{Y["bus11"]}" x2="{margin}" y2="{Y["bus11"]}" stroke="#888" stroke-width="1.2" stroke-dasharray="3,2"/>')
        p.append(f'<text x="{cx}" y="{Y["bus11"]+18}" text-anchor="middle" class="lbl11">11 kV OUTGOING FEEDERS</text>')

        sp  = max(col_w, (total_w - margin*2) // max(num_out, 1))
        sx  = margin + sp//2
        for i, fd in enumerate(outgoing):
            fx = sx + i*sp
            ar = is_autorecloser(fd)
            c  = "#0055CC"
            p.append(sym_line(fx, Y["bus11"], fx, Y["iso_out"]-18, color=c))
            p.append(sym_isolator(fx, Y["iso_out"], has_earth=True, color=c, label="800A,13kA"))
            p.append(sym_line(fx+12, Y["iso_out"]+18, fx, Y["vcb_out"]-(26 if ar else 22), color=c))
            p.append(sym_autorecloser(fx, Y["vcb_out"], color=c) if ar else sym_vcb(fx, Y["vcb_out"], label="VCB", color=c))
            p.append(sym_line(fx, Y["vcb_out"]+22, fx, Y["ct_out"]-20, color=c))
            p.append(sym_ct(fx, Y["ct_out"], color="#555"))
            p.append(sym_line(fx, Y["ct_out"]+20, fx, Y["feeder"], color=c))
            p.append(sym_feeder_out(fx, Y["feeder"], fd["name"], 11, ar))

        p.append(self._equipment_table(ss, feeders, transformers, total_w, Y["feeder"]+100))
        p.append("</svg>")
        return "".join(p)

    def _render_double_bus(self, ss, feeders, transformers, topo):
        outgoing   = [f for f in feeders if f["feeder_type"] == "outgoing_11kv"]
        incoming33 = [f for f in feeders if f["feeder_type"] == "incoming_33kv"]
        lilo       = [f for f in feeders if f["feeder_type"] == "lilo_33kv"]
        num_out    = max(len(outgoing), 2)
        num_tr     = max(len(transformers), 2)
        num_lilo   = len(lilo)
        margin     = 80
        col_w      = 110
        tr_col_w   = 160
        tr_zone_w  = num_tr * tr_col_w
        lilo_zone_w = num_lilo * col_w
        total_w    = max(980, num_out * col_w + margin * 2 + 160, margin*2 + tr_zone_w + lilo_zone_w)
        cx         = total_w // 2
        tr_start   = margin + tr_col_w // 2
        lilo_x0    = margin + tr_zone_w

        Y = dict(
            top=55, la=90, iso1=128, vcb33=172, ct33=212,
            bus33=248, iso_tr=284, tr=344, vcb11ic=424,
            ct11ic=454, bus11a=490, bus11b=570,
            iso_out=618, vcb_out=660, ct_out=700, feeder=730,
            iso_lilo=284, vcb_lilo=326, ct_lilo=366, feeder_lilo=396,
        )
        total_h = Y["feeder"] + 110 + 200 + len(feeders)*14
        p = [self._svg_header(ss, total_w, total_h)]

        # 33kV incomers
        inc_xs = []
        for i in range(min(max(len(incoming33), 2), 2)):
            ix = cx - 100 + i*200
            inc_xs.append(ix)
            name = incoming33[i]["name"] if i < len(incoming33) else f"33kV Incomer {i+1}"
            p.append(f'<text x="{ix}" y="{Y["top"]-12}" text-anchor="middle" class="lbl33" font-size="9">{name[:26]}</text>')
            p.append(sym_line(ix, Y["top"], ix, Y["la"]-22, color="#CC2200"))
            p.append(sym_lightning_arrester(ix-44, Y["la"]))
            p.append(f'<line x1="{ix-44}" y1="{Y["la"]-22}" x2="{ix}" y2="{Y["la"]-22}" stroke="#CC2200" stroke-width="1.5" stroke-dasharray="4,2"/>')
            p.append(sym_line(ix, Y["la"]-22, ix, Y["iso1"]-18, color="#CC2200"))
            p.append(sym_isolator(ix, Y["iso1"], has_earth=True, color="#CC2200", label="800A,10kA"))
            p.append(sym_line(ix+12, Y["iso1"]+18, ix, Y["vcb33"]-22, color="#CC2200"))
            p.append(sym_vcb(ix, Y["vcb33"], label="33kV VCB", color="#CC2200"))
            p.append(sym_line(ix, Y["vcb33"]+22, ix, Y["ct33"]-20, color="#CC2200"))
            p.append(sym_ct(ix, Y["ct33"], label="33kV CT", color="#555"))
            p.append(sym_line(ix, Y["ct33"]+20, ix, Y["bus33"], color="#CC2200"))

        p.append(sym_bus_pt(total_w-margin-10, Y["bus33"]-40, label="33kV Bus PT"))
        p.append(f'<line x1="{total_w-margin-10}" y1="{Y["bus33"]}" x2="{total_w-margin}" y2="{Y["bus33"]}" stroke="#888" stroke-width="1.2" stroke-dasharray="3,2"/>')
        p.append(sym_busbar(margin, Y["bus33"], total_w-margin, "33 kV BUS", "#111111", 33))

        # Transformers
        for i, tr in enumerate(transformers):
            tx  = tr_start + i*tr_col_w
            cap = tr.get("capacity_mva", "?")
            p.append(sym_line(tx, Y["bus33"], tx, Y["iso_tr"]-18, color="#CC2200"))
            p.append(sym_isolator(tx, Y["iso_tr"], has_earth=False, color="#CC2200", label="800A,25kA"))
            p.append(sym_line(tx+12, Y["iso_tr"]+18, tx, Y["tr"]-38, color="#CC2200"))
            p.append(sym_transformer(tx, Y["tr"], label=f"{cap}MVA\n33/11kV"))
            p.append(sym_line(tx, Y["tr"]+38, tx, Y["vcb11ic"]-22, color="#0055CC"))
            p.append(sym_vcb(tx, Y["vcb11ic"], label=f"11kV Incomer {i+1}", color="#0055CC"))
            p.append(sym_line(tx, Y["vcb11ic"]+22, tx, Y["ct11ic"]-20, color="#0055CC"))
            p.append(sym_ct(tx, Y["ct11ic"], label="11kV CT", color="#555"))
            bus_y = Y["bus11a"] if i == 0 else Y["bus11b"]
            p.append(sym_line(tx, Y["ct11ic"]+20, tx, bus_y, color="#0055CC"))

        if lilo:
            lilo_cx = lilo_x0 + lilo_zone_w // 2
            p.append(f'<text x="{lilo_cx}" y="{Y["bus33"]+18}" text-anchor="middle" class="lbl33" font-size="9">33kV LILO TAPS</text>')
        for i, fd in enumerate(lilo):
            lx = lilo_x0 + i*col_w + col_w//2
            ar = is_autorecloser(fd)
            c  = "#CC2200"
            p.append(sym_line(lx, Y["bus33"], lx, Y["iso_lilo"]-18, color=c))
            p.append(sym_isolator(lx, Y["iso_lilo"], has_earth=True, color=c, label="800A,13kA"))
            p.append(sym_line(lx+12, Y["iso_lilo"]+18, lx, Y["vcb_lilo"]-(26 if ar else 22), color=c))
            p.append(sym_autorecloser(lx, Y["vcb_lilo"], color=c) if ar else sym_vcb(lx, Y["vcb_lilo"], label="VCB", color=c))
            p.append(sym_line(lx, Y["vcb_lilo"]+22, lx, Y["ct_lilo"]-20, color=c))
            p.append(sym_ct(lx, Y["ct_lilo"], color="#555"))
            p.append(sym_line(lx, Y["ct_lilo"]+20, lx, Y["feeder_lilo"], color=c))
            p.append(sym_feeder_out(lx, Y["feeder_lilo"], fd["name"], 33, ar))

        # 11kV Bus 1 (left half) and Bus 2 (right half)
        p.append(sym_busbar(margin, Y["bus11a"], cx-30, "11 kV BUS - 1", "#0055CC", 11))
        p.append(sym_busbar(cx+30, Y["bus11b"], total_w-margin, "11 kV BUS - 2", "#0055CC", 11))

        # Bus PT on Bus 1
        p.append(sym_bus_pt(margin-10, Y["bus11a"]-40, label="11kV Bus PT"))
        p.append(f'<line x1="{margin-10}" y1="{Y["bus11a"]}" x2="{margin}" y2="{Y["bus11a"]}" stroke="#888" stroke-width="1.2" stroke-dasharray="3,2"/>')

        # Bus Coupler at centre — Iso(ES) → VCB → Iso(ES) vertical
        p.append(sym_bus_coupler_vertical(cx, Y["bus11a"], Y["bus11b"]))

        # Outgoing feeders split between the two buses
        half = len(outgoing)//2 + len(outgoing)%2
        bus1_fds = outgoing[:half]
        bus2_fds = outgoing[half:]

        p.append(f'<text x="{cx}" y="{Y["bus11b"]+18}" text-anchor="middle" class="lbl11">11 kV OUTGOING FEEDERS</text>')

        def draw_out(flist, bus_y, x0, sp2):
            for i, fd in enumerate(flist):
                fx = x0 + i*sp2
                ar = is_autorecloser(fd)
                c  = "#0055CC"
                p.append(sym_line(fx, bus_y, fx, Y["iso_out"]-18, color=c))
                p.append(sym_isolator(fx, Y["iso_out"], has_earth=True, color=c, label="800A,13kA"))
                p.append(sym_line(fx+12, Y["iso_out"]+18, fx, Y["vcb_out"]-(26 if ar else 22), color=c))
                p.append(sym_autorecloser(fx, Y["vcb_out"], color=c) if ar else sym_vcb(fx, Y["vcb_out"], label="VCB", color=c))
                p.append(sym_line(fx, Y["vcb_out"]+22, fx, Y["ct_out"]-20, color=c))
                p.append(sym_ct(fx, Y["ct_out"], color="#555"))
                p.append(sym_line(fx, Y["ct_out"]+20, fx, Y["feeder"], color=c))
                p.append(sym_feeder_out(fx, Y["feeder"], fd["name"], 11, ar))

        half_w   = (cx - margin - 60)
        out_sp1  = max(col_w, half_w // max(len(bus1_fds), 1))
        out_sp2  = max(col_w, half_w // max(len(bus2_fds), 1))
        draw_out(bus1_fds, Y["bus11a"], margin + out_sp1//2, out_sp1)
        draw_out(bus2_fds, Y["bus11b"], cx + 50 + out_sp2//2, out_sp2)

        p.append(self._equipment_table(ss, feeders, transformers, total_w, Y["feeder"]+110))
        p.append("</svg>")
        return "".join(p)

    def _svg_header(self, ss, w, h):
        name = ss.get("name", "Substation").upper()
        gss  = ss.get("gss_primary", "Unknown GSS")
        topo = ss.get("topology", {})
        bus  = (topo.get("bus_config") or "single_bus").replace("_", " ").upper()
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" id="sld-svg" font-family="Rajdhani,sans-serif">
  <defs><style>
    .lbl33{{font-size:11px;font-weight:700;fill:#CC2200;letter-spacing:.8px}}
    .lbl11{{font-size:11px;font-weight:700;fill:#0055CC;letter-spacing:.8px}}
    .tbl-hd{{font-size:8px;font-weight:700;fill:white}}
    .tbl-td{{font-size:7.5px;fill:#333}}
  </style></defs>
  <rect x="1" y="1" width="{w-2}" height="{h-2}" fill="white" stroke="#ccc" stroke-width="1" rx="4"/>
  <rect x="1" y="1" width="{w-2}" height="22" fill="#1a2744" rx="4"/>
  <text x="{w//2}" y="15" text-anchor="middle" font-size="11" font-weight="700" fill="white" letter-spacing="1">
    SLD — 33/11 kV {name} | SOURCE: {gss} | {bus}
  </text>
"""

    def _equipment_table(self, ss, feeders, transformers, width, y_start):
        rows = []
        for tr in transformers:
            rows.append((f"PTR-{tr.get('sequence','')} Power Transformer",
                         f"{tr.get('capacity_mva','-')} MVA",
                         tr.get("make","-") or "-",
                         str(tr.get("yom","-") or "-"),
                         f"OTI:{tr.get('max_oti_c','-')}°C WTI:{tr.get('max_wti_c','-')}°C"))
        for fd in feeders:
            if fd["feeder_type"] not in ("outgoing_11kv","incoming_33kv","lilo_33kv"):
                continue
            sg = fd.get("switchgear",{})
            mt = fd.get("meter",{})
            ar = " [AR]" if is_autorecloser(fd) else ""
            rows.append((fd["name"][:30]+ar,
                         f"{fd['voltage_kv']} kV",
                         sg.get("vcb_make","-") or "-",
                         str(sg.get("year_commissioned","-") or "-"),
                         f"Meter:{mt.get('number','-') or '-'} CTR:{mt.get('ctr','-') or '-'} MF:{mt.get('mf','-') or '-'}"))
        rh   = 14
        cols = [0, 210, 280, 340, 400, width-40]
        hdrs = ["Equipment / Feeder", "Rating", "Make", "YOM", "Meter / Notes"]
        tbl_h = len(rows)*rh + 20
        p = [f'<g transform="translate(20,{y_start})">',
             f'<rect x="0" y="0" width="{width-40}" height="{tbl_h}" fill="#f8f9fa" stroke="#ddd" rx="3"/>',
             f'<rect x="0" y="0" width="{width-40}" height="16" fill="#1a2744" rx="3"/>']
        for i, h in enumerate(hdrs):
            p.append(f'<text x="{cols[i]+4}" y="12" class="tbl-hd">{h}</text>')
        for r, row in enumerate(rows):
            ry = 16 + r*rh
            bg = "#fff" if r%2==0 else "#eef2ff"
            p.append(f'<rect x="0" y="{ry}" width="{width-40}" height="{rh}" fill="{bg}"/>')
            for c, cell in enumerate(row):
                p.append(f'<text x="{cols[c]+4}" y="{ry+10}" class="tbl-td">{cell}</text>')
        p.append("</g>")
        return "".join(p)

    def _error_svg(self, msg):
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 120"><rect width="500" height="120" fill="#fff1f0" rx="8"/><text x="250" y="65" text-anchor="middle" fill="#cc2200" font-family="Rajdhani,sans-serif" font-size="14" font-weight="700">{msg}</text></svg>'
