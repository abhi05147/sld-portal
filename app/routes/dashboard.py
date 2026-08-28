from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app import mongo
from bson import ObjectId

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/stats")
@jwt_required()
def stats():
    db = mongo.db
    total_ss     = db.substations.count_documents({})
    total_33_inc = db.feeders.count_documents({"feeder_type": "incoming_33kv"})
    total_11_out = db.feeders.count_documents({"feeder_type": "outgoing_11kv"})
    total_tr     = db.transformers.count_documents({})

    cap_res = list(db.transformers.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$capacity_mva"}}}
    ]))
    total_cap = cap_res[0]["total"] if cap_res else 0

    region_breakdown = [
        {"region": r["_id"] or "Unknown", "count": r["count"]}
        for r in db.substations.aggregate([
            {"$group": {"_id": "$region", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])
    ]

    ss_map = list(db.substations.find(
        {},
        {"_id": 1, "name": 1, "gps": 1, "gss_primary": 1, "type": 1, "topology": 1}
    ))
    for s in ss_map:
        s["_id"] = str(s["_id"])

    return jsonify(
        total_substations=total_ss,
        total_33kv_incoming=total_33_inc,
        total_11kv_outgoing=total_11_out,
        total_transformers=total_tr,
        total_capacity_mva=round(float(total_cap), 2),
        region_breakdown=region_breakdown,
        substations_map=ss_map,
    )


@dashboard_bp.get("/hierarchy")
@jwt_required()
def hierarchy():
    db = mongo.db
    gss_list = list(db.grid_substations.find({}, {"_id": 1, "name": 1}))
    result = []
    linked_names = set()

    for gss in gss_list:
        subs = list(db.substations.find(
            {"gss_primary": gss["name"]},
            {"_id": 1, "name": 1, "topology": 1, "type": 1}
        ))
        if not subs:
            continue
        for s in subs:
            sid = str(s["_id"])
            s["_id"] = sid
            linked_names.add(s["name"])
            fds = list(db.feeders.find(
                {"substation_id": ObjectId(sid), "feeder_type": "outgoing_11kv"},
                {"_id": 1, "name": 1, "voltage_kv": 1}
            ))
            s["feeders"] = [{"id": str(f["_id"]), "name": f["name"]} for f in fds]
        result.append({"gss_id": str(gss["_id"]), "gss_name": gss["name"], "substations": subs})

    # Substations whose GSS is not in grid_substations collection
    unlinked = list(db.substations.find(
        {"name": {"$nin": list(linked_names)}},
        {"_id": 1, "name": 1, "gss_primary": 1, "topology": 1, "type": 1}
    ))
    grouped = {}
    for s in unlinked:
        g = s.get("gss_primary") or "Unknown Grid"
        grouped.setdefault(g, []).append({
            "_id": str(s["_id"]), "name": s["name"],
            "topology": s.get("topology"), "type": s.get("type"), "feeders": []
        })
    for g, subs in grouped.items():
        result.append({"gss_id": None, "gss_name": g, "substations": subs})

    return jsonify(result)
