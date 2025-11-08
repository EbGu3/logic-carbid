# app/routes/auth.py
from flask import Blueprint, request, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.orm import load_only
from hmac import compare_digest
from ..extensions import db, bcrypt
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

# --- Utilidades ---
def _bcrypt_cost(pw_hash: str) -> int | None:
    """Extrae el 'cost' de un hash bcrypt del tipo $2b$12$... -> 12."""
    try:
        parts = pw_hash.split("$")
        return int(parts[2]) if len(parts) > 2 else None
    except Exception:
        return None

def _safe_eq(a: str, b: str) -> bool:
    """Comparación en tiempo constante para evitar timing attacks."""
    return compare_digest(a.encode("utf-8"), b.encode("utf-8"))

# Cuentas DEMO (coinciden con tu seed)
_DEMO = {
    "admin@carbid.test":  "admin123",
    "seller@carbid.test": "seller123",
    "buyer@carbid.test":  "buyer123",
}


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

    # Traemos sólo columnas necesarias (menos payload y más rápido)
    u = (
        User.query.options(load_only(User.id, User.email, User.name, User.role, User.password_hash))
        .filter_by(email=email)
        .first()
    )
    if not u:
        return api_error("Credenciales inválidas.", 401)

    # --------- FAST-PATH DEMO (sin bcrypt) ----------
    # Si es una cuenta de semilla y la contraseña coincide,
    # devolvemos el token inmediatamente (sin rehash ni bcrypt).
    demo_pwd = _DEMO.get(email)
    if demo_pwd and _safe_eq(password, demo_pwd):
        token = create_access_token(identity=str(u.id))
        return api_ok({
            "token": token,
            "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}
        })
    # --------- FIN FAST-PATH DEMO ----------

    # Camino normal para el resto de usuarios
    if not u.check_password(password):
        return api_error("Credenciales inválidas.", 401)

    # Rehash progresivo si el hash tiene cost alto comparado con el deseado
    desired_cost = current_app.config.get("BCRYPT_LOG_ROUNDS", 10)
    current_cost = _bcrypt_cost(u.password_hash or "") or 12
    if current_cost > desired_cost:
        try:
            u.set_password(password)
            db.session.commit()
        except Exception:
            db.session.rollback()

    token = create_access_token(identity=str(u.id))
    return api_ok({
        "token": token,
        "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}
    })


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
