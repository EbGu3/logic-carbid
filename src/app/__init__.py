from flask import Flask
from .config import Config
from .extensions import db, migrate, bcrypt, jwt, cors, scheduler
from .routes import register_blueprints
from .tasks import schedule_jobs
from .cli import register_cli
from .utils import api_error, api_ok

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_blueprints(app)

    @app.get("/api/health")
    def health():
        return api_ok(True)

    # Mensajes JWT claros (evita 500 opacos)
    @jwt.unauthorized_loader
    def jwt_missing(reason):
        return api_error(f"Autenticación requerida: {reason}", 401)

    @jwt.invalid_token_loader
    def jwt_invalid(reason):
        return api_error(f"Token inválido: {reason}", 422)

    @jwt.expired_token_loader
    def jwt_expired(h, d):
        return api_error("Token expirado.", 401)

    # Jobs
    scheduler.init_app(app)
    schedule_jobs(scheduler, app)
    scheduler.start()

    register_cli(app)
    return app
