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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from xml.sax.saxutils import escape as _xml_escape, quoteattr as _xml_quoteattr

AR_KEYWORDS = {"autorecloser", "auto recloser", "tavrida", "noja", "schneider ar"}


def esc(s):
    """Escape text content for an SVG <text> body. Escape ONCE, at the
    interpolation boundary — every substation/feeder/transformer-derived string
    must pass through here before it reaches the markup."""
    return _xml_escape("" if s is None else str(s))


def escattr(s):
    """Escape + quote a value for an SVG attribute (returns the value WITH its
    quotes). No attribute in this module currently carries user data — every
    `id`/`class`/`transform` is generated — so this has no call site yet; it is
    the correct tool the moment one does."""
    return _xml_quoteattr("" if s is None else str(s))

RATINGS = {
    "vcb_33": "1250A, 25kA",
    "vcb_11": "1250A, 25kA",
    "iso_33": "630A, 25kA",
    "iso_11": "630A, 25kA",
    "la":     "30kV, 10kA",
    "ct":     "400/5A",
}

def is_autorecloser(feeder: dict) -> bool:
    if feeder.get("is_autorecloser"):
        return True
    sg = feeder.get("switchgear", {})
    for _f in ("vcb_type", "vcb_make", "panel_make"):
        val = str(sg.get(_f) or "").lower()
        if any(kw in val for kw in AR_KEYWORDS):
            return True
    return False


def sym_line(x1, y1, x2, y2, color="#CC2200", w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"/>'


def sym_earth(x, y, color="#006600"):
    """Bare earthing glyph — the three shrinking bars used by every earthed leg."""
    return f"""<g class="sym-earth" transform="translate({x},{y})">
    <line x1="0" y1="-8" x2="0" y2="0" stroke="{color}" stroke-width="2"/>
    <line x1="-7" y1="0" x2="7" y2="0" stroke="{color}" stroke-width="2.2"/>
    <line x1="-5" y1="4" x2="5" y2="4" stroke="{color}" stroke-width="1.6"/>
    <line x1="-2.5" y1="8" x2="2.5" y2="8" stroke="{color}" stroke-width="1"/>
  </g>"""


def sym_lightning_arrester(x, y, color="#CC2200", label="LA"):
    lbl = f'<text x="10" y="2" font-size="8" fill="#888">{esc(label)}</text>' if label else ""
    return f"""<g class="sym-la" transform="translate({x},{y})">
    <line x1="0" y1="-22" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <polygon points="0,-10 -8,8 8,8" fill="none" stroke="{color}" stroke-width="1.8"/>
    <line x1="0" y1="8" x2="0" y2="16" stroke="{color}" stroke-width="2"/>
    <line x1="-7" y1="16" x2="7" y2="16" stroke="#006600" stroke-width="2.2"/>
    <line x1="-5" y1="20" x2="5" y2="20" stroke="#006600" stroke-width="1.6"/>
    <line x1="-2.5" y1="24" x2="2.5" y2="24" stroke="#006600" stroke-width="1"/>
    {lbl}
  </g>"""


def sym_isolator(x, y, has_earth=False, color="#CC2200", label=""):
    earth = ""
    if has_earth:
        earth = """<line x1="6" y1="8" x2="6" y2="18" stroke="#006600" stroke-width="1.8"/>
    <line x1="0" y1="18" x2="12" y2="18" stroke="#006600" stroke-width="1.8"/>
    <line x1="2" y1="22" x2="10" y2="22" stroke="#006600" stroke-width="1.3"/>
    <line x1="4" y1="26" x2="8" y2="26" stroke="#006600" stroke-width="1"/>"""
    lbl = f'<text x="14" y="4" font-size="8" fill="#888">{esc(label)}</text>' if label else ""
    return f"""<g class="sym-iso" transform="translate({x},{y})">
    <line x1="0" y1="-18" x2="0" y2="-6" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="-6" r="2.5" fill="{color}"/>
    <line x1="0" y1="-6" x2="12" y2="6" stroke="{color}" stroke-width="1.8"/>
    <circle cx="12" cy="6" r="2.5" fill="none" stroke="{color}" stroke-width="1.5"/>
    <line x1="12" y1="6" x2="12" y2="18" stroke="{color}" stroke-width="2"/>
    {earth}{lbl}
  </g>"""


def sym_vcb(x, y, label="VCB", color="#CC2200"):
    lbl = (f'<text x="14" y="4" font-size="9" fill="#555" font-weight="600">{esc(label)}</text>'
           if label else "")
    return f"""<g class="sym-vcb" transform="translate({x},{y})">
    <line x1="0" y1="-22" x2="0" y2="-10" stroke="{color}" stroke-width="2"/>
    <rect x="-10" y="-10" width="20" height="20" fill="white" stroke="{color}" stroke-width="2" rx="1"/>
    <line x1="-8" y1="-8" x2="8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="8" y1="-8" x2="-8" y2="8" stroke="{color}" stroke-width="1.5"/>
    <line x1="0" y1="10" x2="0" y2="22" stroke="{color}" stroke-width="2"/>
    {lbl}
  </g>"""


def sym_autorecloser(x, y, label="AR", color="#CC2200"):
    lbl = (f'<text x="18" y="4" font-size="9" fill="#555" font-weight="600">{esc(label)}</text>'
           if label else "")
    return f"""<g class="sym-ar" transform="translate({x},{y})">
    <line x1="0" y1="-26" x2="0" y2="-14" stroke="{color}" stroke-width="2"/>
    <circle cx="0" cy="0" r="14" fill="white" stroke="{color}" stroke-width="2"/>
    <text x="0" y="5" text-anchor="middle" font-size="13" font-weight="700" fill="{color}">A</text>
    <line x1="0" y1="14" x2="0" y2="26" stroke="{color}" stroke-width="2"/>
    {lbl}
  </g>"""


def sym_ct(x, y, label="CT", color="#555555"):
    lbl = f'<text x="13" y="4" font-size="8" fill="#888">{esc(label)}</text>' if label else ""
    return f"""<g class="sym-ct" transform="translate({x},{y})">
    <line x1="0" y1="-20" x2="0" y2="20" stroke="{color}" stroke-width="2"/>
    <ellipse cx="0" cy="0" rx="10" ry="7" fill="white" stroke="{color}" stroke-width="1.8"/>
    {lbl}
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
    <text x="10" y="12" font-size="8" fill="#888">{esc(label)}</text>
  </g>"""


def sym_transformer(x, y, label="2.5MVA\n33/11kV"):
    lines = [ln for ln in (label or "").split("\n") if ln]
    text_els = "".join(
        f'<tspan x="38" dy="{0 if i==0 else 14}" font-size="10">{esc(ln)}</tspan>'
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
    lbl = f'<text x="{x1}" y="{y-8}" font-size="10" font-weight="700" fill="{c}" letter-spacing="0.5">{esc(label)}</text>' if label else ""
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
          transform="rotate(-35,0,55)">{esc((name or "")[:20])}</text>
  </g>"""


def sym_station_transformer(x, y, label="Station Tr"):
    lines = [ln for ln in (label or "").split("\n") if ln]
    text_els = "".join(
        f'<tspan x="20" dy="{0 if i == 0 else 11}" font-size="8">{esc(ln)}</tspan>'
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


def sym_ocef_marker(x, y, label="TVM"):
    lbl = f'<text x="24" y="3" font-size="7" fill="#888">{esc(label)}</text>' if label else ""
    return f"""<g class="sym-ocef" transform="translate({x},{y})">
    <rect x="-2" y="-6" width="18" height="12" fill="white" stroke="#888" stroke-width="1"/>
    <text x="7" y="3" text-anchor="middle" font-size="6.5" fill="#666">OC/EF</text>
    {lbl}
  </g>"""


def sym_bus_coupler_horizontal(x, y, color="#333333", label="BUS COUPLER"):
    """Short horizontal break in a bus: Iso - VCB - Iso, centred on x at height y."""
    lbl = (f'<text x="0" y="22" text-anchor="middle" font-size="8" fill="{color}" '
           f'font-weight="700">{esc(label)}</text>') if label else ""
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
    {lbl}
  </g>"""


LAYOUT = {"MARGIN": 80, "BAY_W": 130, "FEEDER_W": 110, "MIN_W": 940}

# Half-width of the 33 kV bus-coupler symbol; each bus segment stops this far
# short of `coupler_x` so the break in the bus is real.
COUPLER_HALF_W = 40

# Vertical extent, below Y["feed_bot"], of the -35°-rotated feeder-name label
# drawn by sym_feeder_out: its baseline is 60px down and rotates about (0,55),
# so a 20-char label sweeps to roughly y+88; +12 for the descender/leading.
FEEDER_LABEL_BAND = 100
LEGEND_GAP = 20
LEGEND_ROW_H = 32          # tall enough for a real (scaled) symbol glyph

Y = {
    "title": 8, "bay33_top": 74, "bay33_bot": 300, "bus33": 330,
    "tr_top": 360, "tr_bot": 494, "bus11": 624, "feed_top": 660,
    "feed_bot": 764,
}
# The legend must clear the whole rotated-label band or it paints over every
# 11 kV feeder name (it is appended last, over an opaque rect).
Y["legend"] = Y["feed_bot"] + FEEDER_LABEL_BAND + LEGEND_GAP


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


class SLDGenerator:
    def __init__(self, db):
        self.db = db

    # ── layout phase ────────────────────────────────────────────────────
    def _layout(self, ss, feeders, transformers):
        M = LAYOUT["MARGIN"]
        by_type = {}
        for f in feeders:
            ft = f.get("feeder_type")
            # Back-compat shim for pre-branch data: `lilo_33kv` records were
            # shipped before the type was retired; read them as outgoing_33kv
            # so they still appear on the diagram. Not a schema change.
            ft = "outgoing_33kv" if ft == "lilo_33kv" else ft
            by_type.setdefault(ft, []).append(f)
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
        # Each 11 kV section is laid out around its transformer's x: the incomer
        # riser sits at the centre and the feeder bays fan out to either side at
        # FEEDER_W pitch, with half a pitch of busbar past the outermost bay.
        FW = LAYOUT["FEEDER_W"]
        n_sec = max(len(trs), 1)
        sec_left  = [len(sec_feeders[i]) // 2 for i in range(n_sec)]
        sec_right = [len(sec_feeders[i]) - sec_left[i] for i in range(n_sec)]
        sec_widths = [(sec_left[i] + sec_right[i] + 1) * FW for i in range(n_sec)]
        # A transformer bay owns the whole slot its 11 kV section occupies, so
        # the two coordinate systems cannot drift apart.
        slot_widths = [max(sec_widths[i], LAYOUT["BAY_W"]) for i in range(n_sec)]

        # ---- 33 kV bays, left -> right ----
        bays33 = []
        x = M
        for f in inc33:
            bays33.append(self._bay_33kv(f, x + LAYOUT["BAY_W"] // 2, 0)); x += LAYOUT["BAY_W"]
        sec_origin = x                       # 11 kV sections start under the transformers
        sec_slots = []
        for i, t in enumerate(trs):
            slot_w = slot_widths[i]
            sec_x0 = x + (slot_w - sec_widths[i]) // 2
            cx = sec_x0 + sec_left[i] * FW + FW // 2
            bays33.append(self._bay_transformer(t, cx, 0))
            sec_slots.append((sec_x0, sec_x0 + sec_widths[i], cx))
            x += slot_w
        sec_end = x
        for f in out33:
            bays33.append(self._bay_33kv(f, x + LAYOUT["BAY_W"] // 2, 0)); x += LAYOUT["BAY_W"]
        for f in stn:
            b = self._bay_33kv(f, x + LAYOUT["BAY_W"] // 2, 0)
            b.kind = "station_transformer"
            b.equipment = [Equip("la", RATINGS["la"]), Equip("isolator", RATINGS["iso_33"])]
            bays33.append(b); x += LAYOUT["BAY_W"]

        # +BAY_W so the right-pinned bus PT keeps a bay's worth of clearance
        # from the last real bay instead of sitting on top of it.
        width = max(LAYOUT["MIN_W"], x + LAYOUT["BAY_W"] + M, sec_end + M)
        bus_pt = Bay(kind="bus_pt_33", x=width - M, label="33kV Bus PT", voltage_kv=33)
        bays33.append(bus_pt)

        # ---- 11 kV sections (aligned to their transformer bay) ----
        if not sec_slots:                    # no transformers — one nominal section
            w0 = sec_widths[0]
            sec_slots = [(sec_origin, sec_origin + w0, sec_origin + sec_left[0] * FW + FW // 2)]
        sections11 = []
        for i, (x0, x1, cx) in enumerate(sec_slots):
            tr = trs[i] if i < len(trs) else None
            fbays = []
            for k, f in enumerate(sec_feeders[i]):
                if k < sec_left[i]:          # left of the incomer riser
                    fx = cx - (sec_left[i] - k) * FW
                else:                        # right of it
                    fx = cx + (k - sec_left[i] + 1) * FW
                fbays.append(self._bay_11kv_feeder(f, fx))
            inc_bay = self._bay_11kv_incomer(tr, cx)
            sections11.append(Section(tr_index=i, bus=(x0, x1, Y["bus11"]),
                                      incomer_bay=inc_bay, bus_pt_x=x0 + 10,
                                      feeder_bays=fbays))

        # ---- 33 kV bus segments / coupler ----
        has_33_bc = any(f.get("voltage_kv") == 33 for f in by_type.get("bus_coupler", []))
        non_pt = sorted([b for b in bays33 if b.kind != "bus_pt_33"], key=lambda b: b.x)
        if has_33_bc and len(non_pt) >= 2:
            left_n = (len(non_pt) + 1) // 2           # ceil
            for j, b in enumerate(non_pt):
                b.segment = 0 if j < left_n else 1
            bus_pt.segment = 1
            # Break the bus in the gap between the last left bay and the first
            # right bay so neither segment overshoots the coupler.
            split = (non_pt[left_n - 1].x + non_pt[left_n].x) // 2
            split = max(M + COUPLER_HALF_W + 1, min(split, width - M - COUPLER_HALF_W - 1))
            bus33 = Bus(y=Y["bus33"],
                        segments=[(M, split - COUPLER_HALF_W),
                                  (split + COUPLER_HALF_W, width - M)],
                        coupler_x=split)
        else:
            bus33 = Bus(y=Y["bus33"], segments=[(M, width - M)], coupler_x=None)

        n_11_bc = sum(1 for f in by_type.get("bus_coupler", []) if f.get("voltage_kv") != 33)

        # ---- title (bus config derived from what we just laid out, not from a
        # possibly stale stored topology) ----
        updated = ss.get("updated_at") or datetime.now(timezone.utc)
        if has_33_bc and n_11_bc:
            bus_config = "sectionalized_both"
        elif has_33_bc:
            bus_config = "sectionalized_33kv"
        elif n_11_bc:
            bus_config = "sectionalized_11kv"
        else:
            bus_config = "single_bus"
        title = TitleBlock(
            name=ss.get("name", "Substation"),
            last_update_str=updated.strftime("%d.%m.%Y"),
            source_str=f'SOURCE: {ss.get("gss_primary", "—")} · '
                       f'{bus_config.replace("_", " ").title()}',
        )

        couplers11 = []
        for k in range(min(n_11_bc, max(len(sections11) - 1, 0))):
            gap_x = (sections11[k].bus[1] + sections11[k + 1].bus[0]) // 2
            couplers11.append(Coupler(orientation="h11", between=(k, k + 1), x=gap_x))

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
        legend_h = 24 + legend_rows * LEGEND_ROW_H
        legend = LegendBox(x=M, y=Y["legend"], w=width - 2 * M, h=legend_h, entries=legend_entries)

        return Scene(width=width, height=Y["legend"] + legend_h + M, title=title, bus33=bus33,
                     bays33=bays33, sections11=sections11, couplers11=couplers11, legend=legend)

    # ── bay builders ───────────────────────────────────────────────────
    def _bay_33kv(self, feeder, x, segment):
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
                   # keep it inside the renderer's 40-char cap so the sequence
                   # number always survives (bays used to truncate identically)
                   label=f'{cap} MVA 33/11kV Pr. Transformer-{tr.get("sequence", "")}',
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
  <text x="{w//2}" y="17" text-anchor="middle" font-size="13" font-weight="700" fill="white" letter-spacing="1">SLD - 33/11kV {esc(str(title.name).upper())} ELECTRICAL SUB-STATION</text>
  <text x="{w//2}" y="31" text-anchor="middle" font-size="10" font-weight="600" fill="#cbd5e1">DATE OF LAST UPDATE: {esc(title.last_update_str)}</text>
  <text x="{w//2}" y="52" text-anchor="middle" font-size="8" fill="#999">{esc(title.source_str)}</text>
"""

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

        # 11 kV couplers (horizontal - sections are side-by-side at one Y)
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
            # the station TR's own LA + isolator stack, built in _layout
            top = Y["bay33_top"]
            out = [f'<text x="{bay.x}" y="{top-6}" text-anchor="middle" class="lbl33">{esc(bay.label[:34])}</text>',
                   sym_line(bay.x, bus_y, bay.x, top + 10, color=c)]
            eq = bay.equipment or [Equip("isolator", RATINGS["iso_33"])]
            ey = top + 30
            for e in eq:
                out.append(self._render_equip(e, bay.x, ey, c)); ey += 44
            out.append(sym_station_transformer(bay.x, ey + 16,
                                               label=bay.label.replace(" ", "\n", 1)))
            return "".join(out)
        if bay.kind == "transformer":
            tr = bay.ref or {}
            # LV lead stops at tr_bot — the 11 kV incomer bay continues from there
            # down to the section busbar, so the two are in series on one x.
            out = [f'<text x="{bay.x}" y="{Y["bay33_top"]-8}" text-anchor="middle" class="lbl33">{esc(bay.label[:40])}</text>',
                   sym_line(bay.x, bus_y, bay.x, Y["tr_top"]-18, color="#CC2200"),
                   sym_isolator(bay.x, Y["tr_top"], has_earth=True, color="#CC2200", label=RATINGS["iso_33"]),
                   sym_line(bay.x+12, Y["tr_top"]+18, bay.x, Y["tr_top"]+40, color="#CC2200"),
                   sym_transformer(bay.x, Y["tr_top"]+78, label=f'{tr.get("capacity_mva","?")}MVA\n33/11kV'),
                   sym_line(bay.x, Y["tr_top"]+116, bay.x, Y["tr_bot"], color="#0055CC")]
            return "".join(out)

        top = Y["bay33_top"]
        out = [f'<text x="{bay.x}" y="{top-8}" text-anchor="middle" class="lbl33">{esc(bay.label[:24])}</text>']
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
        """The incomer bay hangs off the transformer's LV lead (same x) and runs
        down to the section busbar, so transformer and incomer are in series."""
        bay = sec.incomer_bay
        c = "#0055CC"
        top = Y["tr_bot"]
        out = [sym_line(bay.x, top, bay.x, bus_y, color=c)]
        step = (bus_y - top) / (len(bay.equipment) + 1)
        y = top
        for e in bay.equipment:
            y += step
            out.append(self._render_equip(e, bay.x, int(y), c))
        out.append(f'<text x="{bay.x+16}" y="{top+12}" class="lbl11">{esc(bay.label)}</text>')
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

    # Each legend entry draws its real symbol at reduced scale (spec §3.4).
    # (scale, builder) — builder is called at the local origin with no label so
    # the symbol's own annotation text doesn't clutter the 32px row.
    _LEGEND_GLYPHS = {
        "la":     (0.48, lambda: sym_lightning_arrester(0, 0, color="#555", label="")),
        "isolator": (0.48, lambda: sym_isolator(0, 0, has_earth=True, color="#555")),
        "vcb":    (0.48, lambda: sym_vcb(0, 0, label="", color="#555")),
        "ar":     (0.42, lambda: sym_autorecloser(0, 0, label="", color="#555")),
        "ct":     (0.55, lambda: sym_ct(0, 0, label="", color="#555")),
        "pt":     (0.48, lambda: sym_bus_pt(0, -14, label="", color="#555")),
        "transformer": (0.26, lambda: sym_transformer(0, -7, label="")),
        "station_transformer": (0.42, lambda: sym_station_transformer(0, -6, label="")),
        "coupler": (0.32, lambda: sym_bus_coupler_horizontal(0, 0, color="#555", label="")),
        "bus":    (1.0,  lambda: sym_busbar(-13, 0, 13, color="#111111")),
        "earth":  (0.9,  lambda: sym_earth(0, -4)),
        "ocef":   (0.62, lambda: sym_ocef_marker(-7, 0, label="")),
    }

    def _legend_glyph(self, kind, cx, cy):
        spec = self._LEGEND_GLYPHS.get(kind)
        if not spec:                       # unknown kind — keep the placeholder
            return f'<rect x="{cx-8}" y="{cy-6}" width="16" height="12" fill="white" stroke="#888"/>'
        scale, build = spec
        return (f'<g transform="translate({cx},{cy}) scale({scale})">'
                f'{build()}</g>')

    def _render_legend(self, legend):
        cols = 3
        col_w = legend.w // cols
        out = [f'<g transform="translate({legend.x},{legend.y})">',
               f'<rect x="0" y="0" width="{legend.w}" height="{legend.h}" fill="#f8f9fa" stroke="#ccc" rx="4"/>',
               f'<text x="8" y="15" font-size="9" font-weight="700" fill="#1a2744" letter-spacing="1">LEGEND</text>']
        for i, e in enumerate(legend.entries):
            r, c = divmod(i, cols)
            gx = 10 + c * col_w
            gy = 24 + r * LEGEND_ROW_H
            out.append(self._legend_glyph(e.glyph_kind, gx + 13, gy + 14))
            out.append(f'<text x="{gx+34}" y="{gy+12}" font-size="7.5" font-weight="700" fill="#333">{esc(e.name)}</text>')
            out.append(f'<text x="{gx+34}" y="{gy+22}" font-size="6.5" fill="#777">{esc(e.description)}</text>')
        out.append("</g>")
        return "".join(out)

    def _error_svg(self, msg):
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 120"><rect width="500" height="120" fill="#fff1f0" rx="8"/><text x="250" y="65" text-anchor="middle" fill="#cc2200" font-family="Rajdhani,sans-serif" font-size="14" font-weight="700">{esc(msg)}</text></svg>'
