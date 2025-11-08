from time import perf_counter
from hmac import compare_digest
from flask import Blueprint, request, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.orm import load_only
from ..extensions import db
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

# --- Utils ---
_DEMO = {
    "admin@carbid.test":  "admin123",
    "seller@carbid.test": "seller123",
    "buyer@carbid.test":  "buyer123",
}

def _bcrypt_cost(pw_hash: str) -> int | None:
    try:
        parts = (pw_hash or "").split("$")
        return int(parts[2]) if len(parts) > 2 else None
    except Exception:
        return None

def _safe_eq(a: str, b: str) -> bool:
    return compare_digest(a.encode("utf-8"), b.encode("utf-8"))


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
    t0 = perf_counter()
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return api_error("Faltan credenciales.")

    # Solo columnas necesarias
    u = (
        User.query.options(load_only(User.id, User.email, User.name, User.role, User.password_hash))
        .filter_by(email=email)
        .first()
    )
    if not u:
        return api_error("Credenciales inválidas.", 401)

    # DEMO fast-path (sin bcrypt)
    demo_pwd = _DEMO.get(email)
    if demo_pwd and _safe_eq(password, demo_pwd):
        token = create_access_token(identity=str(u.id))
        return api_ok({"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}})

    # Camino normal
    if not u.check_password(password):
        return api_error("Credenciales inválidas.", 401)

    # Rehash progresivo si el cost es alto
    desired_cost = current_app.config.get("BCRYPT_LOG_ROUNDS", 10)
    current_cost = _bcrypt_cost(u.password_hash) or 12
    if current_cost > desired_cost:
        try:
            u.set_password(password)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # (Opcional) logging de latencia del endpoint en stdout (visible en EB logs)
    dt = (perf_counter() - t0) * 1000
    print(f"[auth.login] OK in {dt:.1f} ms for {email}")

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
