from datetime import datetime
from flask import current_app
from .extensions import db, socketio
from .models import Vehicle, Bid, Notification
from .sse import publish

def close_expired_auctions(app=None):
    """Cierra subastas vencidas (con contexto de app y sesión limpia)."""
    if app is None:
        app = current_app._get_current_object()
    with app.app_context():
        try:
            now = datetime.utcnow()
            to_close = Vehicle.query.filter(
                Vehicle.status == "active",
                Vehicle.auction_end_at <= now
            ).with_for_update(read=True).all()

            changed = False
            for v in to_close:
                win = v.bids.order_by(Bid.amount.desc()).first()
                v.status = "closed"
                if win:
                    v.winner_bid_id = win.id
                    # Notifica ganador
                    db.session.add(Notification(
                        user_id=win.bidder_id,
                        type="auction_won",
                        payload={"vehicle_id": v.id, "amount": win.amount}
                    ))
                    # SSE
                    publish(f"vehicle:{v.id}", "closed", {
                        "vehicleId": v.id, "winnerBidId": win.id, "amount": win.amount
                    })
                    # Socket.IO
                    socketio.emit("closed", {
                        "vehicleId": v.id, "winnerBidId": win.id, "amount": win.amount
                    }, to=f"vehicle:{v.id}", namespace="/rt")
                    socketio.emit("notification", {
                        "type": "auction_won",
                        "payload": {"vehicle_id": v.id, "amount": win.amount}
                    }, to=f"user:{win.bidder_id}", namespace="/rt")
                else:
                    publish(f"vehicle:{v.id}", "closed", {
                        "vehicleId": v.id, "winnerBidId": None
                    })
                    socketio.emit("closed", {
                        "vehicleId": v.id, "winnerBidId": None
                    }, to=f"vehicle:{v.id}", namespace="/rt")
                changed = True

            if changed:
                db.session.commit()
        finally:
            db.session.remove()

def schedule_jobs(scheduler, app):
    scheduler.add_job(
        id="close_auctions",
        func=close_expired_auctions,
        trigger="interval",
        seconds=30,
        args=[app],
        coalesce=True,
        max_instances=1,
    )
