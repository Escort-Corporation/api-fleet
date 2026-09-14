from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routers import vehicles
from app.core.exceptions import register_exception_handlers

settings = get_settings()

app = FastAPI(title="EscortInRoad api-fleet", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(vehicles.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
