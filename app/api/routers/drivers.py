"""Vínculo motorista ↔ ECF (MVP: motorista empregado da ECF, sem autônomo).

Servido SEM o prefixo /fleet (o gateway faz o strip): `/fleet/drivers` na borda.
`/drivers/me` é declarado antes de `/drivers/{driver_id}` para não ser capturado como id.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user_id
from app.models.driver import CarrierDriverOut, DriverEmploymentOut, DriverLinkCreate
from app.services import driver_service

router = APIRouter(prefix="/drivers", tags=["drivers"])

CurrentUserId = Annotated[str, Depends(get_current_user_id)]


@router.post("", response_model=CarrierDriverOut, status_code=status.HTTP_201_CREATED)
def link_driver(user_id: CurrentUserId, payload: DriverLinkCreate) -> CarrierDriverOut:
    """A ECF vincula um motorista cadastrado pelo e-mail dele."""
    return driver_service.link_driver(user_id, payload.driver_email)


@router.get("", response_model=list[CarrierDriverOut])
def list_drivers(user_id: CurrentUserId) -> list[CarrierDriverOut]:
    """Motoristas vigentes da ECF autenticada."""
    return driver_service.list_drivers(user_id)


@router.get("/me", response_model=DriverEmploymentOut)
def my_employment(user_id: CurrentUserId) -> DriverEmploymentOut:
    """Para o motorista: a ECF para a qual ele opera hoje."""
    return driver_service.my_employment(user_id)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def leave_carrier(user_id: CurrentUserId) -> Response:
    """O motorista encerra o próprio vínculo."""
    driver_service.leave_carrier(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_driver(user_id: CurrentUserId, driver_id: str) -> Response:
    """A ECF encerra o vínculo de um motorista."""
    driver_service.unlink_driver(user_id, driver_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
