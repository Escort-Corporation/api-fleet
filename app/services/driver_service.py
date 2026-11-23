"""Vínculo motorista ↔ ECF (MVP, REGRAS_NEGOCIO_MVP.md).

O motorista é empregado da ECF e é pago por ela, via folha — a Escort não paga motorista e não há
motorista autônomo. O vínculo existe para que o motorista opere os fretes da ECF (iniciar viagem,
confirmar entrega, publicar posição) sem usar o login da empresa. Quem decide o acesso é o
api-freight, lendo esta tabela direto do Postgres compartilhado.

Regras:
- Só uma `carrier` ativa e não banida vincula; só um `trucker` ativo e não banido é vinculado.
- Um motorista tem UMA ECF vigente (índice único parcial). Para trocar de ECF, o vínculo atual
  termina primeiro — pela ECF ou pelo próprio motorista (ele nunca fica preso).
- E-mail desconhecido e e-mail de quem não é motorista dão a MESMA resposta (404), para a busca
  não virar um jeito de descobrir que e-mail é de que tipo de conta.
"""

from datetime import datetime, timezone

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.supabase_client import get_supabase_admin_client
from app.models.driver import CarrierDriverOut, DriverEmploymentOut


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile(client, user_id: str) -> dict:
    res = (
        client.table("profiles")
        .select("id, user_type, is_active, is_banned, full_name, email, phone")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise ForbiddenError("Perfil não encontrado para o usuário autenticado.")
    return res.data[0]


def _require_active(profile: dict, expected_type: str, message: str) -> None:
    if (profile.get("user_type") or "").lower() != expected_type:
        raise ForbiddenError(message)
    if not profile.get("is_active") or profile.get("is_banned"):
        raise ForbiddenError("Conta inativa ou suspensa.")


def _active_link_for_driver(client, driver_id: str) -> dict | None:
    res = (
        client.table("carrier_drivers")
        .select("*")
        .eq("driver_id", driver_id)
        .is_("ended_at", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


# --- ECF ---------------------------------------------------------------------------------


def link_driver(carrier_id: str, driver_email: str) -> CarrierDriverOut:
    client = get_supabase_admin_client()
    _require_active(_profile(client, carrier_id), "carrier", "Apenas a transportadora (ECF) pode vincular motoristas.")

    found = (
        client.table("profiles")
        .select("id, user_type, is_active, is_banned, full_name, email, phone")
        .eq("email", driver_email.strip().lower())
        .limit(1)
        .execute()
    )
    driver = found.data[0] if found.data else None
    if (
        driver is None
        or (driver.get("user_type") or "").lower() != "trucker"
        or not driver.get("is_active")
        or driver.get("is_banned")
    ):
        raise NotFoundError("Motorista não encontrado.")

    existing = _active_link_for_driver(client, driver["id"])
    if existing is not None:
        if existing["carrier_id"] == carrier_id:
            raise ConflictError("Este motorista já está vinculado à sua transportadora.")
        raise ConflictError(
            "Este motorista já está vinculado a outra transportadora. O vínculo atual precisa terminar primeiro."
        )

    inserted = (
        client.table("carrier_drivers")
        .insert({"carrier_id": carrier_id, "driver_id": driver["id"], "started_at": _now_iso()})
        .execute()
    )
    return _serialize(inserted.data[0], driver)


def _serialize(link: dict, driver: dict) -> CarrierDriverOut:
    return CarrierDriverOut(
        id=link["id"],
        driver_id=driver["id"],
        full_name=driver["full_name"],
        email=driver["email"],
        phone=driver.get("phone"),
        started_at=link["started_at"],
    )


def list_drivers(carrier_id: str) -> list[CarrierDriverOut]:
    client = get_supabase_admin_client()
    _require_active(_profile(client, carrier_id), "carrier", "Apenas a transportadora (ECF) lista seus motoristas.")
    links = client.table("carrier_drivers").select("*").eq("carrier_id", carrier_id).is_("ended_at", "null").execute().data
    if not links:
        return []
    profiles = (
        client.table("profiles")
        .select("id, full_name, email, phone")
        .in_("id", [link["driver_id"] for link in links])
        .execute()
        .data
    )
    by_id = {p["id"]: p for p in profiles}
    return [_serialize(link, by_id[link["driver_id"]]) for link in links if link["driver_id"] in by_id]


def unlink_driver(carrier_id: str, driver_id: str) -> None:
    """A ECF encerra o vínculo. O histórico fica (ended_at), nada é apagado."""
    client = get_supabase_admin_client()
    _require_active(_profile(client, carrier_id), "carrier", "Apenas a transportadora (ECF) remove motoristas.")
    link = _active_link_for_driver(client, driver_id)
    if link is None or link["carrier_id"] != carrier_id:
        raise NotFoundError("Este motorista não está vinculado à sua transportadora.")
    client.table("carrier_drivers").update({"ended_at": _now_iso()}).eq("id", link["id"]).execute()


# --- Motorista ---------------------------------------------------------------------------


def my_employment(driver_id: str) -> DriverEmploymentOut:
    client = get_supabase_admin_client()
    _require_active(_profile(client, driver_id), "trucker", "Apenas motoristas têm vínculo com uma transportadora.")
    link = _active_link_for_driver(client, driver_id)
    if link is None:
        return DriverEmploymentOut(linked=False)
    carrier = (
        client.table("profiles").select("id, full_name").eq("id", link["carrier_id"]).limit(1).execute().data
    )
    return DriverEmploymentOut(
        linked=True,
        carrier_id=link["carrier_id"],
        carrier_name=carrier[0]["full_name"] if carrier else None,
        started_at=link["started_at"],
    )


def leave_carrier(driver_id: str) -> None:
    """O motorista encerra o próprio vínculo: nunca fica preso a uma ECF."""
    client = get_supabase_admin_client()
    _require_active(_profile(client, driver_id), "trucker", "Apenas motoristas têm vínculo com uma transportadora.")
    link = _active_link_for_driver(client, driver_id)
    if link is None:
        raise NotFoundError("Você não está vinculado a nenhuma transportadora.")
    client.table("carrier_drivers").update({"ended_at": _now_iso()}).eq("id", link["id"]).execute()
