"""
PDF Report Generator — Pure ReportLab, no svglib.
Generates a full substation report:
  Page 1: Cover + substation info + topology summary
  Page 2: Transformer details table
  Page 3: Feeder & switchgear details table
  Page 4: DC supply table + meter details
"""
import io
from datetime import datetime, timezone
from bson import ObjectId

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Spacer,
    Paragraph, HRFlowable, PageBreak, KeepTogether,
)

# Colour palette
C_DARK    = colors.HexColor("#1a2744")
C_RED33   = colors.HexColor("#CC2200")
C_BLUE11  = colors.HexColor("#0055CC")
C_GREEN   = colors.HexColor("#006600")
C_STRIPE  = colors.HexColor("#eef2ff")
C_WHITE   = colors.white
C_LTGREY  = colors.HexColor("#f8f9fa")
C_BORDER  = colors.HexColor("#cccccc")


def _s(v):
    """Safe string — return dash for None/empty."""
    if v is None:
        return "—"
    s = str(v).strip()
    return s if s else "—"


def _now():
    return datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")


class PDFReportGenerator:
    def __init__(self, db):
        self.db = db

    def generate(self, substation_id: str, svg_string: str = None) -> bytes:
        """svg_string ignored — we generate native ReportLab content."""
        ss = self.db.substations.find_one({"_id": ObjectId(substation_id)})
        if not ss:
            raise ValueError("Substation not found")

        feeders = list(self.db.feeders.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))
        transformers = list(self.db.transformers.find(
            {"substation_id": ObjectId(substation_id)}).sort("sequence", 1))

        buf = io.BytesIO()
        page_w, page_h = landscape(A3)
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A3),
            leftMargin=16*mm, rightMargin=16*mm,
            topMargin=14*mm, bottomMargin=14*mm,
            title=f"SLD Report — {ss.get('name','')}",
        )

        styles = getSampleStyleSheet()
        title_st = ParagraphStyle("rpt_title",
            fontName="Helvetica-Bold", fontSize=18,
            textColor=C_DARK, alignment=TA_CENTER, spaceAfter=3)
        sub_st = ParagraphStyle("rpt_sub",
            fontName="Helvetica-Bold", fontSize=13,
            textColor=C_RED33, alignment=TA_CENTER, spaceAfter=3)
        meta_st = ParagraphStyle("rpt_meta",
            fontName="Helvetica", fontSize=9,
            textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=2)
        section_st = ParagraphStyle("rpt_section",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=C_DARK, spaceBefore=10, spaceAfter=5,
            borderPad=4)
        note_st = ParagraphStyle("rpt_note",
            fontName="Helvetica-Oblique", fontSize=8,
            textColor=colors.HexColor("#888888"), alignment=TA_CENTER)

        story = []
        usable_w = page_w - 32*mm

        # ── PAGE 1: Cover ────────────────────────────────────────────────────
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("SINGLE LINE DIAGRAM &amp; EQUIPMENT REPORT", title_st))
        story.append(Paragraph(
            f"33/11 kV {_s(ss.get('name')).upper()} ELECTRICAL SUB-STATION", sub_st))
        story.append(HRFlowable(width="100%", thickness=2.5, color=C_DARK, spaceAfter=6))

        # Info grid table
        topo = ss.get("topology", {})
        gps  = ss.get("gps", {})
        info_data = [
            ["Circle", _s(ss.get("circle")),     "Region",      _s(ss.get("region"))],
            ["T&C",    _s(ss.get("tnc")),         "ESD",         _s(ss.get("esd"))],
            ["Type",   _s(ss.get("type")),        "GPS",         f"{_s(gps.get('lat'))}°N, {_s(gps.get('lon'))}°E"],
            ["Primary GSS (132/33 kV)", _s(ss.get("gss_primary")),
             "Alternate GSS", _s(ss.get("gss_alternate"))],
            ["Tapping Info", _s(ss.get("tapping_info")),
             "LILO Info",    _s(ss.get("lilo_info"))],
        ]
        info_col_w = usable_w / 4
        info_tbl = Table(info_data, colWidths=[info_col_w*0.8, info_col_w*1.2]*2)
        info_tbl.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
            ("FONTNAME",  (2,0), (2,-1),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("TEXTCOLOR", (0,0), (0,-1),  C_DARK),
            ("TEXTCOLOR", (2,0), (2,-1),  C_DARK),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [C_WHITE, C_STRIPE]),
            ("GRID",      (0,0), (-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",(0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",(0,0),(-1,-1), 6),
        ]))
        story.append(info_tbl)
        story.append(Spacer(1, 6*mm))

        # Topology summary
        story.append(Paragraph("NETWORK TOPOLOGY SUMMARY", section_st))
        bus_config = (topo.get("bus_config") or "single_bus").replace("_"," ").title()
        topo_data = [
            ["Bus Configuration", bus_config,
             "No. of Transformers", _s(topo.get("num_transformers"))],
            ["Bus Coupler Present", "Yes" if topo.get("has_bus_coupler") else "No",
             "Station Transformer", "Yes" if topo.get("has_station_transformer") else "No"],
            ["33 kV Incoming Feeders", _s(topo.get("incoming_33kv_count")),
             "11 kV Outgoing Feeders", _s(topo.get("outgoing_11kv_count"))],
        ]
        topo_tbl = Table(topo_data, colWidths=[info_col_w*0.8, info_col_w*1.2]*2)
        topo_tbl.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
            ("FONTNAME",  (2,0), (2,-1),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("TEXTCOLOR", (0,0), (0,-1),  C_BLUE11),
            ("TEXTCOLOR", (2,0), (2,-1),  C_BLUE11),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_WHITE, C_STRIPE]),
            ("GRID",      (0,0), (-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",(0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",(0,0),(-1,-1), 6),
        ]))
        story.append(topo_tbl)
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            f"Report generated: {_now()}  |  View SLD in browser for the interactive single line diagram.",
            note_st))

        story.append(PageBreak())

        # ── PAGE 2: Transformer Details ──────────────────────────────────────
        story.append(Paragraph("POWER TRANSFORMER DETAILS", section_st))
        tr_hdrs = ["#", "Capacity\n(MVA)", "Make", "YOM",
                   "Max Load\n(MW)", "Max OTI\n(°C)", "Max WTI\n(°C)"]
        tr_rows = [tr_hdrs]
        for tr in transformers:
            tr_rows.append([
                _s(tr.get("sequence")), _s(tr.get("capacity_mva")),
                _s(tr.get("make")),     _s(tr.get("yom")),
                _s(tr.get("max_loading_mw")), _s(tr.get("max_oti_c")),
                _s(tr.get("max_wti_c")),
            ])
        if len(tr_rows) == 1:
            tr_rows.append(["No transformer data", "—","—","—","—","—","—"])
        tr_cw = usable_w / len(tr_hdrs)
        story.append(self._make_table(tr_rows, [tr_cw]*len(tr_hdrs)))
        story.append(Spacer(1, 8*mm))

        # ── Feeder & Switchgear Table ─────────────────────────────────────────
        story.append(Paragraph("FEEDER &amp; SWITCHGEAR DETAILS", section_st))
        fd_hdrs = ["#", "Feeder Name", "Type", "kV",
                   "VCB Type", "Panel Make", "VCB Make", "YOM",
                   "OC/EF Relay", "Status"]
        fd_rows = [fd_hdrs]
        for i, fd in enumerate(feeders, 1):
            sg = fd.get("switchgear", {})
            from app.services.sld_generator import is_autorecloser
            ar = " [AR]" if is_autorecloser(fd) else ""
            fd_rows.append([
                str(i),
                _s(fd.get("name"))[:30] + ar,
                fd.get("feeder_type","").replace("_"," "),
                _s(fd.get("voltage_kv")),
                _s(sg.get("vcb_type")),     _s(sg.get("panel_make")),
                _s(sg.get("vcb_make")),     _s(sg.get("yom")),
                _s(sg.get("oc_ef_relay_type")), _s(sg.get("vcb_status")),
            ])
        fd_cw_map = [8*mm, 55*mm, 28*mm, 10*mm,
                     22*mm, 32*mm, 28*mm, 14*mm, 30*mm, 22*mm]
        story.append(self._make_table(fd_rows, fd_cw_map, font_size=7))

        story.append(PageBreak())

        # ── PAGE 3: Meter Details ─────────────────────────────────────────────
        story.append(Paragraph("METER &amp; CT DETAILS", section_st))
        mt_hdrs = ["#", "Feeder Name", "Meter No.", "Make",
                   "Type", "Status", "CTR", "MF", "CT Type", "CT Status", "DCU"]
        mt_rows = [mt_hdrs]
        for i, fd in enumerate(feeders, 1):
            mt = fd.get("meter", {})
            mt_rows.append([
                str(i), _s(fd.get("name"))[:28],
                _s(mt.get("number")),    _s(mt.get("make")),
                _s(mt.get("meter_type")),_s(mt.get("status")),
                _s(mt.get("ctr")),       _s(mt.get("mf")),
                _s(mt.get("ct_type")),   _s(mt.get("ct_status")),
                _s(mt.get("dcu_status")),
            ])
        mt_cw_map = [8*mm, 50*mm, 28*mm, 24*mm,
                     20*mm, 18*mm, 20*mm, 16*mm, 26*mm, 18*mm, 18*mm]
        story.append(self._make_table(mt_rows, mt_cw_map, font_size=7))
        story.append(Spacer(1, 8*mm))

        # DC Supply
        dc_rows_data = [fd for fd in feeders if fd.get("dc_supply", {}).get("charger_status")]
        if dc_rows_data:
            story.append(Paragraph("DC SUPPLY DETAILS", section_st))
            dc_hdrs = ["Feeder", "Charger Status", "Charger Make",
                       "Charger YOM", "Battery Status", "Battery Type"]
            dc_rows = [dc_hdrs]
            for fd in dc_rows_data:
                dc = fd.get("dc_supply", {})
                dc_rows.append([
                    _s(fd.get("name"))[:28],
                    _s(dc.get("charger_status")), _s(dc.get("charger_make")),
                    _s(dc.get("charger_yom")),    _s(dc.get("battery_status")),
                    _s(dc.get("battery_type")),
                ])
            dc_cw = usable_w / 6
            story.append(self._make_table(dc_rows, [dc_cw]*6))

        doc.build(story, onFirstPage=self._header_footer,
                  onLaterPages=self._header_footer)
        buf.seek(0)
        return buf.read()

    def _make_table(self, data, col_widths, font_size=8):
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), C_DARK),
            ("TEXTCOLOR",     (0,0), (-1,0), C_WHITE),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0), font_size),
            ("ALIGN",         (0,0), (-1,-1), "LEFT"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,1), (-1,-1), font_size-1),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_STRIPE]),
            ("GRID",          (0,0), (-1,-1), 0.4, C_BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("WORDWRAP",      (0,0), (-1,-1), True),
        ]))
        return t

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        w, h = landscape(A3)
        # Header bar
        canvas.setFillColor(C_DARK)
        canvas.rect(0, h-12*mm, w, 12*mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(C_WHITE)
        canvas.drawCentredString(w/2, h-8*mm, "GEC-II CIRCLE — ELECTRICAL SUBSTATION SLD PORTAL")
        # Footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(16*mm, 6*mm, f"Generated: {_now()}")
        canvas.drawCentredString(w/2, 6*mm, "CONFIDENTIAL — FOR INTERNAL USE ONLY")
        canvas.drawRightString(w-16*mm, 6*mm, f"Page {doc.page}")
        canvas.restoreState()
