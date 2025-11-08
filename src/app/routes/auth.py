# app/routes/auth.py
from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

@bp.post("/register")
def register():
    """
    Registro por POST **sin body** usando query-string.
    También acepta JSON como compatibilidad.

    Ejemplos válidos:
      POST /api/auth/register?name=Ana&email=ana@test.com&password=xyz&role=seller
      POST /api/auth/register     (con JSON {"name": "...", "email": "...", ...})
    """
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or request.args.get("name") or "").strip()
    email = (data.get("email") or request.args.get("email") or "").strip().lower()
    password = (data.get("password") or request.args.get("password") or "")
    role = (data.get("role") or request.args.get("role") or "buyer").strip().lower()

    if not all([name, email, password]):
        return api_error("Faltan campos obligatorios (name, email, password).", 400)

    if role not in ("buyer", "seller", "admin"):
        return api_error("Rol inválido. Use buyer, seller o admin.", 400)

    if User.query.filter_by(email=email).first():
        return api_error("El correo ya está registrado.", 409)

    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    return api_ok({"id": u.id, "email": u.email, "name": u.name, "role": u.role})

@bp.route("/login", methods=["GET", "POST"])   # acepta ambos
def login():
    # 1) intenta JSON; si no, usa query string
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or request.args.get("email") or "").strip()
    password = (data.get("password") or request.args.get("password") or "")

    if not email or not password:
        return api_error("Faltan credenciales.", 400)

    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return api_error("Credenciales inválidas.", 401)

    token = create_access_token(identity=str(u.id))
    return api_ok({"token": token, "user": {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role
    }})

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
