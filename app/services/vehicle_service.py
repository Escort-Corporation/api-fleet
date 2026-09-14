"""Lógica de domínio de frota. Routers ficam finos, o service concentra as regras
(mesmo padrão do api-auth — sem repository pattern). Ver ARCHITECTURE.md §4.

Todas as escritas usam o client com secret key (bypass de RLS); a autorização
("é o dono vigente?") é feita aqui, na aplicação.
"""

from datetime import datetime, timezone

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.supabase_client import get_supabase_admin_client
from app.models.vehicle import (
    TransferRequest,
    VehicleCapacityOut,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
    normalize_plate,
)

_ELIGIBLE_OWNER_TYPES = {"trucker", "carrier"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_owner_type(user_id: str) -> str:
    """Lê o tipo do usuário autenticado em public.profiles (mesmo banco, leitura direta).
    Só trucker/carrier podem ser donos de veículo (ARCHITECTURE.md §4)."""
    client = get_supabase_admin_client()
    res = client.table("profiles").select("user_type").eq("id", user_id).limit(1).execute()
    if not res.data:
        raise ForbiddenError("Perfil não encontrado para o usuário autenticado.")
    user_type = (res.data[0].get("user_type") or "").lower()
    if user_type not in _ELIGIBLE_OWNER_TYPES:
        raise ForbiddenError("Apenas transportador (trucker) ou transportadora (carrier) podem ter veículos.")
    return user_type


def _active_ownership(vehicle_id: str) -> dict | None:
    client = get_supabase_admin_client()
    res = (
        client.table("vehicle_ownerships")
        .select("*")
        .eq("vehicle_id", vehicle_id)
        .is_("ended_at", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _serialize(vehicle_row: dict, ownership_row: dict | None) -> VehicleOut:
    return VehicleOut.model_validate({**vehicle_row, "current_owner": ownership_row})


def _get_vehicle_owned_by(vehicle_id: str, user_id: str) -> tuple[dict, dict]:
    client = get_supabase_admin_client()
    res = client.table("vehicles").select("*").eq("id", vehicle_id).limit(1).execute()
    if not res.data:
        raise NotFoundError("Veículo não encontrado.")
    ownership = _active_ownership(vehicle_id)
    if ownership is None or ownership["owner_id"] != user_id:
        raise ForbiddenError("Apenas o dono vigente do veículo pode fazer esta operação.")
    return res.data[0], ownership


# --- Fluxos (ARCHITECTURE.md §4) ---------------------------------------------


def create_vehicle(user_id: str, payload: VehicleCreate) -> VehicleOut:
    owner_type = _resolve_owner_type(user_id)
    client = get_supabase_admin_client()

    plate = normalize_plate(payload.plate)
    existing = client.table("vehicles").select("id").eq("plate", plate).limit(1).execute()
    if existing.data:
        raise ConflictError("Já existe um veículo com esta placa.")

    vehicle_data = payload.model_dump()
    vehicle_data["plate"] = plate
    inserted = client.table("vehicles").insert(vehicle_data).execute()
    vehicle_row = inserted.data[0]

    try:
        ownership = (
            client.table("vehicle_ownerships")
            .insert(
                {
                    "vehicle_id": vehicle_row["id"],
                    "owner_type": owner_type,
                    "owner_id": user_id,
                    "started_at": _now_iso(),
                }
            )
            .execute()
        )
    except Exception:
        # Sem transação real via PostgREST: compensa apagando o veículo órfão.
        client.table("vehicles").delete().eq("id", vehicle_row["id"]).execute()
        raise

    return _serialize(vehicle_row, ownership.data[0])


def list_vehicles(user_id: str) -> list[VehicleOut]:
    client = get_supabase_admin_client()
    owned = (
        client.table("vehicle_ownerships")
        .select("*")
        .eq("owner_id", user_id)
        .is_("ended_at", "null")
        .execute()
    )
    if not owned.data:
        return []

    by_vehicle = {o["vehicle_id"]: o for o in owned.data}
    vehicles = (
        client.table("vehicles")
        .select("*")
        .in_("id", list(by_vehicle.keys()))
        .order("created_at", desc=True)
        .execute()
    )
    return [_serialize(v, by_vehicle.get(v["id"])) for v in vehicles.data]


def get_vehicle(user_id: str, vehicle_id: str) -> VehicleOut:
    vehicle_row, ownership = _get_vehicle_owned_by(vehicle_id, user_id)
    return _serialize(vehicle_row, ownership)


def update_vehicle(user_id: str, vehicle_id: str, payload: VehicleUpdate) -> VehicleOut:
    vehicle_row, ownership = _get_vehicle_owned_by(vehicle_id, user_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("Nenhum campo para atualizar.")

    client = get_supabase_admin_client()
    updated = client.table("vehicles").update(changes).eq("id", vehicle_id).execute()
    return _serialize(updated.data[0], ownership)


def deactivate_vehicle(user_id: str, vehicle_id: str) -> VehicleOut:
    """Soft delete — não existe DELETE físico (ARCHITECTURE.md §4)."""
    return update_vehicle(user_id, vehicle_id, VehicleUpdate(status="inactive"))


def get_vehicle_capacity(vehicle_id: str) -> VehicleCapacityOut:
    """Leitura usada pelo api-matching para checar capacidade/compatibilidade
    (ARCHITECTURE.md §7, fase 5) — não é escopada por dono: qualquer serviço
    autenticado precisa poder consultar a capacidade de qualquer veículo para
    cruzar com uma carga. Só expõe atributos técnicos, nunca dado de propriedade."""
    client = get_supabase_admin_client()
    res = client.table("vehicles").select("*").eq("id", vehicle_id).limit(1).execute()
    if not res.data:
        raise NotFoundError("Veículo não encontrado.")
    return VehicleCapacityOut.model_validate(res.data[0])


def transfer_ownership(user_id: str, vehicle_id: str, payload: TransferRequest) -> VehicleOut:
    vehicle_row, ownership = _get_vehicle_owned_by(vehicle_id, user_id)

    if payload.new_owner_id == user_id:
        raise ValidationError("O novo dono é o dono atual.")

    client = get_supabase_admin_client()
    new_owner = (
        client.table("profiles").select("user_type").eq("id", payload.new_owner_id).limit(1).execute()
    )
    if not new_owner.data:
        raise NotFoundError("Novo dono não encontrado.")

    # Fecha a propriedade vigente e abre a nova. Efeito imediato, sem aprovação (§2).
    client.table("vehicle_ownerships").update({"ended_at": _now_iso()}).eq("id", ownership["id"]).execute()
    try:
        created = (
            client.table("vehicle_ownerships")
            .insert(
                {
                    "vehicle_id": vehicle_id,
                    "owner_type": payload.new_owner_type,
                    "owner_id": payload.new_owner_id,
                    "started_at": _now_iso(),
                }
            )
            .execute()
        )
    except Exception:
        client.table("vehicle_ownerships").update({"ended_at": None}).eq("id", ownership["id"]).execute()
        raise

    return _serialize(vehicle_row, created.data[0])
