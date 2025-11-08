import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'carbid')}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Motor más robusto frente a locks/cons conectadas
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "isolation_level": "READ COMMITTED",  # reduce lock contention
    }

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

    MIN_INCREMENT_DEFAULT = int(os.getenv("MIN_INCREMENT_DEFAULT", "100"))
