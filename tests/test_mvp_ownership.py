"""MVP: so ECF (carrier) tem frota. Motorista autonomo (trucker dono de veiculo) esta fora."""

import pytest

from app.core.exceptions import ForbiddenError
from app.models.vehicle import TransferRequest, VehicleCreate
from app.services import vehicle_service


def _vehicle_payload(plate="ABC1D23") -> VehicleCreate:
    return VehicleCreate(
        plate=plate,
        make="Volvo",
        model="FH 540",
        year=2022,
        vehicle_type="truck",
        weight_capacity_kg=25000,
    )


def test_carrier_can_register_a_vehicle(db):
    db.add("profiles", id="carrier-1", user_type="carrier")
    out = vehicle_service.create_vehicle("carrier-1", _vehicle_payload())
    assert out.current_owner.owner_type == "carrier"


def test_autonomous_trucker_cannot_register_a_vehicle(db):
    db.add("profiles", id="trucker-1", user_type="trucker")
    with pytest.raises(ForbiddenError):
        vehicle_service.create_vehicle("trucker-1", _vehicle_payload())
    assert not db.tables.get("vehicles")


def test_shipper_cannot_register_a_vehicle(db):
    db.add("profiles", id="shipper-1", user_type="shipper")
    with pytest.raises(ForbiddenError):
        vehicle_service.create_vehicle("shipper-1", _vehicle_payload())


def _owned_vehicle(db):
    db.add("profiles", id="carrier-1", user_type="carrier")
    return vehicle_service.create_vehicle("carrier-1", _vehicle_payload())


def test_transfer_to_another_carrier_is_allowed(db):
    v = _owned_vehicle(db)
    db.add("profiles", id="carrier-2", user_type="carrier")
    out = vehicle_service.transfer_ownership(
        "carrier-1", v.id, TransferRequest(new_owner_type="carrier", new_owner_id="carrier-2")
    )
    assert out.current_owner.owner_id == "carrier-2" and out.current_owner.owner_type == "carrier"


def test_transfer_to_a_trucker_is_refused(db):
    v = _owned_vehicle(db)
    db.add("profiles", id="trucker-1", user_type="trucker")
    with pytest.raises(ForbiddenError):
        vehicle_service.transfer_ownership(
            "carrier-1", v.id, TransferRequest(new_owner_type="trucker", new_owner_id="trucker-1")
        )
    assert vehicle_service._active_ownership(v.id)["owner_id"] == "carrier-1"


def test_owner_type_comes_from_the_profile_not_from_the_payload(db):
    """Declarar new_owner_type='carrier' para um trucker nao burla a regra."""
    v = _owned_vehicle(db)
    db.add("profiles", id="trucker-1", user_type="trucker")
    with pytest.raises(ForbiddenError):
        vehicle_service.transfer_ownership(
            "carrier-1", v.id, TransferRequest(new_owner_type="carrier", new_owner_id="trucker-1")
        )


# --- Motorista autonomo: preparado e desligado (MOTORISTA_AUTONOMO.md) ---------------------


@pytest.fixture()
def autonomy_on(monkeypatch):
    from app.core.config import Settings

    s = Settings(
        _env_file=None,
        autonomous_drivers_enabled=True,
        autonomous_legal_review_done=True,
        autonomous_cargo_insurance_active=True,
        autonomous_rntrc_ciot_ready=True,
    )
    monkeypatch.setattr(vehicle_service, "get_settings", lambda: s)
    return s


def test_autonomous_trucker_registers_a_vehicle_only_with_autonomy_on(db, autonomy_on):
    db.add("profiles", id="trucker-1", user_type="trucker")
    out = vehicle_service.create_vehicle("trucker-1", _vehicle_payload())
    assert out.current_owner.owner_type == "trucker"


def test_transfer_to_a_trucker_only_with_autonomy_on(db, autonomy_on):
    v = _owned_vehicle(db)
    db.add("profiles", id="trucker-1", user_type="trucker")
    out = vehicle_service.transfer_ownership(
        "carrier-1", v.id, TransferRequest(new_owner_type="trucker", new_owner_id="trucker-1")
    )
    assert out.current_owner.owner_type == "trucker"


def test_shipper_still_cannot_own_vehicles_with_autonomy_on(db, autonomy_on):
    db.add("profiles", id="shipper-1", user_type="shipper")
    with pytest.raises(ForbiddenError):
        vehicle_service.create_vehicle("shipper-1", _vehicle_payload())


def test_fleet_refuses_to_start_with_autonomy_on_but_no_legal_review():
    from pydantic import ValidationError as PydanticValidationError

    from app.core.config import Settings

    with pytest.raises(PydanticValidationError):
        Settings(_env_file=None, autonomous_drivers_enabled=True)
