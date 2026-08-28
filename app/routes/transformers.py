from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import transformer_doc, audit_log_doc, utcnow
from bson import ObjectId
from app.routes.helpers import (
    parse_object_id,
    refresh_substation_topology,
    transformer_substation_id,
)

transformers_bp = Blueprint("transformers", __name__)


def _ser(t):
    t["_id"] = str(t["_id"])
    t["substation_id"] = str(t["substation_id"])
    return t


@transformers_bp.get("/substation/<ss_id>")
@jwt_required()
def list_transformers(ss_id):
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    trs = list(mongo.db.transformers.find(
        {"substation_id": substation_id}).sort("sequence", 1))
    return jsonify([_ser(t) for t in trs])


@transformers_bp.post("/substation/<ss_id>")
@jwt_required()
def create_transformer(ss_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    data = request.get_json(silent=True) or {}
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    if not mongo.db.substations.find_one({"_id": substation_id}, {"_id": 1}):
        return jsonify(error="Substation not found"), 404
    if not data.get("capacity_mva"):
        return jsonify(error="capacity_mva required"), 400

    # Auto-sequence
    last = mongo.db.transformers.find_one(
        {"substation_id": substation_id},
        sort=[("sequence", -1)]
    )
    seq = (last["sequence"] + 1) if last else 1

    doc = transformer_doc(
        substation_id=substation_id,
        sequence=seq,
        capacity_mva=float(data["capacity_mva"]),
        make=data.get("make"),
        yom=data.get("yom"),
        max_loading_mw=data.get("max_loading_mw"),
        max_oti=data.get("max_oti_c"),
        max_wti=data.get("max_wti_c"),
    )
    res = mongo.db.transformers.insert_one(doc)
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "create_transformer", "transformers", str(res.inserted_id))
    )
    return jsonify(id=str(res.inserted_id)), 201


@transformers_bp.put("/<tr_id>")
@jwt_required()
def update_transformer(tr_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    transformer_id, err = parse_object_id(tr_id, "transformer ID")
    if err:
        return err
    substation_id = transformer_substation_id(transformer_id)
    if not substation_id:
        return jsonify(error="Transformer not found"), 404
    data = request.get_json(silent=True) or {}
    allowed = {"capacity_mva", "make", "yom", "max_loading_mw", "max_oti_c", "max_wti_c"}
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = utcnow()
    mongo.db.transformers.update_one({"_id": transformer_id}, {"$set": update})
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "update_transformer", "transformers", tr_id)
    )
    return jsonify(message="Updated")


@transformers_bp.delete("/<tr_id>")
@jwt_required()
def delete_transformer(tr_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    transformer_id, err = parse_object_id(tr_id, "transformer ID")
    if err:
        return err
    substation_id = transformer_substation_id(transformer_id)
    if not substation_id:
        return jsonify(error="Transformer not found"), 404
    mongo.db.transformers.delete_one({"_id": transformer_id})
    refresh_substation_topology(substation_id)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "delete_transformer", "transformers", tr_id)
    )
    return jsonify(message="Deleted")
