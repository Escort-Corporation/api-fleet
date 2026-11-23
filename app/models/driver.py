"""Schemas do vínculo motorista ↔ ECF (MVP: motorista é empregado da ECF, sem autônomo)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DriverLinkCreate(BaseModel):
    """A ECF vincula um motorista cadastrado (user_type = trucker) pelo e-mail dele."""

    model_config = ConfigDict(extra="forbid")

    # Sem EmailStr: evita somar email-validator só para isto. O e-mail é só chave de busca em profiles.
    driver_email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CarrierDriverOut(BaseModel):
    """Visão da ECF: um motorista vigente da frota."""

    id: str
    driver_id: str
    full_name: str
    email: str
    phone: str | None = None
    started_at: datetime


class DriverEmploymentOut(BaseModel):
    """Visão do motorista: a ECF para a qual ele opera hoje (ou nenhuma)."""

    linked: bool
    carrier_id: str | None = None
    carrier_name: str | None = None
    started_at: datetime | None = None
