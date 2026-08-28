from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import feeder_doc, audit_log_doc, utcnow
from bson import ObjectId
from app.routes.helpers import (
    feeder_substation_id,
    parse_object_id,
    refresh_substation_topology,
)

feeders_bp = Blueprint("feeders", __name__)


def _ser(f):
    f["_id"] = str(f["_id"])
    f["substation_id"] = str(f["substation_id"])
    if f.get("transformer_id"):
        f["transformer_id"] = str(f["transformer_id"])
    return f


@feeders_bp.get("/substation/<ss_id>")
@jwt_required()
def list_feeders(ss_id):
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    fds = list(mongo.db.feeders.find({"substation_id": substation_id}).sort("sequence", 1))
    return jsonify([_ser(f) for f in fds])


@feeders_bp.post("/substation/<ss_id>")
@jwt_required()
def create_feeder(ss_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    data = request.get_json(silent=True) or {}
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    if not mongo.db.substations.find_one({"_id": substation_id}, {"_id": 1}):
        return jsonify(error="Substation not found"), 404
    doc = feeder_doc(
        substation_id=substation_id,
        transformer_id=data.get("transformer_id"),
        sequence=data.get("sequence", 99),
        name=data.get("name", ""),
        voltage_kv=data.get("voltage_kv", 11),
        feeder_type=data.get("feeder_type", "outgoing_11kv"),
    )
    for section in ("meter", "switchgear", "dc_supply"):
        if data.get(section):
            doc[section].update(data[section])
    doc["remarks"] = data.get("remarks")
    if "is_autorecloser" in data:
        doc["is_autorecloser"] = bool(data["is_autorecloser"])
    res = mongo.db.feeders.insert_one(doc)
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "create_feeder", "feeders", str(res.inserted_id))
    )
    return jsonify(id=str(res.inserted_id)), 201


@feeders_bp.put("/<feeder_id>")
@jwt_required()
def update_feeder(feeder_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    fid, err = parse_object_id(feeder_id, "feeder ID")
    if err:
        return err
    substation_id = feeder_substation_id(fid)
    if not substation_id:
        return jsonify(error="Feeder not found"), 404
    data = request.get_json(silent=True) or {}
    update = {"updated_at": utcnow()}
    for field in ("name", "sequence", "voltage_kv", "feeder_type", "remarks", "is_autorecloser"):
        if field in data:
            update[field] = data[field]
    for section in ("meter", "switchgear", "dc_supply"):
        if data.get(section):
            for k, v in data[section].items():
                update[f"{section}.{k}"] = v
    mongo.db.feeders.update_one({"_id": fid}, {"$set": update})
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "update_feeder", "feeders", feeder_id)
    )
    return jsonify(message="Updated")


@feeders_bp.delete("/<feeder_id>")
@jwt_required()
def delete_feeder(feeder_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    fid, err = parse_object_id(feeder_id, "feeder ID")
    if err:
        return err
    substation_id = feeder_substation_id(fid)
    if not substation_id:
        return jsonify(error="Feeder not found"), 404
    mongo.db.feeders.delete_one({"_id": fid})
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "delete_feeder", "feeders", feeder_id)
    )
    return jsonify(message="Deleted")
