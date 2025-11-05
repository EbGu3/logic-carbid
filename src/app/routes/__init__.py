from .auth import bp as auth_bp
from .vehicles import bp as vehicles_bp
from .users import bp as users_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(vehicles_bp, url_prefix="/api")
    app.register_blueprint(users_bp, url_prefix="/api")
