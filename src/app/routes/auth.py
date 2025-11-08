# app/routes/auth.py
from flask import Blueprint, request, current_app, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.orm import load_only
from hmac import compare_digest
from ..extensions import db
from ..models import User
from ..utils import api_error, api_ok
import logging, time, json

bp = Blueprint("auth", __name__)
log = logging.getLogger("carbid.auth")

# --- Utilidades ---
def _bcrypt_cost(pw_hash: str) -> int | None:
    try:
        parts = (pw_hash or "").split("$")
        return int(parts[2]) if len(parts) > 2 else None
    except Exception:
        return None

def _safe_eq(a: str, b: str) -> bool:
    return compare_digest(a.encode("utf-8"), b.encode("utf-8"))

# Cuentas DEMO (coinciden con tu seed)
_DEMO = {
    "admin@carbid.test":  "admin123",
    "seller@carbid.test": "seller123",
    "buyer@carbid.test":  "buyer123",
}

# --- Pequeño tracer por-request ---
class LoginDiag:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.t0 = time.perf_counter()
        self.last = "start"
        self.steps = [{"step": "start", "t": 0.0}]

    def mark(self, step: str):
        t = time.perf_counter() - self.t0
        self.last = step
        if self.enabled:
            self.steps.append({"step": step, "t": round(t, 4)})

    def to_headers(self) -> dict:
        if not self.enabled:
            return {}
        compact = {"last": self.last, "steps": self.steps}
        # Header con JSON compacto
        return {
            "X-Login-Last-Step": self.last,
            "X-Login-Diag": json.dumps(compact, separators=(",", ":")),
        }

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


@bp.post("/login")
def login():
    # Activa diagnóstico SOLO si pides ?diag=1 o header X-Debug-Diag: 1
    diag_enabled = request.args.get("diag") == "1" or request.headers.get("X-Debug-Diag") == "1"
    d = LoginDiag(enabled=diag_enabled)

    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        d.mark("missing_credentials")
        resp = api_error("Faltan credenciales.")
        # añade headers si corresponde
        for k, v in d.to_headers().items():
            resp.headers[k] = v
        return resp

    log.info("login:start email=%s", email)

    # Trae SOLO lo necesario
    q0 = time.perf_counter()
    u = (
        User.query.options(load_only(User.id, User.email, User.name, User.role, User.password_hash))
        .filter_by(email=email)
        .first()
    )
    d.mark("db_query")
    q1 = time.perf_counter()

    if not u:
        log.info("login:notfound email=%s db=%.3fs", email, q1 - q0)
        d.mark("not_found")
        resp = api_error("Credenciales inválidas.", 401)
        for k, v in d.to_headers().items():
            resp.headers[k] = v
        return resp

    # Fast-path DEMO (sin bcrypt)
    demo_pwd = _DEMO.get(email)
    if demo_pwd and _safe_eq(password, demo_pwd):
        d.mark("demo_fastpath_ok")
        token = create_access_token(identity=str(u.id))
        d.mark("token_created")

        payload = {"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}}
        # Incluye diag en el body solo si está habilitado (útil para depurar en frontend)
        if d.enabled:
            payload["_diag"] = {"last": d.last, "steps": d.steps}

        resp = api_ok(payload)
        for k, v in d.to_headers().items():
            resp.headers[k] = v
        log.info("login:demo_ok email=%s db=%.3fs total=%.3fs",
                 email, q1 - q0, time.perf_counter() - d.t0)
        return resp

    # Camino normal (bcrypt)
    v0 = time.perf_counter()
    ok = u.check_password(password)
    d.mark("bcrypt_verify")
    if not ok:
        log.info("login:badpass email=%s db=%.3fs verify=%.3fs",
                 email, q1 - q0, time.perf_counter() - v0)
        resp = api_error("Credenciales inválidas.", 401)
        for k, v in d.to_headers().items():
            resp.headers[k] = v
        return resp

    # Rehash progresivo si el cost vigente es mayor que el deseado
    desired_cost = current_app.config.get("BCRYPT_LOG_ROUNDS", 10)
    current_cost = _bcrypt_cost(u.password_hash) or 12
    if current_cost > desired_cost:
        try:
            u.set_password(password)
            db.session.commit()
            d.mark("rehash_done")
        except Exception:
            db.session.rollback()
            d.mark("rehash_failed")

    token = create_access_token(identity=str(u.id))
    d.mark("token_created")

    payload = {"token": token, "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}}
    if d.enabled:
        payload["_diag"] = {"last": d.last, "steps": d.steps}

    resp = api_ok(payload)
    for k, v in d.to_headers().items():
        resp.headers[k] = v

    log.info(
        "login:ok email=%s db=%.3fs total=%.3fs",
        email, q1 - q0, time.perf_counter() - d.t0
    )
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
