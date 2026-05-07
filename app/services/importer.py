"""
Excel / CSV import service.
Handles the 3-row merged header format from GECII feeder status data.
"""
import re
import pandas as pd
from bson import ObjectId
from datetime import datetime, timezone
from app.models import (
    utcnow, grid_substation_doc, substation_doc,
    transformer_doc, feeder_doc, infer_topology,
)


# ── Column index map (0-based) from the Excel structure ──────────────────────
COL = {
    "sn": 0, "region": 1, "circle": 2, "tnc": 3, "esd": 4,
    "ss_name": 5, "lat": 6, "lon": 7, "ss_type": 8,
    "gss_primary": 9, "gss_alternate": 10,
    "tapping_info": 11, "lilo_info": 12,
    "tr_capacity": 13, "tr_make": 14, "tr_yom": 15,
    "tr_max_load": 16, "tr_oti": 17, "tr_wti": 18,
    "feeder_name": 19, "feeder_voltage": 20,
    "meter_no": 21, "meter_make": 22, "meter_type": 23, "meter_status": 24,
    "ctr": 25, "mf": 26,
    "ct_type": 27, "ct_status": 28, "dcu_status": 29,
    "vcb_type": 30, "panel_make": 31, "vcb_status": 32, "vcb_make": 33,
    "vcb_yom": 34, "oc_ef_relay": 35, "diff_relay": 36,
    "relay_make": 37, "diff_relay_make": 38,
    "diff_relay_status": 39, "oc_ef_relay_status": 40,
    "aux_relay_status": 41, "year_commissioned": 42,
    "remarks": 43,
    "charger_status": 44, "charger_make": 45, "charger_yom": 46,
    "battery_status": 47, "battery_type": 48,
}


def _val(row, key):
    """Safe cell value retrieval — returns None for NaN/empty."""
    try:
        v = row.iloc[COL[key]]
        if pd.isna(v):
            return None
        v = str(v).strip()
        return v if v else None
    except (IndexError, KeyError):
        return None


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
    """Determine feeder_type from name and voltage string."""
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
            if raw.empty or raw.shape[0] < 4:
                continue
            # Data starts at row index 3 (0-based), skip 3 header rows
            data = raw.iloc[3:].reset_index(drop=True)
            if data.empty:
                continue
            try:
                s = self._import_sheet(data, user_id, sheet_name)
                summary["substations"] += s["substations"]
                summary["transformers"] += s["transformers"]
                summary["feeders"] += s["feeders"]
                summary["errors"].extend(s["errors"])
            except Exception as e:
                summary["errors"].append(f"Sheet '{sheet_name}': {e}")

        return summary

    def _import_sheet(self, data: pd.DataFrame, user_id: str, sheet_name: str) -> dict:
        summary = {"substations": 0, "transformers": 0, "feeders": 0, "errors": []}
        current_ss = None        # current substation dict
        current_ss_id = None
        current_tr = None        # current transformer doc
        current_tr_id = None
        tr_seq = 0
        feeder_seq = 0
        all_feeders = []         # for topology inference

        for idx, row in data.iterrows():
            ss_name = _val(row, "ss_name")
            tr_cap = _val(row, "tr_capacity")
            feeder_name = _val(row, "feeder_name")
            feeder_volt = _val(row, "feeder_voltage")

            # ── New substation block ─────────────────────────────────────────
            if ss_name:
                # Finalize previous substation topology
                if current_ss_id and all_feeders:
                    topo = infer_topology(all_feeders)
                    self.db.substations.update_one(
                        {"_id": current_ss_id},
                        {"$set": {"topology": topo, "updated_at": utcnow()}}
                    )

                lat = _dms_to_decimal(_val(row, "lat"))
                lon = _dms_to_decimal(_val(row, "lon"))
                gss = _val(row, "gss_primary")

                # Upsert GSS
                if gss:
                    self.db.grid_substations.update_one(
                        {"name": gss},
                        {"$setOnInsert": grid_substation_doc(gss)},
                        upsert=True,
                    )

                ss_doc = substation_doc(
                    name=ss_name,
                    region=_val(row, "region"),
                    circle=_val(row, "circle"),
                    tnc=_val(row, "tnc"),
                    esd=_val(row, "esd"),
                    gps_lat=lat, gps_lon=lon,
                    sub_type=_val(row, "ss_type") or "Conventional",
                    gss_primary=gss,
                    gss_alternate=_val(row, "gss_alternate"),
                    tapping_info=_val(row, "tapping_info"),
                    lilo_info=_val(row, "lilo_info"),
                )

                result = self.db.substations.find_one_and_update(
                    {"name": ss_name},
                    {"$set": {**ss_doc, "updated_at": utcnow()}},
                    upsert=True,
                    return_document=True,
                )
                if result:
                    current_ss_id = result["_id"]
                else:
                    current_ss_id = self.db.substations.find_one({"name": ss_name})["_id"]

                # Delete existing feeders/transformers for this substation (overwrite)
                self.db.feeders.delete_many({"substation_id": current_ss_id})
                self.db.transformers.delete_many({"substation_id": current_ss_id})

                current_ss = ss_name
                current_tr = None
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
                    make=_val(row, "tr_make"),
                    yom=_safe_int(_val(row, "tr_yom")),
                    max_loading_mw=_safe_float(_val(row, "tr_max_load")),
                    max_oti=_safe_float(_val(row, "tr_oti")),
                    max_wti=_safe_float(_val(row, "tr_wti")),
                )
                res = self.db.transformers.insert_one(tr_doc)
                current_tr_id = res.inserted_id
                summary["transformers"] += 1

            # ── Feeder row ───────────────────────────────────────────────────
            if feeder_name and current_ss_id:
                feeder_seq += 1
                ftype = _classify_feeder(feeder_name, feeder_volt)
                if not ftype:
                    continue

                volt_kv = 11
                if feeder_volt:
                    m = re.search(r"(\d+)", str(feeder_volt))
                    if m:
                        volt_kv = int(m.group(1))

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
                # Meter
                fd["meter"].update({
                    "number": _val(row, "meter_no"),
                    "make": _val(row, "meter_make"),
                    "meter_type": _val(row, "meter_type"),
                    "status": _val(row, "meter_status"),
                    "ctr": _val(row, "ctr"),
                    "mf": _safe_float(_val(row, "mf")),
                    "ct_type": _val(row, "ct_type"),
                    "ct_status": _val(row, "ct_status"),
                    "dcu_status": _val(row, "dcu_status"),
                })
                # Switchgear
                fd["switchgear"].update({
                    "vcb_type": _val(row, "vcb_type"),
                    "panel_make": _val(row, "panel_make"),
                    "vcb_status": _val(row, "vcb_status"),
                    "vcb_make": _val(row, "vcb_make"),
                    "yom": _safe_int(_val(row, "vcb_yom")),
                    "oc_ef_relay_type": _val(row, "oc_ef_relay"),
                    "diff_relay_type": _val(row, "diff_relay"),
                    "relay_make": _val(row, "relay_make"),
                    "diff_relay_make": _val(row, "diff_relay_make"),
                    "diff_relay_status": _val(row, "diff_relay_status"),
                    "oc_ef_relay_status": _val(row, "oc_ef_relay_status"),
                    "aux_relay_status": _val(row, "aux_relay_status"),
                    "year_commissioned": _safe_int(_val(row, "year_commissioned")),
                })
                # DC Supply (substation-level, stored per row if present)
                charger_status = _val(row, "charger_status")
                if charger_status:
                    fd["dc_supply"].update({
                        "charger_status": charger_status,
                        "charger_make": _val(row, "charger_make"),
                        "charger_yom": _safe_int(_val(row, "charger_yom")),
                        "battery_status": _val(row, "battery_status"),
                        "battery_type": _val(row, "battery_type"),
                    })
                fd["remarks"] = _val(row, "remarks")

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
