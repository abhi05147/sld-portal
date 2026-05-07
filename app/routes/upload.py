from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import mongo
from app.models import audit_log_doc
from app.services.importer import ExcelImporter
from app.services.template_generator import generate_template
import io

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


@upload_bp.get("/template")
@jwt_required()
def download_template():
    """Download the blank Excel import template."""
    try:
        xlsx_bytes = generate_template()
    except Exception as e:
        return jsonify(error=f"Template generation failed: {e}"), 500
    return send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="GEC_II_SLD_Import_Template.xlsx",
    )
