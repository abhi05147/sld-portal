"""
Remaining API routes:
  /api/v1/sld         — SVG generation + PDF download
  /api/v1/feeders     — CRUD
  /api/v1/upload      — Excel/CSV import
  /api/v1/users       — Admin user management
  /api/v1/dashboard   — Aggregated stats
  /views              — HTML page rendering
"""
# ── SLD ──────────────────────────────────────────────────────────────────────
from flask import Blueprint, request, jsonify, Response, send_file, render_template
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import feeder_doc, audit_log_doc, utcnow
from app.services.sld_generator import SLDGenerator
from app.services.pdf_generator import PDFReportGenerator
from app.services.importer import ExcelImporter
from bson import ObjectId
import io, os

# ── SLD ──────────────────────────────────────────────────────────────────────
sld_bp = Blueprint("sld", __name__)

@sld_bp.get("/<ss_id>")
@jwt_required()
def get_sld(ss_id):
    gen = SLDGenerator(mongo.db)
    svg = gen.generate(ss_id)
    return Response(svg, mimetype="image/svg+xml")


@sld_bp.get("/<ss_id>/pdf")
@jwt_required()
def get_pdf(ss_id):
    gen = SLDGenerator(mongo.db)
    svg = gen.generate(ss_id)
    pdf_gen = PDFReportGenerator(mongo.db)
    try:
        pdf_bytes = pdf_gen.generate(ss_id, svg)
    except Exception as e:
        return jsonify(error=str(e)), 500
    ss = mongo.db.substations.find_one({"_id": ObjectId(ss_id)}, {"name": 1})
    name = (ss or {}).get("name", "substation").replace(" ", "_")
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"SLD_{name}_Report.pdf",
    )


# ── Feeders ───────────────────────────────────────────────────────────────────
feeders_bp = Blueprint("feeders", __name__)

def _ser_feeder(f):
    f["_id"] = str(f["_id"])
    f["substation_id"] = str(f["substation_id"])
    if f.get("transformer_id"):
        f["transformer_id"] = str(f["transformer_id"])
    return f

@feeders_bp.get("/substation/<ss_id>")
@jwt_required()
def list_feeders(ss_id):
    fds = list(mongo.db.feeders.find({"substation_id": ObjectId(ss_id)}).sort("sequence", 1))
    return jsonify([_ser_feeder(f) for f in fds])


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
    # merge meter/switchgear if provided
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


# ── Upload ────────────────────────────────────────────────────────────────────
upload_bp = Blueprint("upload", __name__)

@upload_bp.post("/excel")
@jwt_required()
def upload_excel():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "engineer"):
        return jsonify(error="Engineer or Admin access required"), 403

    if "file" not in request.files:
        return jsonify(error="No file provided"), 400
    f = request.files["file"]
    if not f.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        return jsonify(error="Only .xlsx, .xls, .csv files accepted"), 400

    importer = ExcelImporter(mongo.db)
    try:
        summary = importer.import_file(f.stream, get_jwt_identity())
    except Exception as e:
        return jsonify(error=f"Import failed: {e}"), 500

    mongo.db.audit_logs.insert_one(
        audit_log_doc(get_jwt_identity(), "excel_upload", detail=str(summary))
    )
    return jsonify(summary)


# ── Users ─────────────────────────────────────────────────────────────────────
users_bp = Blueprint("users", __name__)

def _ser_user(u):
    return {
        "id": str(u["_id"]),
        "username": u.get("username"),
        "email": u.get("email"),
        "role": u.get("role"),
        "is_active": u.get("is_active"),
        "last_login": u.get("last_login").isoformat() if u.get("last_login") else None,
        "created_at": u.get("created_at").isoformat() if u.get("created_at") else None,
    }


@users_bp.get("/")
@jwt_required()
def list_users():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify(error="Admin access required"), 403
    users = list(mongo.db.users.find({}, {"password_hash": 0}))
    return jsonify([_ser_user(u) for u in users])


@users_bp.patch("/<user_id>")
@jwt_required()
def patch_user(user_id):
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify(error="Admin access required"), 403
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
    from app import bcrypt
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify(error="Admin access required"), 403
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


# ── Dashboard ─────────────────────────────────────────────────────────────────
dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.get("/stats")
@jwt_required()
def stats():
    db = mongo.db

    total_ss       = db.substations.count_documents({})
    total_33_inc   = db.feeders.count_documents({"feeder_type": "incoming_33kv"})
    total_11_out   = db.feeders.count_documents({"feeder_type": "outgoing_11kv"})
    total_tr       = db.transformers.count_documents({})

    # Total capacity
    cap_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$capacity_mva"}}}]
    cap_res = list(db.transformers.aggregate(cap_pipeline))
    total_cap = cap_res[0]["total"] if cap_res else 0

    # GSS breakdown
    gss_pipeline = [
        {"$group": {"_id": "$gss_primary", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    gss_breakdown = [
        {"gss": r["_id"] or "Unknown", "substation_count": r["count"]}
        for r in db.substations.aggregate(gss_pipeline)
    ]

    # Region breakdown
    region_pipeline = [
        {"$group": {"_id": "$region", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    region_breakdown = [
        {"region": r["_id"] or "Unknown", "count": r["count"]}
        for r in db.substations.aggregate(region_pipeline)
    ]

    # Substation list with coords for map
    ss_map = list(db.substations.find(
        {"gps.lat": {"$ne": None}},
        {"_id": 1, "name": 1, "gps": 1, "gss_primary": 1, "type": 1, "topology": 1}
    ))
    for s in ss_map:
        s["_id"] = str(s["_id"])

    return jsonify(
        total_substations=total_ss,
        total_33kv_incoming=total_33_inc,
        total_11kv_outgoing=total_11_out,
        total_transformers=total_tr,
        total_capacity_mva=total_cap,
        gss_breakdown=gss_breakdown,
        region_breakdown=region_breakdown,
        substations_map=ss_map,
    )


@dashboard_bp.get("/hierarchy")
@jwt_required()
def hierarchy():
    """Return full GSS → Substation → Feeder tree."""
    db = mongo.db
    gss_list = list(db.grid_substations.find({}, {"_id": 1, "name": 1}))
    result = []
    for gss in gss_list:
        subs = list(db.substations.find(
            {"gss_primary": gss["name"]},
            {"_id": 1, "name": 1, "topology": 1}
        ))
        for s in subs:
            s["_id"] = str(s["_id"])
            fds = list(db.feeders.find(
                {"substation_id": ObjectId(s["_id"]), "feeder_type": "outgoing_11kv"},
                {"_id": 1, "name": 1, "voltage_kv": 1}
            ))
            s["feeders"] = [{"id": str(f["_id"]), "name": f["name"], "voltage_kv": f["voltage_kv"]} for f in fds]
        result.append({
            "gss_id": str(gss["_id"]),
            "gss_name": gss["name"],
            "substations": subs,
        })
    # Substations not linked to known GSS
    linked = {s["name"] for g in result for s in g["substations"]}
    unlinked = list(db.substations.find({"name": {"$nin": list(linked)}}, {"_id": 1, "name": 1, "gss_primary": 1}))
    if unlinked:
        gss_names = {}
        for s in unlinked:
            g = s.get("gss_primary", "Unknown")
            gss_names.setdefault(g, []).append({"_id": str(s["_id"]), "name": s["name"], "feeders": []})
        for g, subs in gss_names.items():
            result.append({"gss_id": None, "gss_name": g, "substations": subs})
    return jsonify(result)


# ── HTML Views ────────────────────────────────────────────────────────────────
views_bp = Blueprint("views", __name__)

@views_bp.get("/")
@views_bp.get("/login")
def login_page():
    return render_template("auth/login.html")

@views_bp.get("/dashboard")
def dashboard_page():
    return render_template("dashboard/index.html")

@views_bp.get("/sld/<ss_id>")
def sld_page(ss_id):
    return render_template("sld/index.html", ss_id=ss_id)

@views_bp.get("/admin/users")
def admin_users_page():
    return render_template("admin/users.html")

@views_bp.get("/admin/upload")
def upload_page():
    return render_template("admin/upload.html")
