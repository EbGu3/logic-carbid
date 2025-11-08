# app/routes/auth.py
from flask import Blueprint, request, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ..extensions import db, bcrypt
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

# Extrae el "cost" del hash bcrypt: "$2b$12$..." -> 12
def _bcrypt_cost(pw_hash: str) -> int | None:
    try:
        parts = pw_hash.split("$")
        return int(parts[2]) if len(parts) > 2 else None
    except Exception:
        return None


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
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return api_error("Faltan credenciales.")

    # Cuentas semilla (DEMO). Deben coincidir con tu seed.
    DEMO = {
        "admin@carbid.test":  "admin123",
        "seller@carbid.test": "seller123",
        "buyer@carbid.test":  "buyer123",
    }
    # Costo deseado para re-hash rápido (el valor actual de tu app)
    desired_cost = current_app.config.get("BCRYPT_LOG_ROUNDS", 10)

    # Buscar usuario
    u = User.query.filter_by(email=email).first()
    if not u:
        return api_error("Credenciales inválidas.", 401)

    # Fast-path DEMO: si es cuenta semilla y la contraseña coincide, evita bcrypt
    if email in DEMO and password == DEMO[email]:
        current_cost = _bcrypt_cost(u.password_hash or "") or 12
        if current_cost > desired_cost:
            # Re-hash inmediato con el costo actual (más bajo)
            u.set_password(password)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        token = create_access_token(identity=str(u.id))
        return api_ok({"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}})

    # Camino normal (otros usuarios)
    if not u.check_password(password):
        return api_error("Credenciales inválidas.", 401)

    # Re-hash progresivo si el hash vigente tiene costo mayor al deseado
    current_cost = _bcrypt_cost(u.password_hash or "") or 12
    if current_cost > desired_cost:
        try:
            u.set_password(password)
            db.session.commit()
        except Exception:
            db.session.rollback()

    token = create_access_token(identity=str(u.id))
    return api_ok({"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}})


@bp.get("/me")
@jwt_required()
def me():
    uid = int(get_jwt_identity())
    u = User.query.get(uid)
    return api_ok({"id": u.id, "email": u.email, "name": u.name, "role": u.role})


@bp.post("/change-password")
@jwt_required()
def change_password():
    uid = int(get_jwt_identity())
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
