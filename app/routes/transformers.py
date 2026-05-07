from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import transformer_doc, audit_log_doc, utcnow
from bson import ObjectId

transformers_bp = Blueprint("transformers", __name__)


def _ser(t):
    t["_id"] = str(t["_id"])
    t["substation_id"] = str(t["substation_id"])
    return t


@transformers_bp.get("/substation/<ss_id>")
@jwt_required()
def list_transformers(ss_id):
    trs = list(mongo.db.transformers.find(
        {"substation_id": ObjectId(ss_id)}).sort("sequence", 1))
    return jsonify([_ser(t) for t in trs])


@transformers_bp.post("/substation/<ss_id>")
@jwt_required()
def create_transformer(ss_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    data = request.get_json(silent=True) or {}
    if not data.get("capacity_mva"):
        return jsonify(error="capacity_mva required"), 400

    # Auto-sequence
    last = mongo.db.transformers.find_one(
        {"substation_id": ObjectId(ss_id)},
        sort=[("sequence", -1)]
    )
    seq = (last["sequence"] + 1) if last else 1

    doc = transformer_doc(
        substation_id=ss_id,
        sequence=seq,
        capacity_mva=float(data["capacity_mva"]),
        make=data.get("make"),
        yom=data.get("yom"),
        max_loading_mw=data.get("max_loading_mw"),
        max_oti=data.get("max_oti_c"),
        max_wti=data.get("max_wti_c"),
    )
    res = mongo.db.transformers.insert_one(doc)
    return jsonify(id=str(res.inserted_id)), 201


@transformers_bp.put("/<tr_id>")
@jwt_required()
def update_transformer(tr_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    data = request.get_json(silent=True) or {}
    allowed = {"capacity_mva", "make", "yom", "max_loading_mw", "max_oti_c", "max_wti_c"}
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = utcnow()
    mongo.db.transformers.update_one({"_id": ObjectId(tr_id)}, {"$set": update})
    return jsonify(message="Updated")


@transformers_bp.delete("/<tr_id>")
@jwt_required()
def delete_transformer(tr_id):
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Insufficient permissions"), 403
    mongo.db.transformers.delete_one({"_id": ObjectId(tr_id)})
    return jsonify(message="Deleted")
