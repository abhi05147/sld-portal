"""
MongoDB document schemas as Python dataclasses + helper functions.
No ORM — raw PyMongo with typed dicts for clarity.
"""
from datetime import datetime, timezone
from bson import ObjectId


def utcnow():
    return datetime.now(timezone.utc)


# ── Grid Substation (132/33kV source) ────────────────────────────────────────

def grid_substation_doc(name: str, voltage_kv: int = 132) -> dict:
    return {
        "name": name,
        "voltage_kv": voltage_kv,
        "created_at": utcnow(),
    }


# ── Substation (33/11kV) ──────────────────────────────────────────────────────

def substation_doc(
    name, region, circle, tnc, esd,
    gps_lat, gps_lon, sub_type,
    gss_primary, gss_alternate=None,
    tapping_info=None, lilo_info=None,
) -> dict:
    return {
        "name": name,
        "region": region,
        "circle": circle,
        "tnc": tnc,
        "esd": esd,
        "gps": {"lat": gps_lat, "lon": gps_lon},
        "type": sub_type,                        # Conventional / Compact
        "gss_primary": gss_primary,
        "gss_alternate": gss_alternate,
        "tapping_info": tapping_info,
        "lilo_info": lilo_info,
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
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


# ── Power Transformer ─────────────────────────────────────────────────────────

def transformer_doc(substation_id, sequence, capacity_mva, make, yom,
                    max_loading_mw=None, max_oti=None, max_wti=None) -> dict:
    return {
        "substation_id": ObjectId(substation_id),
        "sequence": sequence,                    # 1, 2, ...
        "capacity_mva": capacity_mva,
        "make": make,
        "yom": yom,
        "max_loading_mw": max_loading_mw,
        "max_oti_c": max_oti,
        "max_wti_c": max_wti,
        "is_station_transformer": False,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


# ── Feeder ────────────────────────────────────────────────────────────────────
# feeder_type: "incoming_33kv" | "outgoing_33kv" | "transformer_hv" | "station_transformer"
#            | "incomer_11kv" | "outgoing_11kv" | "bus_coupler"

def feeder_doc(substation_id, transformer_id=None, sequence=0,
               name="", voltage_kv=11, feeder_type="outgoing_11kv") -> dict:
    return {
        "substation_id": ObjectId(substation_id),
        "transformer_id": ObjectId(transformer_id) if transformer_id else None,
        "sequence": sequence,
        "name": name,
        "voltage_kv": voltage_kv,
        "feeder_type": feeder_type,
        "meter": {
            "number": None, "make": None, "meter_type": None,
            "status": None, "ctr": None, "mf": None,
            "ct_type": None, "ct_status": None,
            "pt_type": None, "pt_status": None,
            "dcu_status": None,
        },
        "switchgear": {
            "vcb_type": None, "panel_make": None, "vcb_status": None,
            "vcb_make": None, "yom": None,
            "oc_ef_relay_type": None, "diff_relay_type": None,
            "relay_make": None, "diff_relay_make": None,
            "diff_relay_status": None, "oc_ef_relay_status": None,
            "aux_relay_status": None, "year_commissioned": None,
        },
        "dc_supply": {
            "charger_status": None, "charger_make": None, "charger_yom": None,
            "battery_status": None, "battery_type": None,
        },
        "remarks": None,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


# ── User ──────────────────────────────────────────────────────────────────────

def user_doc(username, email, password_hash, role, created_by_id=None) -> dict:
    return {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "role": role,                            # admin | engineer | viewer
        "is_active": True,
        "created_by": ObjectId(created_by_id) if created_by_id else None,
        "created_at": utcnow(),
        "last_login": None,
        "password_reset_required": False,
    }


# ── Audit Log ─────────────────────────────────────────────────────────────────

def audit_log_doc(user_id, action, target_collection=None,
                  target_id=None, detail=None) -> dict:
    return {
        "user_id": ObjectId(user_id),
        "action": action,
        "target_collection": target_collection,
        "target_id": ObjectId(target_id) if target_id else None,
        "detail": detail,
        "timestamp": utcnow(),
    }


# ── Topology inference ────────────────────────────────────────────────────────

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
