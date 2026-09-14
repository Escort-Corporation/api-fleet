# api-fleet

Microsserviço de **frota** do Escort in Road: veículo físico, histórico de
propriedade e configuração atual de acoplamento/capacidade para o `api-matching`.
Arquitetura, escopo e decisões em [`ARCHITECTURE.md`](ARCHITECTURE.md).

Stack: Python / FastAPI. Valida o Bearer token do Supabase Auth (mesmo projeto do
`api-auth`) — sem login próprio. Toda escrita passa pelo backend com a secret key.

## Estrutura

| Caminho | Para quê |
|---|---|
| `app/main.py` | App FastAPI, CORS, handlers de erro, registro de routers |
| `app/api/deps.py` | Validação do Bearer token → `user_id` |
| `app/api/routers/vehicles.py` | `POST/GET/PATCH /vehicles`, `/vehicles/{id}`, `/vehicles/{id}/transfer` |
| `app/services/vehicle_service.py` | Regras de domínio (unicidade de placa, dono vigente, transferência) |
| `app/models/vehicle.py` | Schemas Pydantic + normalização de placa |
| `app/core/` | Config, client Supabase, hierarquia `AppError` |
| `migrations/001_fleet_init.sql` | `vehicles`, `vehicle_ownerships`, trigger, RLS (aplicar no Supabase) |

## Endpoints

Servidos **sem** o prefixo `/fleet` — o gateway (`api-core`, Caddy) remove o
prefixo com `handle_path`. Pelo gateway: `POST /fleet/vehicles` → aqui `POST /vehicles`.

| Método | Path | Descrição |
|---|---|---|
| `POST` | `/vehicles` | Cadastra veículo + primeira linha de propriedade |
| `GET` | `/vehicles` | Lista os veículos cujo dono vigente é o usuário |
| `GET` | `/vehicles/{id}` | Consulta um veículo (só o dono vigente) |
| `PATCH` | `/vehicles/{id}` | Atualiza specs/acoplamento/status (`inactive` = desativar) |
| `POST` | `/vehicles/{id}/transfer` | Transfere propriedade (efeito imediato, sem aprovação na v1) |
| `GET` | `/health` | Health check |

## Desenvolvimento local

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # preencha SUPABASE_URL e SUPABASE_SECRET_KEY
uvicorn app.main:app --reload --port 8002
```

Aplique `migrations/001_fleet_init.sql` no SQL editor do Supabase antes do primeiro uso.
Pelo gateway local (`api-core/Caddyfile.dev`), o serviço é esperado na porta `8002`.

## Deploy com Docker

```bash
docker network create escort-net      # se ainda não existe
cp .env.example .env                   # preencha os segredos do Supabase
docker compose up -d --build
```

O container sobe como `api-fleet` na rede `escort-net`, escutando em `:8000`
(não exposto publicamente). O gateway roteia `/fleet/*` para `api-fleet:8000`.

## Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `SUPABASE_URL` | Projeto Supabase compartilhado (`core-db`) |
| `SUPABASE_SECRET_KEY` | Secret key — backend-only, nunca vai ao client |
| `CORS_ALLOWED_ORIGINS` | Lista separada por vírgula; sem default hardcoded |
