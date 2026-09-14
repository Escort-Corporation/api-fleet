-- api-fleet — schema inicial (fase 1 do roteiro, ver ARCHITECTURE.md §3 e §7).
--
-- Roda no mesmo projeto Supabase (`core-db`) do api-auth. Assume que a função
-- public.set_updated_at() e a tabela public.profiles já existem (criadas pelo api-auth).
--
-- Aplicar via Supabase (SQL editor / migration). Idempotente o suficiente para
-- rodar novamente em ambiente limpo.

-- Veículo físico + configuração atual de acoplamento.
create table if not exists public.vehicles (
  id uuid primary key default gen_random_uuid(),
  plate text not null unique,              -- normalizada: maiúsculas, sem espaço/traço
  make text not null,
  model text not null,
  year integer not null,
  vehicle_type text not null,              -- 'truck', 'pickup', 'van', 'car'... sem CHECK rígido
  height_m numeric,
  width_m numeric,

  -- Configuração atual de acoplamento (mutável; sem histórico na v1 — ver §2).
  attachment_type text,                    -- 'sider', 'cacamba', 'tanque', null = sem acoplamento
  weight_capacity_kg numeric not null,
  volume_capacity_m3 numeric,

  status text not null default 'active' check (status in ('active', 'inactive', 'maintenance')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Histórico de propriedade. Uma linha com ended_at = null é a propriedade vigente.
create table if not exists public.vehicle_ownerships (
  id uuid primary key default gen_random_uuid(),
  vehicle_id uuid not null references public.vehicles(id) on delete cascade,
  owner_type text not null check (owner_type in ('trucker', 'carrier')),
  owner_id uuid not null references public.profiles(id),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_at timestamptz not null default now()
);

-- No máximo um dono vigente por veículo.
create unique index if not exists vehicle_ownerships_active_owner
  on public.vehicle_ownerships (vehicle_id)
  where ended_at is null;

-- Busca frequente: "veículos cujo dono vigente é X".
create index if not exists vehicle_ownerships_owner_active
  on public.vehicle_ownerships (owner_id)
  where ended_at is null;

-- updated_at calculado pelo Postgres, nunca pelo client (mesmo padrão do api-auth).
-- create or replace: no-op se o api-auth já criou a função com o mesmo corpo.
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_vehicles_updated_at on public.vehicles;
create trigger set_vehicles_updated_at
  before update on public.vehicles
  for each row execute function public.set_updated_at();

-- RLS: nenhuma policy de escrita para anon/authenticated — toda mutação passa
-- pelo backend com a secret key. Ver ARCHITECTURE.md §3 e §6.
alter table public.vehicles enable row level security;
alter table public.vehicle_ownerships enable row level security;

-- Leitura: dono vigente pode ler seus próprios veículos.
drop policy if exists vehicles_select_owner on public.vehicles;
create policy vehicles_select_owner on public.vehicles
  for select to authenticated
  using (
    exists (
      select 1 from public.vehicle_ownerships o
      where o.vehicle_id = vehicles.id
        and o.ended_at is null
        and o.owner_id = auth.uid()
    )
  );

drop policy if exists vehicle_ownerships_select_owner on public.vehicle_ownerships;
create policy vehicle_ownerships_select_owner on public.vehicle_ownerships
  for select to authenticated
  using (owner_id = auth.uid());
