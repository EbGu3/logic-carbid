# src/app/__init__.py
from flask import Flask, request, current_app
from .config import Config
from .extensions import db, migrate, bcrypt, jwt, cors, scheduler, socketio
from .routes import register_blueprints
from .tasks import schedule_jobs
from .cli import register_cli
from .utils import api_error, api_ok
from .sockets import register_socketio

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Extensiones base
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # Orígenes QUEMADOS (idénticos para CORS HTTP y WS)
    ORIGINS = ["https://cbid.click", "https://www.cbid.click"]

    # CORS HTTP para /api/* y también para /socket.io/* (preflight del WS)
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": ORIGINS,
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
            },
            r"/socket.io/*": {
                "origins": ORIGINS,
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
            },
        },
    )

    # Socket.IO con los mismos orígenes QUEMADOS
    socketio.init_app(
        app,
        cors_allowed_origins=ORIGINS,
        cors_credentials=True,
    )

    # Preflight ultrarrápido para evitar timeouts en OPTIONS de API/WS
    @app.before_request
    def _fast_preflight():
        if request.method == "OPTIONS" and (
            request.path.startswith("/api/") or request.path.startswith("/socket.io/")
        ):
            resp = current_app.make_default_options_response()
            origin = request.headers.get("Origin", "")
            req_hdrs = request.headers.get(
                "Access-Control-Request-Headers", "Authorization, Content-Type"
            )
            if origin in ORIGINS:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = req_hdrs
            return resp

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

    # Namespaces/handlers de Socket.IO
    register_socketio(socketio)

    register_cli(app)
    return app
