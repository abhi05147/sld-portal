from flask import Flask
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()

mongo = PyMongo()
jwt = JWTManager()
bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Config
    app.config["MONGO_URI"] = os.environ["MONGO_URI"]
    app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 28800))
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 604800))
    app.config["BCRYPT_LOG_ROUNDS"] = int(os.getenv("BCRYPT_LOG_ROUNDS", 12))
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_SIZE_MB", 20)) * 1024 * 1024

    # Extensions
    mongo.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Ensure indexes on startup
    with app.app_context():
        _ensure_indexes()

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.substations import substations_bp
    from app.routes.feeders import feeders_bp
    from app.routes.sld import sld_bp
    from app.routes.upload import upload_bp
    from app.routes.users import users_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.views import views_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(substations_bp, url_prefix="/api/v1/substations")
    app.register_blueprint(feeders_bp, url_prefix="/api/v1/feeders")
    app.register_blueprint(sld_bp, url_prefix="/api/v1/sld")
    app.register_blueprint(upload_bp, url_prefix="/api/v1/upload")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(views_bp)

    return app


def _ensure_indexes():
    from app import mongo
    db = mongo.db
    db.users.create_index("username", unique=True)
    db.users.create_index("email", unique=True)
    db.substations.create_index("name")
    db.substations.create_index("gss_primary")
    db.feeders.create_index("substation_id")
    db.feeders.create_index([("substation_id", 1), ("sequence", 1)])
    db.grid_substations.create_index("name", unique=True)
    db.audit_logs.create_index([("user_id", 1), ("timestamp", -1)])
