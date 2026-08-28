from flask import Blueprint, request, jsonify, Response, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import mongo
from app.services.sld_generator import SLDGenerator
from app.services.pdf_generator import PDFReportGenerator
from bson import ObjectId
from app.routes.helpers import parse_object_id
import io

sld_bp = Blueprint("sld", __name__)

@sld_bp.get("/<ss_id>")
@jwt_required()
def get_sld(ss_id):
    _, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    gen = SLDGenerator(mongo.db)
    svg = gen.generate(ss_id)
    return Response(svg, mimetype="image/svg+xml")


@sld_bp.get("/<ss_id>/pdf")
@jwt_required()
def get_pdf(ss_id):
    substation_id, err = parse_object_id(ss_id, "substation ID")
    if err:
        return err
    gen = SLDGenerator(mongo.db)
    svg = gen.generate(ss_id)
    pdf_gen = PDFReportGenerator(mongo.db)
    try:
        pdf_bytes = pdf_gen.generate(ss_id, svg)
    except Exception as e:
        return jsonify(error=str(e)), 500
    ss = mongo.db.substations.find_one({"_id": substation_id}, {"name": 1})
    name = (ss or {}).get("name", "substation").replace(" ", "_")
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"SLD_{name}_Report.pdf",
    )
