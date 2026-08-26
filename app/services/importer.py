"""
Excel / CSV import service.
Reads a single header row (see app.services.import_schema.FIELD_HEADERS)
followed by one row per feeder; substation and transformer details repeat
on the first feeder row of each block.
"""
import re
import pandas as pd
from app.models import (
    utcnow, grid_substation_doc, substation_doc,
    transformer_doc, feeder_doc, infer_topology,
)
from app.services.import_schema import FIELD_HEADERS, REQUIRED_FIELDS

FEEDER_TYPE_MAP = {
    "substation incomer": "incoming_33kv",
    "transformer incomer": "transformer_hv",
    "transformer outgoing": "incomer_11kv",
    "outgoing feeder": "outgoing_11kv",
}

STATUS_VALUES = ["Working", "Defective", "Not Available"]
TYPE_VALUES = ["Indoor", "Outdoor", "Panel Mounted", "Autorecloser", "CTPT"]
METER_TYPE_VALUES = ["DLMS", "Non-DLMS"]
SS_TYPE_VALUES = ["Conventional", "Compact"]
BATTERY_TYPE_VALUES = ["VRLA", "Lead Acid"]


def _norm_header(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _resolve_columns(header_row):
    """Map field_key -> column index by matching header text (order-independent)."""
    lookup = {_norm_header(h): i for i, h in enumerate(header_row) if h is not None}
    col_map = {}
    for field_key, header_text in FIELD_HEADERS:
        idx = lookup.get(_norm_header(header_text))
        if idx is not None:
            col_map[field_key] = idx
    missing = [
        header_text for field_key, header_text in FIELD_HEADERS
        if field_key in REQUIRED_FIELDS and field_key not in col_map
    ]
    if missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found headers: {[h for h in header_row if h is not None]}"
        )
    return col_map


def _val(row, col_map, key):
    """Safe cell value retrieval — returns None for NaN/empty/absent columns."""
    idx = col_map.get(key)
    if idx is None:
        return None
    try:
        v = row.iloc[idx]
        if pd.isna(v):
            return None
        v = str(v).strip()
        return v if v else None
    except IndexError:
        return None


def _norm_enum(value, canonical):
    """Strip/collapse whitespace; snap to canonical casing on case-insensitive match."""
    if value is None:
        return None
    v = re.sub(r"\s+", " ", str(value)).strip()
    if not v:
        return None
    for c in canonical:
        if v.lower() == c.lower():
            return c
    return v


def _dms_to_decimal(dms_str):
    """Convert '26° 11' 2.09\"N' → 26.1839"""
    if not dms_str:
        return None
    try:
        nums = re.findall(r"[\d.]+", str(dms_str))
        if len(nums) < 3:
            return float(nums[0]) if nums else None
        deg, mn, sec = float(nums[0]), float(nums[1]), float(nums[2])
        val = deg + mn / 60 + sec / 3600
        if "S" in str(dms_str).upper() or "W" in str(dms_str).upper():
            val = -val
        return round(val, 6)
    except Exception:
        return None


def _classify_feeder(name, voltage_str):
    """Fallback feeder_type heuristic, used when the Feeder Type column is blank/unrecognized."""
    if not name:
        return None
    n = name.lower()
    v = str(voltage_str or "").lower()
    if "station" in n or "auxiliary" in n or "aux" in n:
        return "station_transformer"
    if "bus coupler" in n or "bus-coupler" in n or "bc" == n:
        return "bus_coupler"
    if "incomer" in n or "i/c" in n or "incoming" in n:
        if "33" in v:
            return "incoming_33kv"
        return "incomer_11kv"
    if "power transformer" in n or "ptr" in n or ("33/11" in v and "transformer" in n):
        return "transformer_hv"
    if "33" in v and ("incomer" in n or "i/c" in n or "feeder" not in n):
        return "incoming_33kv"
    return "outgoing_11kv"


def _resolve_feeder_type(name, raw_type, voltage):
    """Bus-coupler name always wins (source data mislabels these); else the
    explicit Feeder Type column; else fall back to the name/voltage heuristic."""
    if name and "coupler" in name.lower():
        return "bus_coupler"
    if raw_type:
        mapped = FEEDER_TYPE_MAP.get(str(raw_type).strip().lower())
        if mapped:
            return mapped
    return _classify_feeder(name, voltage)


def _safe_float(v):
    try:
        return float(str(v).replace(",", "").strip()) if v else None
    except Exception:
        return None


def _safe_int(v):
    try:
        return int(str(v).strip().split(".")[0]) if v else None
    except Exception:
        return None


class ExcelImporter:
    def __init__(self, db):
        self.db = db

    def import_file(self, filepath_or_buffer, user_id: str) -> dict:
        """
        Parse Excel and upsert all data into MongoDB.
        Returns summary dict: {substations, transformers, feeders, errors}
        """
        xl = pd.read_excel(filepath_or_buffer, sheet_name=None, header=None)
        summary = {"substations": 0, "transformers": 0, "feeders": 0, "errors": []}

        for sheet_name, raw in xl.items():
            if raw.empty or raw.shape[0] < 2:
                continue
            header_row = raw.iloc[0].tolist()
            try:
                col_map = _resolve_columns(header_row)
            except ValueError as e:
                summary["errors"].append(f"Sheet '{sheet_name}': {e}")
                continue
            data = raw.iloc[1:].reset_index(drop=True)
            if data.empty:
                continue
            try:
                s = self._import_sheet(data, col_map, user_id, sheet_name)
                summary["substations"] += s["substations"]
                summary["transformers"] += s["transformers"]
                summary["feeders"] += s["feeders"]
                summary["errors"].extend(s["errors"])
            except Exception as e:
                summary["errors"].append(f"Sheet '{sheet_name}': {e}")

        return summary

    def _import_sheet(self, data: pd.DataFrame, col_map: dict, user_id: str, sheet_name: str) -> dict:
        summary = {"substations": 0, "transformers": 0, "feeders": 0, "errors": []}
        current_ss_id = None
        current_tr_id = None
        tr_seq = 0
        feeder_seq = 0
        all_feeders = []         # for topology inference

        for idx, row in data.iterrows():
            ss_name = _val(row, col_map, "ss_name")
            tr_cap = _val(row, col_map, "tr_capacity")
            feeder_name = _val(row, col_map, "feeder_name")
            feeder_volt = _val(row, col_map, "feeder_voltage")

            # ── New substation block ─────────────────────────────────────────
            if ss_name:
                # Finalize previous substation topology
                if current_ss_id and all_feeders:
                    topo = infer_topology(all_feeders)
                    self.db.substations.update_one(
                        {"_id": current_ss_id},
                        {"$set": {"topology": topo, "updated_at": utcnow()}}
                    )

                esd = _val(row, col_map, "esd")
                gss = _val(row, col_map, "gss_primary")
                lat = _dms_to_decimal(_val(row, col_map, "lat"))
                lon = _dms_to_decimal(_val(row, col_map, "lon"))

                # Upsert GSS
                if gss:
                    self.db.grid_substations.update_one(
                        {"name": gss},
                        {"$setOnInsert": grid_substation_doc(gss)},
                        upsert=True,
                    )

                ss_doc = substation_doc(
                    name=ss_name,
                    region=_val(row, col_map, "region"),
                    circle=_val(row, col_map, "circle"),
                    tnc=_val(row, col_map, "tnc"),
                    esd=esd,
                    gps_lat=lat, gps_lon=lon,
                    sub_type=_norm_enum(_val(row, col_map, "ss_type"), SS_TYPE_VALUES) or "Conventional",
                    gss_primary=gss,
                    gss_alternate=_val(row, col_map, "gss_alternate"),
                    tapping_info=_val(row, col_map, "tapping_info"),
                    lilo_info=_val(row, col_map, "lilo_info"),
                )

                # Identify the substation by name + ESD + primary GSS: the
                # source data reuses substation names across genuinely
                # different sites (e.g. two "Jail Road" substations).
                ss_key = {"name": ss_name, "esd": esd, "gss_primary": gss}
                result = self.db.substations.find_one_and_update(
                    ss_key,
                    {"$set": {**ss_doc, "updated_at": utcnow()}},
                    upsert=True,
                    return_document=True,
                )
                if result:
                    current_ss_id = result["_id"]
                else:
                    current_ss_id = self.db.substations.find_one(ss_key)["_id"]

                # Delete existing feeders/transformers for this substation (overwrite)
                self.db.feeders.delete_many({"substation_id": current_ss_id})
                self.db.transformers.delete_many({"substation_id": current_ss_id})

                current_tr_id = None
                tr_seq = 0
                feeder_seq = 0
                all_feeders = []
                summary["substations"] += 1

            # ── New transformer block ────────────────────────────────────────
            if tr_cap and current_ss_id:
                tr_seq += 1
                tr_doc = transformer_doc(
                    substation_id=current_ss_id,
                    sequence=tr_seq,
                    capacity_mva=_safe_float(tr_cap),
                    make=_val(row, col_map, "tr_make"),
                    yom=_safe_int(_val(row, col_map, "tr_yom")),
                    max_loading_mw=_safe_float(_val(row, col_map, "tr_max_load")),
                    max_oti=_safe_float(_val(row, col_map, "tr_oti")),
                    max_wti=_safe_float(_val(row, col_map, "tr_wti")),
                )
                res = self.db.transformers.insert_one(tr_doc)
                current_tr_id = res.inserted_id
                summary["transformers"] += 1

            # ── Feeder row ───────────────────────────────────────────────────
            if feeder_name and current_ss_id:
                feeder_seq += 1
                feeder_type_raw = _val(row, col_map, "feeder_type_raw")
                ftype = _resolve_feeder_type(feeder_name, feeder_type_raw, feeder_volt)
                if not ftype:
                    continue

                volt_kv = 11
                if feeder_volt:
                    m = re.search(r"(\d+)", str(feeder_volt))
                    if m:
                        volt_kv = int(m.group(1))

                vcb_type = _norm_enum(_val(row, col_map, "vcb_type"), TYPE_VALUES)

                fd = feeder_doc(
                    substation_id=current_ss_id,
                    transformer_id=current_tr_id if ftype in (
                        "incomer_11kv", "outgoing_11kv", "transformer_hv"
                    ) else None,
                    sequence=feeder_seq,
                    name=feeder_name,
                    voltage_kv=volt_kv,
                    feeder_type=ftype,
                )
                fd["is_autorecloser"] = (vcb_type == "Autorecloser")
                # Meter
                fd["meter"].update({
                    "number": _val(row, col_map, "meter_no"),
                    "make": _val(row, col_map, "meter_make"),
                    "meter_type": _norm_enum(_val(row, col_map, "meter_type"), METER_TYPE_VALUES),
                    "status": _norm_enum(_val(row, col_map, "meter_status"), STATUS_VALUES),
                    "ctr": _val(row, col_map, "ctr"),
                    "mf": _safe_float(_val(row, col_map, "mf")),
                    "ct_type": _norm_enum(_val(row, col_map, "ct_type"), TYPE_VALUES),
                    "ct_status": _norm_enum(_val(row, col_map, "ct_status"), STATUS_VALUES),
                    "pt_type": _norm_enum(_val(row, col_map, "pt_type"), TYPE_VALUES),
                    "pt_status": _norm_enum(_val(row, col_map, "pt_status"), STATUS_VALUES),
                    "dcu_status": _norm_enum(_val(row, col_map, "dcu_status"), STATUS_VALUES),
                })
                # Switchgear
                fd["switchgear"].update({
                    "vcb_type": vcb_type,
                    "panel_make": _val(row, col_map, "panel_make"),
                    "vcb_status": _norm_enum(_val(row, col_map, "vcb_status"), STATUS_VALUES),
                    "vcb_make": _val(row, col_map, "vcb_make"),
                    "yom": _safe_int(_val(row, col_map, "vcb_yom")),
                    "oc_ef_relay_type": _val(row, col_map, "oc_ef_relay"),
                    "diff_relay_type": _val(row, col_map, "diff_relay"),
                    "relay_make": _val(row, col_map, "relay_make"),
                    "diff_relay_make": _val(row, col_map, "diff_relay_make"),
                    "diff_relay_status": _norm_enum(_val(row, col_map, "diff_relay_status"), STATUS_VALUES),
                    "oc_ef_relay_status": _norm_enum(_val(row, col_map, "oc_ef_relay_status"), STATUS_VALUES),
                    "aux_relay_status": _norm_enum(_val(row, col_map, "aux_relay_status"), STATUS_VALUES),
                    "year_commissioned": _safe_int(_val(row, col_map, "year_commissioned")),
                })
                # DC Supply (substation-level, stored per row if present)
                charger_status = _norm_enum(_val(row, col_map, "charger_status"), STATUS_VALUES)
                if charger_status:
                    fd["dc_supply"].update({
                        "charger_status": charger_status,
                        "charger_make": _val(row, col_map, "charger_make"),
                        "charger_yom": _safe_int(_val(row, col_map, "charger_yom")),
                        "battery_status": _norm_enum(_val(row, col_map, "battery_status"), STATUS_VALUES),
                        "battery_type": _norm_enum(_val(row, col_map, "battery_type"), BATTERY_TYPE_VALUES),
                    })
                fd["remarks"] = _val(row, col_map, "remarks")

                self.db.feeders.insert_one(fd)
                all_feeders.append(fd)
                summary["feeders"] += 1

        # Finalize last substation topology
        if current_ss_id and all_feeders:
            topo = infer_topology(all_feeders)
            self.db.substations.update_one(
                {"_id": current_ss_id},
                {"$set": {"topology": topo, "updated_at": utcnow()}}
            )

        return summary
