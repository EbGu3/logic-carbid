# app/cli.py
import click
from flask import current_app
from .extensions import db
from .models import User, Vehicle
from .config import Config

def register_cli(app):
    @app.cli.command("seed")
    def seed():
        """Carga datos de ejemplo (admin/seller/buyer y 3 vehículos)."""
        with app.app_context():
            if not User.query.filter_by(email="admin@carbid.test").first():
                admin = User(name="Admin", email="admin@carbid.test", role="admin")
                admin.set_password("admin123")
                db.session.add(admin)

            if not User.query.filter_by(email="seller@carbid.test").first():
                seller = User(name="Seller", email="seller@carbid.test", role="seller")
                seller.set_password("seller123")
                db.session.add(seller)
                db.session.flush()

                v1 = Vehicle(
                    seller_id=seller.id, make="Ford", model="Mustang",
                    year=1969, base_price=200000, lot_code="F54",
                    images=["https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1600&q=80"],
                    description="Ford Mustang 1969 en excelente estado",
                    min_increment=app.config.get("MIN_INCREMENT_DEFAULT", 100)
                )
                v2 = Vehicle(
                    seller_id=seller.id, make="Dodge", model="Charger",
                    year=1970, base_price=150000, lot_code="M12",
                    images=["https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=1600&q=80"],
                    description="Dodge Charger 1970 restaurado",
                    min_increment=app.config.get("MIN_INCREMENT_DEFAULT", 100)
                )
                v3 = Vehicle(
                    seller_id=seller.id, make="Honda", model="Civic",
                    year=1998, base_price=5000, lot_code="C03",
                    images=["https://images.unsplash.com/photo-1619767886558-efdc259cde1c?auto=format&fit=crop&w=1600&q=80"],
                    description="Honda Civic 1998 para proyecto",
                    min_increment=app.config.get("MIN_INCREMENT_DEFAULT", 100)
                )
                db.session.add_all([v1, v2, v3])

            if not User.query.filter_by(email="buyer@carbid.test").first():
                buyer = User(name="Buyer", email="buyer@carbid.test", role="buyer")
                buyer.set_password("buyer123")
                db.session.add(buyer)

            db.session.commit()
            click.echo("Seed listo.")
