from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_apscheduler import APScheduler
from flask_socketio import SocketIO

db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()
scheduler = APScheduler()

_HARDCODED_ORIGINS = ["https://cbid.click", "https://www.cbid.click"]

socketio = SocketIO(
    cors_allowed_origins=_HARDCODED_ORIGINS,
    cors_credentials=True,
    logger=False,
    engineio_logger=False,
)
