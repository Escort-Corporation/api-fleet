-- Eixos do veículo — filtro de compatibilidade (ver escopo original das sprints,
-- docs/SCOPE_DECISIONS.md). Nullable, sem backfill — mesmo precedente de
-- api-auth/supabase/migrations/20260922150000_add_trucker_location.sql. O filtro
-- em si (frete exige N eixos mínimos) vive no api-matching, que lê esta coluna
-- direto do mesmo Postgres.

alter table public.vehicles add column if not exists axle_count integer
  check (axle_count is null or axle_count > 0);
