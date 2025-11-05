# app/routes/users.py
from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from ..extensions import db
from ..models import Bid, Vehicle, Notification
from ..utils import api_ok

bp = Blueprint("users", __name__)

@bp.get("/users/me/history")
@jwt_required()
def my_history():
    uid = int(get_jwt_identity())
    bids = (
        db.session.query(Bid, Vehicle)
        .join(Vehicle, Vehicle.id == Bid.vehicle_id)
        .filter(Bid.bidder_id == uid)
        .order_by(Bid.created_at.desc())
        .all()
    )
    data = []
    for b, v in bids:
        top = db.session.query(func.max(Bid.amount)).filter(Bid.vehicle_id == v.id).scalar()
        won = (v.status == "closed" and v.winner_bid_id == b.id)
        data.append({
            "bidId": b.id,
            "vehicleId": v.id,
            "make": v.make,
            "model": v.model,
            "amount": b.amount,
            "topAtClose": top,
            "won": won,
            "vehicleStatus": v.status,
            "bidAt": b.created_at.isoformat() + "Z",
        })
    return api_ok(data)

@bp.get("/users/me/notifications")
@jwt_required()
def my_notifications():
    uid = get_jwt_identity()
    items = (
        Notification.query
        .filter_by(user_id=uid)
        .order_by(Notification.read_at.is_(None).desc(), Notification.created_at.desc())
        .all()
    )
    data = []
    for n in items:
        payload = n.payload or {}
        v_id = payload.get("vehicle_id")
        lot_code = None
        if v_id:
            v = Vehicle.query.get(v_id)
            lot_code = v.lot_code if v else None
        # Etiquetas simples
        tlabel = {
            "auction_won": "Ganaste una subasta",
            "outbid": "Tu oferta fue superada",
            "reminder": "Recordatorio",
        }.get(n.type, n.type)
        desc = ""
        if n.type == "auction_won":
            desc = f"Ganaste el lote {lot_code} por ${payload.get('amount'):,}" if lot_code else "Ganaste una subasta."
        elif n.type == "outbid":
            desc = f"Te superaron en el lote {lot_code}" if lot_code else "Tu oferta fue superada."
        elif n.type == "reminder":
            desc = payload.get("message", "Recordatorio de subasta")
        else:
            desc = str(payload) if payload else n.type

        data.append({
            "id": n.id,
            "type": n.type,
            "typeLabel": tlabel,
            "description": desc,
            "payload": payload,
            "createdAt": n.created_at.isoformat() + "Z",
            "readAt": n.read_at.isoformat() + "Z" if n.read_at else None,
        })
    return api_ok(data)

@bp.post("/users/me/notifications/read-all")
@jwt_required()
def mark_notifications_read():
    uid = get_jwt_identity()
    Notification.query.filter_by(user_id=uid, read_at=None).update(
        {Notification.read_at: func.now()}, synchronize_session=False
    )
    db.session.commit()
    return api_ok({"updated": True})

@bp.get("/users/me/agenda")
@jwt_required()
def my_agenda():
    """Eventos próximos: subastas activas donde el usuario ha pujado o es vendedor."""
    uid = get_jwt_identity()
    # Vehículos donde el usuario pujó
    subq = (
        db.session.query(Bid.vehicle_id)
        .filter(Bid.bidder_id == uid)
        .group_by(Bid.vehicle_id)
        .subquery()
    )
    items = (
        db.session.query(Vehicle)
        .filter(
            Vehicle.status == "active",
            ((Vehicle.seller_id == uid) | (Vehicle.id.in_(subq)))
        )
        .order_by(Vehicle.auction_end_at.asc())
        .limit(20)
        .all()
    )
    data = []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for v in items:
        ends = v.auction_end_at.replace(tzinfo=timezone.utc)
        secs = int((ends - now).total_seconds())
        if secs < 0:
            tl = "cierra pronto"
        else:
            d, r = divmod(secs, 86400)
            h, r = divmod(r, 3600)
            m, _ = divmod(r, 60)
            if d > 0: tl = f"{d}d {h}h"
            elif h > 0: tl = f"{h}h {m}m"
            else: tl = f"{m}m"
        data.append({
            "vehicleId": v.id,
            "make": v.make,
            "model": v.model,
            "lotCode": v.lot_code,
            "minIncrement": v.min_increment,
            "endsAt": v.auction_end_at.isoformat() + "Z",
            "timeLeftLabel": tl,
        })
    return api_ok(data)
