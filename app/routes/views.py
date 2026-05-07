from flask import Blueprint, render_template

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
