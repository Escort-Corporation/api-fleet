"""Endpoints de veículo e transferência de propriedade (ARCHITECTURE.md §4, §7).

Router fino: valida o token (deps), delega ao service. Os paths são servidos SEM
o prefixo /fleet — o gateway (api-core, Caddy) faz o strip com handle_path.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user_id
from app.models.vehicle import (
    TransferRequest,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
)
from app.services import vehicle_service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

CurrentUserId = Annotated[str, Depends(get_current_user_id)]


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(user_id: CurrentUserId, payload: VehicleCreate) -> VehicleOut:
    return vehicle_service.create_vehicle(user_id, payload)


@router.get("", response_model=list[VehicleOut])
def list_vehicles(user_id: CurrentUserId) -> list[VehicleOut]:
    return vehicle_service.list_vehicles(user_id)


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(user_id: CurrentUserId, vehicle_id: str) -> VehicleOut:
    return vehicle_service.get_vehicle(user_id, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(user_id: CurrentUserId, vehicle_id: str, payload: VehicleUpdate) -> VehicleOut:
    return vehicle_service.update_vehicle(user_id, vehicle_id, payload)


@router.post("/{vehicle_id}/transfer", response_model=VehicleOut)
def transfer_ownership(
    user_id: CurrentUserId, vehicle_id: str, payload: TransferRequest
) -> VehicleOut:
    return vehicle_service.transfer_ownership(user_id, vehicle_id, payload)
