from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import substation_doc, audit_log_doc, utcnow
from bson import ObjectId
from app.routes.helpers import parse_object_id

substations_bp = Blueprint("substations", __name__)


def _serialize(doc):
    doc["_id"] = str(doc["_id"])
    return doc


def _require_roles(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify(error="Insufficient permissions"), 403
    return None


@substations_bp.get("/")
@jwt_required()
def list_substations():
    gss = request.args.get("gss")
    query = {"gss_primary": gss} if gss else {}
    docs = list(mongo.db.substations.find(query, {
        "_id": 1, "name": 1, "gss_primary": 1, "region": 1,
        "circle": 1, "type": 1, "gps": 1, "topology": 1,
    }).sort("name", 1))
    return jsonify([_serialize(d) for d in docs])


@substations_bp.get("/<ss_id>")
@jwt_required()
def get_substation(ss_id):
    try:
        doc = mongo.db.substations.find_one({"_id": ObjectId(ss_id)})
    except Exception:
        return jsonify(error="Invalid ID"), 400
    if not doc:
        return jsonify(error="Not found"), 404
    trs = list(mongo.db.transformers.find({"substation_id": ObjectId(ss_id)}).sort("sequence", 1))
    fds = list(mongo.db.feeders.find({"substation_id": ObjectId(ss_id)}).sort("sequence", 1))
    result = _serialize(doc)
    result["transformers"] = [{**t, "_id": str(t["_id"]), "substation_id": ss_id} for t in trs]
    result["feeders"] = [{**f, "_id": str(f["_id"]), "substation_id": ss_id,
                          "transformer_id": str(f["transformer_id"]) if f.get("transformer_id") else None}
                         for f in fds]
    return jsonify(result)


@substations_bp.post("/")
@jwt_required()
def create_substation():
    err = _require_roles("admin", "engineer")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify(error="name required"), 400
    if mongo.db.substations.find_one({"name": data["name"]}):
        return jsonify(error="Substation already exists"), 409
    doc = substation_doc(
        name=data["name"], region=data.get("region"),
        circle=data.get("circle"), tnc=data.get("tnc"),
        esd=data.get("esd"),
        gps_lat=data.get("gps_lat"), gps_lon=data.get("gps_lon"),
        sub_type=data.get("type", "Conventional"),
        gss_primary=data.get("gss_primary"),
        gss_alternate=data.get("gss_alternate"),
    )
    res = mongo.db.substations.insert_one(doc)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "create_substation", "substations", str(res.inserted_id))
    )
    return jsonify(id=str(res.inserted_id)), 201


@substations_bp.put("/<ss_id>")
@jwt_required()
def update_substation(ss_id):
    err = _require_roles("admin", "engineer")
    if err:
        return err
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    allowed = {"name","region","circle","tnc","esd","type","gss_primary","gss_alternate","tapping_info","lilo_info"}
    update = {k: v for k, v in data.items() if k in allowed}
    if "gps_lat" in data:
        update["gps.lat"] = data.get("gps_lat")
    if "gps_lon" in data:
        update["gps.lon"] = data.get("gps_lon")
    if not update:
        return jsonify(error="No valid fields"), 400
    update["updated_at"] = utcnow()
    result = mongo.db.substations.update_one({"_id": substation_id}, {"$set": update})
    if result.matched_count == 0:
        return jsonify(error="Substation not found"), 404
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "update_substation", "substations", ss_id)
    )
    return jsonify(message="Updated")


@substations_bp.delete("/<ss_id>")
@jwt_required()
def delete_substation(ss_id):
    err = _require_roles("admin")
    if err:
        return err
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    result = mongo.db.substations.delete_one({"_id": substation_id})
    if result.deleted_count == 0:
        return jsonify(error="Substation not found"), 404
    mongo.db.feeders.delete_many({"substation_id": substation_id})
    mongo.db.transformers.delete_many({"substation_id": substation_id})
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "delete_substation", "substations", ss_id)
    )
    return jsonify(message="Deleted")
