"""
PDF Report Generator — Full substation report:
  Page 1: Cover + SLD (SVG embedded)
  Page 2: Equipment summary table
  Page 3: Feeder details table
"""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Spacer,
    Paragraph, HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from bson import ObjectId
from datetime import datetime, timezone


C_DARK   = colors.HexColor("#1a2744")
C_RED33  = colors.HexColor("#CC2200")
C_BLUE11 = colors.HexColor("#0055CC")
C_GREY   = colors.HexColor("#f0f4ff")
C_WHITE  = colors.white


def _str(v):
    if v is None:
        return "-"
    return str(v).strip() or "-"


class PDFReportGenerator:
    def __init__(self, db):
        self.db = db

    def generate(self, substation_id: str, svg_string: str) -> bytes:
        ss = self.db.substations.find_one({"_id": ObjectId(substation_id)})
        if not ss:
            raise ValueError("Substation not found")

        feeders = list(
            self.db.feeders.find({"substation_id": ObjectId(substation_id)}).sort("sequence", 1)
        )
        transformers = list(
            self.db.transformers.find({"substation_id": ObjectId(substation_id)}).sort("sequence", 1)
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A3),
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title", fontName="Helvetica-Bold", fontSize=16,
            textColor=C_DARK, alignment=TA_CENTER, spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "Sub", fontName="Helvetica", fontSize=10,
            textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=2,
        )
        section_style = ParagraphStyle(
            "Section", fontName="Helvetica-Bold", fontSize=11,
            textColor=C_DARK, spaceBefore=8, spaceAfter=4,
        )

        story = []

        # ── Cover / Header ───────────────────────────────────────────────────
        story.append(Paragraph(
            f"SINGLE LINE DIAGRAM &amp; EQUIPMENT REPORT", title_style
        ))
        story.append(Paragraph(
            f"33/11 kV {_str(ss.get('name')).upper()} ELECTRICAL SUBSTATION", title_style
        ))
        story.append(Paragraph(
            f"Source Grid: {_str(ss.get('gss_primary'))}  |  "
            f"Circle: {_str(ss.get('circle'))}  |  "
            f"Region: {_str(ss.get('region'))}  |  "
            f"Type: {_str(ss.get('type'))}",
            sub_style,
        ))
        story.append(Paragraph(
            f"GPS: {_str(ss.get('gps', {}).get('lat'))}°N, "
            f"{_str(ss.get('gps', {}).get('lon'))}°E  |  "
            f"Report generated: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}",
            sub_style,
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=C_DARK, spaceAfter=8))

        # ── SLD (SVG as drawing) ─────────────────────────────────────────────
        story.append(Paragraph("SINGLE LINE DIAGRAM", section_style))
        try:
            from svglib.svglib import svg2rlg
            svg_buf = io.BytesIO(svg_string.encode("utf-8"))
            drawing = svg2rlg(svg_buf)
            if drawing:
                # Scale to fit page width
                page_w = landscape(A3)[0] - 30 * mm
                scale = min(page_w / drawing.width, 1.0)
                drawing.width  *= scale
                drawing.height *= scale
                drawing.transform = (scale, 0, 0, scale, 0, 0)
                story.append(drawing)
        except Exception as e:
            story.append(Paragraph(f"[SLD rendering skipped: {e}]", sub_style))

        story.append(PageBreak())

        # ── Transformer Table ────────────────────────────────────────────────
        story.append(Paragraph("POWER TRANSFORMER DETAILS", section_style))
        tr_data = [["#", "Capacity (MVA)", "Make", "YOM", "Max Load (MW)", "Max OTI (°C)", "Max WTI (°C)"]]
        for tr in transformers:
            tr_data.append([
                str(tr.get("sequence", "-")),
                _str(tr.get("capacity_mva")),
                _str(tr.get("make")),
                _str(tr.get("yom")),
                _str(tr.get("max_loading_mw")),
                _str(tr.get("max_oti_c")),
                _str(tr.get("max_wti_c")),
            ])
        story.append(self._table(tr_data))
        story.append(Spacer(1, 8 * mm))

        # ── Feeder Details Table ─────────────────────────────────────────────
        story.append(Paragraph("FEEDER & SWITCHGEAR DETAILS", section_style))
        fd_data = [[
            "Feeder Name", "Type", "kV",
            "Meter No.", "Meter Make", "CTR", "MF", "CT Status",
            "VCB Type", "Panel Make", "VCB Make", "YOM", "OC/EF Relay", "Status",
        ]]
        for fd in feeders:
            mt = fd.get("meter", {})
            sg = fd.get("switchgear", {})
            fd_data.append([
                fd.get("name", "-")[:28],
                fd.get("feeder_type", "-").replace("_", " "),
                str(fd.get("voltage_kv", "-")),
                _str(mt.get("number")),
                _str(mt.get("make")),
                _str(mt.get("ctr")),
                _str(mt.get("mf")),
                _str(mt.get("ct_status")),
                _str(sg.get("vcb_type")),
                _str(sg.get("panel_make")),
                _str(sg.get("vcb_make")),
                _str(sg.get("yom")),
                _str(sg.get("oc_ef_relay_type")),
                _str(sg.get("vcb_status")),
            ])
        story.append(self._table(fd_data, font_size=7))

        story.append(Spacer(1, 8 * mm))

        # ── DC Supply Table ──────────────────────────────────────────────────
        dc_rows = [fd for fd in feeders if fd.get("dc_supply", {}).get("charger_status")]
        if dc_rows:
            story.append(Paragraph("DC SUPPLY DETAILS", section_style))
            dc_data = [["Feeder", "Charger Status", "Charger Make", "YOM", "Battery Status", "Battery Type"]]
            for fd in dc_rows:
                dc = fd["dc_supply"]
                dc_data.append([
                    fd.get("name", "-")[:28],
                    _str(dc.get("charger_status")),
                    _str(dc.get("charger_make")),
                    _str(dc.get("charger_yom")),
                    _str(dc.get("battery_status")),
                    _str(dc.get("battery_type")),
                ])
            story.append(self._table(dc_data))

        doc.build(story)
        buf.seek(0)
        return buf.read()

    def _table(self, data, font_size=8):
        col_count = len(data[0])
        page_w = landscape(A3)[0] - 30 * mm
        col_w = page_w / col_count

        t = Table(data, colWidths=[col_w] * col_count, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), C_DARK),
            ("TEXTCOLOR",    (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), font_size),
            ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",     (0, 1), (-1, -1), font_size - 1),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREY]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ]))
        return t
