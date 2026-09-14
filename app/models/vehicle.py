"""Pydantic schemas para veículos e propriedade.

Validação de valores conhecidos de `vehicle_type`/`attachment_type` fica aqui
(camada de aplicação), não no banco — ver ARCHITECTURE.md §3.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

VehicleStatus = Literal["active", "inactive", "maintenance"]
OwnerType = Literal["trucker", "carrier"]

PlateStr = Annotated[str, Field(min_length=5, max_length=10)]


def normalize_plate(plate: str) -> str:
    """Maiúsculas, sem espaço/traço — unicidade da placa na plataforma inteira (§1)."""
    return "".join(ch for ch in plate.upper() if ch.isalnum())


class VehicleBase(BaseModel):
    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1900, le=datetime.now().year + 1)
    vehicle_type: str = Field(min_length=1, max_length=40)
    height_m: float | None = Field(default=None, gt=0, le=10)
    width_m: float | None = Field(default=None, gt=0, le=10)
    attachment_type: str | None = Field(default=None, max_length=40)
    weight_capacity_kg: float = Field(gt=0)
    volume_capacity_m3: float | None = Field(default=None, gt=0)


class VehicleCreate(VehicleBase):
    plate: PlateStr

    @field_validator("plate")
    @classmethod
    def _normalize(cls, v: str) -> str:
        normalized = normalize_plate(v)
        if len(normalized) < 5:
            raise ValueError("Placa inválida.")
        return normalized


class VehicleUpdate(BaseModel):
    """PATCH parcial. `plate` não é editável por aqui (ARCHITECTURE.md §4)."""

    model_config = ConfigDict(extra="forbid")

    make: str | None = Field(default=None, min_length=1, max_length=60)
    model: str | None = Field(default=None, min_length=1, max_length=60)
    year: int | None = Field(default=None, ge=1900, le=datetime.now().year + 1)
    vehicle_type: str | None = Field(default=None, min_length=1, max_length=40)
    height_m: float | None = Field(default=None, gt=0, le=10)
    width_m: float | None = Field(default=None, gt=0, le=10)
    attachment_type: str | None = Field(default=None, max_length=40)
    weight_capacity_kg: float | None = Field(default=None, gt=0)
    volume_capacity_m3: float | None = Field(default=None, gt=0)
    status: VehicleStatus | None = None


class OwnershipOut(BaseModel):
    id: str
    vehicle_id: str
    owner_type: OwnerType
    owner_id: str
    started_at: datetime
    ended_at: datetime | None = None


class VehicleOut(VehicleBase):
    id: str
    plate: str
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime
    current_owner: OwnershipOut | None = None


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_owner_type: OwnerType
    new_owner_id: str
