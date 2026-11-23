"""Vinculo motorista <-> ECF: o motorista e empregado da ECF, pago por ela (MVP)."""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.services import driver_service


def _people(db):
    db.add("profiles", id="carrier-1", user_type="carrier", is_active=True, is_banned=False, full_name="Transp A", email="a@t.com", phone=None)
    db.add("profiles", id="carrier-2", user_type="carrier", is_active=True, is_banned=False, full_name="Transp B", email="b@t.com", phone=None)
    db.add("profiles", id="driver-1", user_type="trucker", is_active=True, is_banned=False, full_name="Joao Motorista", email="joao@x.com", phone="41999990000")
    db.add("profiles", id="shipper-1", user_type="shipper", is_active=True, is_banned=False, full_name="ESF", email="esf@x.com", phone=None)


def test_carrier_links_a_driver_by_email(db):
    _people(db)
    out = driver_service.link_driver("carrier-1", "Joao@X.com")  # e-mail e normalizado
    assert out.driver_id == "driver-1" and out.full_name == "Joao Motorista"
    assert [d.driver_id for d in driver_service.list_drivers("carrier-1")] == ["driver-1"]


def test_only_a_carrier_can_link_drivers(db):
    _people(db)
    for user in ("driver-1", "shipper-1"):
        with pytest.raises(ForbiddenError):
            driver_service.link_driver(user, "joao@x.com")


def test_banned_or_inactive_carrier_cannot_link(db):
    _people(db)
    db.tables["profiles"][0]["is_banned"] = True
    with pytest.raises(ForbiddenError):
        driver_service.link_driver("carrier-1", "joao@x.com")


@pytest.mark.parametrize("email", ["nao-existe@x.com", "esf@x.com", "b@t.com"])
def test_unknown_email_and_non_driver_email_look_the_same(db, email):
    """Nao da para descobrir, pela busca, que e-mail pertence a que tipo de conta."""
    _people(db)
    with pytest.raises(NotFoundError) as exc:
        driver_service.link_driver("carrier-1", email)
    assert str(exc.value) == "Motorista não encontrado."


def test_banned_driver_cannot_be_linked(db):
    _people(db)
    db.tables["profiles"][2]["is_banned"] = True
    with pytest.raises(NotFoundError):
        driver_service.link_driver("carrier-1", "joao@x.com")


def test_driver_has_a_single_employer(db):
    _people(db)
    driver_service.link_driver("carrier-1", "joao@x.com")
    with pytest.raises(ConflictError):
        driver_service.link_driver("carrier-1", "joao@x.com")  # mesma ECF
    with pytest.raises(ConflictError):
        driver_service.link_driver("carrier-2", "joao@x.com")  # outra ECF


def test_carrier_can_unlink_and_driver_can_then_join_another(db):
    _people(db)
    driver_service.link_driver("carrier-1", "joao@x.com")
    driver_service.unlink_driver("carrier-1", "driver-1")
    assert driver_service.list_drivers("carrier-1") == []
    assert driver_service.link_driver("carrier-2", "joao@x.com").driver_id == "driver-1"
    # historico preservado: o vinculo antigo continua registrado, so encerrado
    old = [r for r in db.tables["carrier_drivers"] if r["carrier_id"] == "carrier-1"]
    assert len(old) == 1 and old[0]["ended_at"] is not None


def test_a_carrier_cannot_unlink_another_carriers_driver(db):
    _people(db)
    driver_service.link_driver("carrier-1", "joao@x.com")
    with pytest.raises(NotFoundError):
        driver_service.unlink_driver("carrier-2", "driver-1")
    assert len(driver_service.list_drivers("carrier-1")) == 1


def test_driver_sees_his_employer_and_can_leave(db):
    _people(db)
    assert driver_service.my_employment("driver-1").linked is False
    driver_service.link_driver("carrier-1", "joao@x.com")
    mine = driver_service.my_employment("driver-1")
    assert mine.linked and mine.carrier_id == "carrier-1" and mine.carrier_name == "Transp A"
    driver_service.leave_carrier("driver-1")
    assert driver_service.my_employment("driver-1").linked is False
    with pytest.raises(NotFoundError):
        driver_service.leave_carrier("driver-1")


def test_only_a_driver_has_an_employment(db):
    _people(db)
    with pytest.raises(ForbiddenError):
        driver_service.my_employment("carrier-1")


def test_list_is_scoped_to_the_calling_carrier(db):
    _people(db)
    driver_service.link_driver("carrier-1", "joao@x.com")
    assert driver_service.list_drivers("carrier-2") == []


# --- HTTP ---------------------------------------------------------------------------------


@pytest.fixture()
def client(db, monkeypatch):
    from app.api import deps
    from app.main import app

    app.dependency_overrides[deps.get_current_user_id] = lambda: "carrier-1"
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_http_link_list_and_unlink(client, db):
    _people(db)
    created = client.post("/drivers", json={"driver_email": "joao@x.com"})
    assert created.status_code == 201 and created.json()["driver_id"] == "driver-1"
    assert [d["email"] for d in client.get("/drivers").json()] == ["joao@x.com"]
    assert client.delete("/drivers/driver-1").status_code == 204
    assert client.get("/drivers").json() == []


def test_http_rejects_extra_fields_and_bad_email(client, db):
    _people(db)
    assert client.post("/drivers", json={"driver_email": "joao@x.com", "salary": 1}).status_code == 422
    assert client.post("/drivers", json={"driver_email": "not-an-email"}).status_code == 422


def test_http_me_is_not_captured_as_a_driver_id(client, db):
    _people(db)
    # carrier-1 chamando /drivers/me: e rota de motorista (403), nao DELETE de um id "me"
    assert client.get("/drivers/me").status_code == 403
