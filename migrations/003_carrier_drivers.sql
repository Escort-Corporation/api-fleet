-- api-fleet — vínculo motorista ↔ ECF (MVP, REGRAS_NEGOCIO_MVP.md).
--
-- No MVP o motorista é EMPREGADO de uma ECF (carrier) e é pago por ela, via folha; a Escort não
-- paga motorista e não há motorista autônomo. O veículo pertence à ECF (vehicle_ownerships) e o
-- frete casa com a ECF (freights.matched_driver_id = dono do veículo). Esta tabela diz QUAIS
-- motoristas (trucker) operam pela ECF: eles iniciam a viagem, confirmam a entrega e publicam
-- posição nos fretes da ECF — sem isso, só a própria ECF (login da empresa) conseguiria fazê-lo.
--
-- É um vínculo de emprego, não uma atribuição motorista↔veículo (vehicle_assignments segue no
-- backlog): qualquer motorista vinculado opera qualquer frete da ECF.
--
-- Aplicar DEPOIS do schema do api-auth (profiles). Idempotente o suficiente para rodar de novo.

create table if not exists public.carrier_drivers (
  id uuid primary key default gen_random_uuid(),
  carrier_id uuid not null references public.profiles(id),
  driver_id uuid not null references public.profiles(id),
  started_at timestamptz not null default now(),
  ended_at timestamptz,                          -- null = vínculo vigente
  created_at timestamptz not null default now(),
  check (carrier_id <> driver_id)
);

-- Um motorista tem no máximo UMA ECF vigente (empregador único). Evita também que duas ECFs
-- disputem o mesmo motorista e que o vínculo sirva de brecha para operar frete alheio.
create unique index if not exists carrier_drivers_active_driver
  on public.carrier_drivers (driver_id)
  where ended_at is null;

-- "Motoristas vigentes da ECF X" (listagem e checagem de acesso do api-freight).
create index if not exists carrier_drivers_active_carrier
  on public.carrier_drivers (carrier_id)
  where ended_at is null;

-- RLS: sem policy de escrita — toda mutação passa pelo backend (secret key). Leitura: a ECF e o
-- próprio motorista veem o vínculo.
alter table public.carrier_drivers enable row level security;

drop policy if exists carrier_drivers_select_parties on public.carrier_drivers;
create policy carrier_drivers_select_parties on public.carrier_drivers
  for select to authenticated
  using ((select auth.uid()) in (carrier_id, driver_id));
