from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import feeder_doc, audit_log_doc, utcnow
from bson import ObjectId

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
    fds = list(mongo.db.feeders.find({"substation_id": ObjectId(ss_id)}).sort("sequence", 1))
    return jsonify([_ser(f) for f in fds])


@feeders_bp.post("/substation/<ss_id>")
@jwt_required()
def create_feeder(ss_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    data = request.get_json(silent=True) or {}
    doc = feeder_doc(
        substation_id=ss_id,
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
    res = mongo.db.feeders.insert_one(doc)
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
    data = request.get_json(silent=True) or {}
    update = {"updated_at": utcnow()}
    for field in ("name", "sequence", "voltage_kv", "feeder_type", "remarks"):
        if field in data:
            update[field] = data[field]
    for section in ("meter", "switchgear", "dc_supply"):
        if data.get(section):
            for k, v in data[section].items():
                update[f"{section}.{k}"] = v
    mongo.db.feeders.update_one({"_id": ObjectId(feeder_id)}, {"$set": update})
    return jsonify(message="Updated")


@feeders_bp.delete("/<feeder_id>")
@jwt_required()
def delete_feeder(feeder_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    mongo.db.feeders.delete_one({"_id": ObjectId(feeder_id)})
    return jsonify(message="Deleted")
