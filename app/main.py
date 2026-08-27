from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
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

# Routers (vehicles, ownership transfer) are added here as they're implemented —
# see ARCHITECTURE.md section 7 for the phased roadmap.


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
