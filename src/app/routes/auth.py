# app/routes/auth.py
from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

@bp.post("/register")
def register():
    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "buyer")
    if not all([name, email, password]):
        return api_error("Faltan campos obligatorios (name, email, password).")
    if User.query.filter_by(email=email).first():
        return api_error("El correo ya está registrado.", 409)
    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return api_ok({"id": u.id, "email": u.email, "name": u.name, "role": u.role})

@bp.post("/login")
def login():
    """
    Login robusto: intenta leer JSON; si no hay cuerpo, usa querystring.
    Permite POST /api/auth/login?email=...&password=...
    """
    # 1) Intento "silencioso" de JSON (no lanza 400 si no es JSON)
    data = request.get_json(silent=True) or {}

    # 2) Fallback a querystring si el body no llegó o vino vacío
    email = (data.get("email") or request.args.get("email") or "").strip()
    password = (data.get("password") or request.args.get("password") or "")

    if not email or not password:
        return api_error("Faltan credenciales.", 400)

    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return api_error("Credenciales inválidas.", 401)

    # *** IMPORTANTE: el 'identity' debe ser string ***
    token = create_access_token(identity=str(u.id))

    resp = api_ok({
        "token": token,
        "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}
    })

    # Cabeceras de diagnóstico (opcional)
    resp.headers["X-Auth-From"] = "json" if "email" in data else "query"
    return resp

@bp.get("/me")
@jwt_required()
def me():
    uid = int(get_jwt_identity())
    u = User.query.get(uid)
    return api_ok({"id": u.id, "email": u.email, "name": u.name, "role": u.role})

@bp.post("/change-password")
@jwt_required()
def change_password():
    uid = get_jwt_identity()
    data = request.get_json() or {}
    old_pwd = data.get("old_password")
    new_pwd = data.get("new_password")
    if not old_pwd or not new_pwd:
        return api_error("Faltan campos (old_password, new_password).")
    u = User.query.get(uid)
    if not u or not u.check_password(old_pwd):
        return api_error("La contraseña actual no es correcta.", 401)
    u.set_password(new_pwd)
    db.session.commit()
    return api_ok({"message": "Contraseña actualizada"})
