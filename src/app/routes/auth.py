# app/routes/auth.py
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from sqlalchemy.orm import load_only
from hmac import compare_digest
from ..extensions import db
from ..models import User
from ..utils import api_error, api_ok

bp = Blueprint("auth", __name__)

# --- Utilidades ---
def _safe_eq(a: str, b: str) -> bool:
    return compare_digest(a.encode("utf-8"), b.encode("utf-8"))

# Cuentas DEMO (coinciden con tu seed)
_DEMO = {
    "admin@carbid.test":  "admin123",
    "seller@carbid.test": "seller123",
    "buyer@carbid.test":  "buyer123",
}
_ROLE_BY_EMAIL = {
    "admin@carbid.test":  "admin",
    "seller@carbid.test": "seller",
    "buyer@carbid.test":  "buyer",
}

@bp.post("/_echo")
def _echo():
    data = request.get_json(silent=True) or {}
    return api_ok({"echo": data, "ts": __import__("time").time()})

# ---------- Endpoints ----------
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


# --------- LOGIN ULTRA-RÁPIDO (único login activo) ----------
@bp.post("/login")
def login():
    """
    Modo diagnóstico ultra-rápido:
    - No consulta DB ni usa bcrypt.
    - Acepta únicamente las 3 cuentas DEMO.
    - Emite un JWT con identity "0" y claims (email, name, role, demo=True).
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    demo_pwd = _DEMO.get(email)
    if not (demo_pwd and _safe_eq(password, demo_pwd)):
        return api_error("Credenciales inválidas (modo ultra).", 401)

    role = _ROLE_BY_EMAIL.get(email, "buyer")
    user = {
        "id": 0,
        "email": email,
        "name": f"ULTRA-{email.split('@')[0]}",
        "role": role,
    }

    token = create_access_token(
        identity="0",  # identity numérica en string; sockets la pueden castear a int
        additional_claims={"email": user["email"], "name": user["name"], "role": user["role"], "demo": True},
    )

    return api_ok({"token": token, "user": user})
# --------- FIN LOGIN ULTRA-RÁPIDO ----------


@bp.get("/me")
@jwt_required()
def me():
    """
    Compatible con modo ultra:
    - Si identity==0, reconstruye el usuario desde los claims del JWT.
    - Si no, intenta devolver el usuario real desde DB (para cuando quites el modo ultra).
    """
    uid_raw = get_jwt_identity()
    try:
        uid = int(uid_raw)
    except Exception:
        uid = -1

    if uid == 0:
        claims = get_jwt()
        return api_ok({
            "id": 0,
            "email": claims.get("email"),
            "name": claims.get("name"),
            "role": claims.get("role", "buyer"),
            "demo": True,
        })

    u = User.query.options(load_only(User.id, User.email, User.name, User.role)).get(uid)
    if not u:
        return api_error("Usuario no encontrado.", 404)
    return api_ok({"id": u.id, "email": u.email, "name": u.name, "role": u.role})


@bp.post("/change-password")
@jwt_required()
def change_password():
    uid_raw = get_jwt_identity()
    try:
        uid = int(uid_raw)
    except Exception:
        uid = -1

    if uid == 0:
        return api_error("Operación no permitida en modo demo/ultra.", 403)

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
