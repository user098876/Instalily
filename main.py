from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal

settings = get_settings()

app = FastAPI(title="InstaLily LeadGen API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def readiness() -> dict:
    db_ok = False
    redis_ok = False
    db_error = None
    redis_error = None

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # pragma: no cover - exercised in integration environments
        db_error = str(exc)
    finally:
        db.close()

    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
        redis_ok = True
    except Exception as exc:  # pragma: no cover - exercised in integration environments
        redis_error = str(exc)

    status = "ok" if db_ok and redis_ok else "degraded"
    return {
        "status": status,
        "app_env": settings.app_env,
        "services": {
            "database": {"ok": db_ok, "error": db_error},
            "redis": {"ok": redis_ok, "error": redis_error},
        },
    }
