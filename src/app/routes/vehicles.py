from time import sleep
from flask import Blueprint, request, current_app
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Vehicle, Bid, User
from ..utils import api_error, api_ok
from ..sse import stream, sse_response, publish

bp = Blueprint("vehicles", __name__)

@bp.get("/sse/vehicles/<int:vehicle_id>")
def sse_vehicle(vehicle_id):
    return sse_response(stream(f"vehicle:{vehicle_id}"))

@bp.get("/vehicles")
def list_vehicles():
    status = request.args.get("status", "active")
    q = Vehicle.query
    if status != "all":
        q = q.filter(Vehicle.status == status)
    text_q = request.args.get("q")
    if text_q:
        like = f"%{text_q}%"
        q = q.filter(
            (Vehicle.make.ilike(like)) |
            (Vehicle.model.ilike(like)) |
            (Vehicle.lot_code.ilike(like))
        )
    items = q.order_by(Vehicle.created_at.desc()).all()
    return api_ok([serialize_vehicle_summary(v) for v in items])

@bp.post("/vehicles")
@jwt_required()
def create_vehicle():
    # Reducimos lock waits de esta sesión
    try:
        db.session.execute(text("SET SESSION innodb_lock_wait_timeout = 5"))
    except Exception:
        pass

    uid_raw = get_jwt_identity()
    try:
        uid = int(uid_raw)
    except Exception:
        return api_error("Token inválido.", 401)

    user = User.query.get(uid)
    if not user:
        return api_error("Usuario no encontrado.", 404)
    if user.role not in ("seller", "admin"):
        return api_error("Solo vendedores o administradores pueden publicar.", 403)

    data = request.get_json() or {}

    make = (data.get("make") or "").strip()
    model = (data.get("model") or "").strip()
    lot_code = (data.get("lot_code") or "").strip()

    try:
        year = int(data.get("year") or 0)
        base_price = int(data.get("base_price") or 0)
        min_increment = int(data.get("min_increment") or 100)
    except ValueError:
        return api_error("Campos numéricos inválidos (year/base_price/min_increment).", 400)

    if not all([make, model, lot_code]) or year < 1886 or base_price <= 0:
        return api_error("Datos incompletos o inválidos.", 400)

    if Vehicle.query.filter_by(lot_code=lot_code).first():
        return api_error("El código de lote ya existe.", 409)

    imgs = data.get("images") or []
    if not isinstance(imgs, list):
        return api_error("images debe ser un arreglo de URLs.", 400)

    v = Vehicle(
        seller_id=uid,
        make=make, model=model, year=year,
        base_price=base_price, lot_code=lot_code,
        images=imgs, description=data.get("description"),
        min_increment=min_increment, status=data.get("status") or "active",
    )

    # ---- Retry ante 1205/1213 ----
    for attempt in range(3):
        try:
            db.session.add(v)
            db.session.commit()
            return api_ok(serialize_vehicle_detail(v))
        except OperationalError as e:
            code = getattr(getattr(e, "orig", None), "args", [None])[0]
            if code in (1205, 1213):  # lock wait / deadlock
                current_app.logger.warning(f"Retry vehicles.insert por lock (intento {attempt+1})")
                db.session.rollback()
                sleep(0.35 * (attempt + 1))
                continue
            db.session.rollback()
            current_app.logger.exception("Error operacional creando vehículo")
            return api_error("No se pudo publicar el vehículo.", 400, details=str(getattr(e, "orig", e)))
        except IntegrityError as e:
            db.session.rollback()
            return api_error("Conflicto de datos (posible lote duplicado).", 409,
                             details=str(getattr(e, "orig", e)))
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.exception("Error SQL creando vehículo")
            return api_error("No se pudo publicar el vehículo.", 400, details=str(getattr(e, "orig", e)))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Error inesperado creando vehículo")
            return api_error("Error interno al publicar.", 500, details=str(e))

    return api_error("No se pudo publicar el vehículo (reintentos agotados).", 409)

@bp.get("/vehicles/<int:vehicle_id>")
def get_vehicle(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    return api_ok(serialize_vehicle_detail(v))

@bp.patch("/vehicles/<int:vehicle_id>/close")
@jwt_required()
def close_vehicle(vehicle_id):
    uid = int(get_jwt_identity())
    v = Vehicle.query.get_or_404(vehicle_id)
    if v.seller_id != uid:
        return api_error("Solo el vendedor puede cerrar la subasta.", 403)
    if v.status == "closed":
        return api_error("La subasta ya está cerrada.", 409)
    v.status = "closed"
    win = v.bids.order_by(Bid.amount.desc()).first()
    if win:
        v.winner_bid_id = win.id
    db.session.commit()
    publish(f"vehicle:{v.id}", "closed",
            {"vehicleId": v.id, "winnerBidId": v.winner_bid_id, "amount": win.amount if win else None})
    return api_ok({"vehicleId": v.id, "status": v.status, "winnerBidId": v.winner_bid_id})

@bp.get("/vehicles/<int:vehicle_id>/bids")
def list_bids(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    bids = v.bids.order_by(Bid.amount.desc(), Bid.created_at.asc()).all()
    return api_ok([serialize_bid(b) for b in bids])

@bp.post("/vehicles/<int:vehicle_id>/bids")
@jwt_required()
def place_bid(vehicle_id):
    uid = int(get_jwt_identity())
    v = db.session.query(Vehicle).filter_by(id=vehicle_id).with_for_update().first()
    if not v:
        return api_error("Vehículo no encontrado.", 404)
    if v.status != "active":
        return api_error("La subasta no está activa.", 409)
    if v.seller_id == uid:
        return api_error("El vendedor no puede pujar su propio vehículo.", 403)

    data = request.get_json() or {}
    amount = int(data.get("amount") or 0)

    current = v.base_price
    top = db.session.query(func.max(Bid.amount)).filter(Bid.vehicle_id == vehicle_id).scalar()
    if top and top > current:
        current = top

    min_required = current + v.min_increment
    if amount < min_required:
        return api_error("La oferta es menor al mínimo requerido.", 400,
                         min_required=min_required, current=current, min_increment=v.min_increment)

    b = Bid(vehicle_id=vehicle_id, bidder_id=uid, amount=amount)
    db.session.add(b)
    db.session.commit()

    publish(f"vehicle:{v.id}", "top-updated", {"vehicleId": v.id, "top": amount, "bidId": b.id})
    return api_ok(serialize_bid(b), min_required=amount + v.min_increment)

def serialize_vehicle_summary(v: Vehicle):
    current = v.base_price
    top = v.bids.with_entities(func.max(Bid.amount)).scalar()
    if top and top > current:
        current = top
    return {
        "id": v.id,
        "make": v.make,
        "model": v.model,
        "year": v.year,
        "basePrice": v.base_price,
        "currentPrice": current,
        "minIncrement": v.min_increment,
        "lotCode": v.lot_code,
        "images": v.images or [],
        "status": v.status,
        "endsAt": v.auction_end_at.isoformat() + "Z",
    }

def serialize_vehicle_detail(v: Vehicle):
    data = serialize_vehicle_summary(v)
    data.update({
        "description": v.description,
        "sellerId": v.seller_id,
        "createdAt": v.created_at.isoformat() + "Z",
    })
    return data

def serialize_bid(b: Bid):
    return {
        "id": b.id,
        "vehicleId": b.vehicle_id,
        "bidderId": b.bidder_id,
        "amount": b.amount,
        "createdAt": b.created_at.isoformat() + "Z",
    }
