# tests/conftest.py
import os
import pytest
from app import create_app
from app.extensions import db, scheduler

# Importa los modelos para que SQLAlchemy conozca las tablas
from app import models  # noqa

@pytest.fixture(scope="session")
def app_instance(monkeypatch, tmp_path_factory):
    """
    Crea una instancia de la app para pruebas:
    - Deshabilita el scheduler.
    - Usa SQLite en archivo temporal.
    """
    # Evitar que el scheduler arranque threads en tests
    monkeypatch.setattr(scheduler, "start", lambda *a, **k: None)

    # Crea la app
    application = create_app()

    # Cambia la DB a SQLite para pruebas
    db_path = tmp_path_factory.mktemp("db") / "test.sqlite"
    application.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # Crea las tablas
    with application.app_context():
        db.drop_all()
        db.create_all()

    yield application

    # Limpieza final
    with application.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app_instance):
    return app_instance.test_client()

@pytest.fixture()
def app_ctx(app_instance):
    with app_instance.app_context():
        yield

@pytest.fixture()
def auth_headers(client):
    """
    Helper que registra y loguea un usuario,
    devolviendo headers con Bearer token.
    """
    def _mk(email, password):
        # login
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code in (200, 401)
        if r.status_code == 401:
            # Si no existe, registrar y volver a intentar login
            client.post("/api/auth/register", json={
                "name": "Test User",
                "email": email,
                "password": password,
                "role": "buyer"
            })
            r = client.post("/api/auth/login", json={"email": email, "password": password})
            assert r.status_code == 200
        token = r.get_json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}
    return _mk

@pytest.fixture()
def seller_headers(client):
    """
    Crea un usuario seller (o lo reutiliza) y devuelve headers con token.
    """
    email = "seller@test.local"
    password = "seller123"

    # Intenta login directo
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code == 401:
        # Crear seller
        rr = client.post("/api/auth/register", json={
            "name": "Seller",
            "email": email,
            "password": password,
            "role": "seller"
        })
        assert rr.status_code == 200
        r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    token = r.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
d