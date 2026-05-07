from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo, bcrypt
from app.models import audit_log_doc
from bson import ObjectId

users_bp = Blueprint("users", __name__)


def _ser(u):
    return {
        "id": str(u["_id"]),
        "username": u.get("username"),
        "email": u.get("email"),
        "role": u.get("role"),
        "is_active": u.get("is_active"),
        "last_login": u.get("last_login").isoformat() if u.get("last_login") else None,
        "created_at": u.get("created_at").isoformat() if u.get("created_at") else None,
        "password_reset_required": u.get("password_reset_required", False),
    }


def _admin_required():
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify(error="Admin access required"), 403
    return None


@users_bp.get("/")
@jwt_required()
def list_users():
    err = _admin_required()
    if err:
        return err
    users = list(mongo.db.users.find({}, {"password_hash": 0}))
    return jsonify([_ser(u) for u in users])


@users_bp.patch("/<user_id>")
@jwt_required()
def patch_user(user_id):
    err = _admin_required()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    update = {}
    if "is_active" in data:
        update["is_active"] = bool(data["is_active"])
    if "role" in data and data["role"] in ("admin", "engineer", "viewer"):
        update["role"] = data["role"]
    if not update:
        return jsonify(error="No valid fields"), 400
    mongo.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update})
    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "patch_user", "users", user_id, str(update))
    )
    return jsonify(message="Updated")


@users_bp.post("/<user_id>/reset-password")
@jwt_required()
def reset_password(user_id):
    err = _admin_required()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400
    pw_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": pw_hash, "password_reset_required": True}}
    )
    return jsonify(message="Password reset")
