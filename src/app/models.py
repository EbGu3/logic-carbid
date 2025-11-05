from datetime import datetime, timedelta
from .extensions import db, bcrypt

class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(db.Model, TimestampMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="buyer")  # buyer|seller|admin

    bids = db.relationship("Bid", back_populates="bidder", lazy="dynamic")

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode()

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

class Vehicle(db.Model, TimestampMixin):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    make = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    base_price = db.Column(db.Integer, nullable=False)
    lot_code = db.Column(db.String(20), nullable=False)
    images = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="active")  # active|closed
    auction_start_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    auction_end_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=7))
    min_increment = db.Column(db.Integer, nullable=False, default=100)

    # Gana una puja
    winner_bid_id = db.Column(db.Integer, db.ForeignKey("bids.id"), nullable=True)

    # Relaciones
    seller = db.relationship("User", foreign_keys=[seller_id])

    # *** CLAVE: especificar foreign_keys para desambiguar ***
    bids = db.relationship(
        "Bid",
        back_populates="vehicle",
        lazy="dynamic",
        foreign_keys="Bid.vehicle_id",
        order_by="Bid.amount.desc()",
    )

    # Relación directa al ganador (opcional, útil para lecturas)
    winner_bid = db.relationship(
        "Bid",
        foreign_keys=[winner_bid_id],
        uselist=False,
        post_update=True,   # ayuda a evitar ciclos al actualizar FKs
    )

class Bid(db.Model, TimestampMixin):
    __tablename__ = "bids"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    bidder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)

    vehicle = db.relationship("Vehicle", back_populates="bids", foreign_keys=[vehicle_id])
    bidder = db.relationship("User", back_populates="bids", foreign_keys=[bidder_id])

class Notification(db.Model, TimestampMixin):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
