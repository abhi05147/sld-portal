from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
)
from app import mongo, bcrypt
from app.models import user_doc, audit_log_doc, utcnow
from bson import ObjectId
import re

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_payload(u):
    return {
        "id": str(u["_id"]),
        "username": u["username"],
        "email": u["email"],
        "role": u["role"],
        "is_active": u["is_active"],
    }


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify(error="Username and password required"), 400

    user = mongo.db.users.find_one({"username": username})
    if not user or not bcrypt.check_password_hash(user["password_hash"], password):
        return jsonify(error="Invalid credentials"), 401
    if not user.get("is_active"):
        return jsonify(error="Account disabled. Contact administrator."), 403

    access  = create_access_token(identity=str(user["_id"]),
                                  additional_claims={"role": user["role"]})
    refresh = create_refresh_token(identity=str(user["_id"]))
    mongo.db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": utcnow()}})
    mongo.db.audit_logs.insert_one(audit_log_doc(str(user["_id"]), "login"))

    return jsonify(access_token=access, refresh_token=refresh, user=_user_payload(user))


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({"_id": ObjectId(uid)})
    if not user or not user.get("is_active"):
        return jsonify(error="Account disabled"), 403
    access = create_access_token(identity=uid,
                                 additional_claims={"role": user["role"]})
    return jsonify(access_token=access)


@auth_bp.post("/register")
@jwt_required()
def register():
    """Admin-only: create new user."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify(error="Admin access required"), 403

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role     = (data.get("role") or "viewer").lower()

    if not username or not email or not password:
        return jsonify(error="username, email, password required"), 400
    if role not in ("admin", "engineer", "viewer"):
        return jsonify(error="Invalid role"), 400
    if not EMAIL_RE.match(email):
        return jsonify(error="Invalid email"), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400

    if mongo.db.users.find_one({"username": username}):
        return jsonify(error="Username already exists"), 409
    if mongo.db.users.find_one({"email": email}):
        return jsonify(error="Email already registered"), 409

    creator_id = get_jwt_identity()
    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    doc = user_doc(username, email, pw_hash, role, created_by_id=creator_id)
    res = mongo.db.users.insert_one(doc)
    mongo.db.audit_logs.insert_one(
        audit_log_doc(creator_id, "create_user", "users", str(res.inserted_id))
    )
    return jsonify(id=str(res.inserted_id), username=username, role=role), 201


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    old_pw = data.get("old_password") or ""
    new_pw = data.get("new_password") or ""

    if len(new_pw) < 8:
        return jsonify(error="New password must be at least 8 characters"), 400

    user = mongo.db.users.find_one({"_id": ObjectId(uid)})
    if not bcrypt.check_password_hash(user["password_hash"], old_pw):
        return jsonify(error="Current password incorrect"), 401

    new_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
    mongo.db.users.update_one(
        {"_id": ObjectId(uid)},
        {"$set": {"password_hash": new_hash, "password_reset_required": False}}
    )
    return jsonify(message="Password updated")


@auth_bp.get("/me")
@jwt_required()
def me():
    uid = get_jwt_identity()
    user = mongo.db.users.find_one({"_id": ObjectId(uid)})
    if not user:
        return jsonify(error="User not found"), 404
    return jsonify(_user_payload(user))
