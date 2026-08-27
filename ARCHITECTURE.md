# api-fleet — Arquitetura

> Microsserviço de frota do **Escort in Road**. Responsável pelo veículo físico, sua propriedade (com histórico) e sua configuração de equipamento/acoplamento atual — os dados que o `api-matching` precisa para saber "este veículo consegue transportar esta carga".
>
> Este documento cobre **apenas** o serviço `api-fleet`. Autenticação/identidade é responsabilidade do [`api-auth`](../api-auth) (já implementado). Habilitações/permissões do motorista, fretes, matching, chat e tracking são responsabilidade de outros serviços, fora de escopo aqui.

Status: **planejamento** — nenhum código implementado ainda. Este é um documento vivo — reflete o estado atual do serviço e evolui junto com ele.

Contexto de projeto: TCC com verba **R$ 0**. Toda decisão de escopo e stack abaixo prioriza simplicidade de desenvolvimento e infraestrutura gratuita sobre "arquitetura ideal". Ver histórico de decisões na seção 8.

---

## 1. Visão geral

- **Framework**: FastAPI (Python) — mesma stack do `api-auth`, por produtividade. Fleet é CRUD + histórico relacional, não tem carga de concorrência que justifique Rust (ver seção 8 para o critério usado).
- **Banco**: mesmo projeto Supabase do `api-auth` (`core-db`), tabelas próprias do domínio Fleet. Serviços compartilham um único projeto Postgres gratuito em vez de um banco por serviço — trade-off deliberado de TCC/verba zero (ver seção 8).
- **Autenticação**: valida o mesmo Supabase Auth do `api-auth` (JWT emitido por login). O Fleet não tem sistema de login próprio.
- **Dono de**: veículo físico, propriedade (histórico), configuração atual de acoplamento/equipamento.

### O que este serviço faz
- Cadastro, consulta, atualização e desativação de veículos.
- Histórico de propriedade (`vehicle_ownerships`) — permite venda/transferência sem recriar o veículo.
- Transferência de propriedade entre `TRUCKER`/`CARRIER`.
- Unicidade de placa na plataforma inteira.
- Configuração atual de acoplamento/equipamento do veículo (sider, caçamba, tanque, sem acoplamento, etc.) e as capacidades relevantes para matching.

### O que este serviço **não** faz (fica para outros serviços)
- Autenticação/identidade — isso é `api-auth`.
- Habilitação/permissão legal do motorista (CNH, autorização para carga perigosa etc.) — isso é o perfil do motorista no `api-auth`/futuro `api-driver`. O Fleet expõe só a capacidade técnica do veículo; quem cruza capacidade + permissão é o `api-matching`.
- Quem está dirigindo o veículo *agora* (atribuição/empréstimo) — modelo de `vehicle_assignments` foi **adiado deliberadamente** para depois do TCC (seção 7).
- Matching, fretes, negociação, rating.

---

## 2. Escopo da v1 (o que entra e o que fica pra depois)

Decisão explícita de reduzir escopo pelo prazo/verba do TCC — não é o modelo de domínio "ideal" do planejamento original da plataforma, é o subconjunto que sustenta a demonstração central da tese (matching que reduz viagem vazia) sem inflar o cronograma.

**Entra na v1:**
- `vehicles` — veículo físico + configuração atual de acoplamento (sem histórico de troca de acoplamento).
- `vehicle_ownerships` — histórico de propriedade (venda/transferência do veículo entre `TRUCKER`/`CARRIER`).
- Transferência de propriedade **direta** (dono atual transfere para outro `owner_id`, efeito imediato — sem fluxo de aprovação em duas etapas).

**Fica para trabalhos futuros (documentado, não implementado):**
- `vehicle_assignments` — quem está dirigindo o veículo agora, distinto de quem é o dono (empréstimo temporário/indefinido). Motivo do corte: é a peça mais complexa do domínio original (múltiplos estados, aprovação, expiração) e não é necessária para demonstrar o núcleo da tese — a v1 assume que dono e operador são a mesma pessoa/empresa.
- Fluxo de aprovação de transferência (contra-assinatura do novo dono) e o caso excepcional de transferência administrativa (dono não pode/não quer aprovar). V1 confia na boa-fé de quem já está autenticado como dono atual.
- Histórico de troca de acoplamento — v1 trata o acoplamento como um atributo mutável do veículo (sobrescreve o atual), não como uma entidade com histórico próprio.
- Acoplamento fornecido pelo contratante (caso "vehicle + contractor attachment" do planejamento original) — é uma configuração ad-hoc por frete, resolvida no `api-matching`/`api-freight` quando esses serviços existirem, não algo que o Fleet precisa modelar.
- Integração com base externa (marca/modelo/ano → especificações automáticas).

---

## 3. Modelo de dados

### Por que veículo e acoplamento não são a mesma coisa, mas acoplamento não vira entidade própria na v1

O planejamento original da plataforma trata `VEHICLE` e `ATTACHMENT` como entidades separadas com histórico próprio, porque um caminhão pode trocar de equipamento ao longo do tempo sem deixar de ser o mesmo veículo. Esse princípio continua válido aqui — só que, para reduzir escopo, a v1 representa a configuração de acoplamento como **campos no próprio registro do veículo** (mutáveis, sem histórico), em vez de uma tabela `attachments` com histórico de troca. Isso é uma simplificação de implementação, não uma mudança de modelo conceitual: se no futuro for necessário histórico de acoplamento (ex. saber qual equipamento estava montado numa viagem específica), o campo pode ser extraído para uma tabela própria sem quebrar o contrato externo do `api-matching` (que só enxerga "capacidade atual do veículo X").

### Por que propriedade tem histórico, mas atribuição de motorista não existe ainda

Propriedade (`vehicle_ownerships`) precisa de histórico desde a v1 porque é o que garante a unicidade da placa: quando um veículo é vendido, ele continua sendo o mesmo `vehicle_id`, só muda o dono. Sem histórico de propriedade, uma venda exigiria recriar o veículo do zero, perdendo rastreabilidade e arriscando duplicidade de placa. Atribuição de motorista (quem está dirigindo) não tem esse mesmo custo de omitir — na v1, dono e operador são tratados como a mesma coisa; é uma perda de expressividade aceita conscientemente (ver seção 2).

### SQL de referência (v1)

```sql
-- Veículo físico + configuração atual de acoplamento.
create table public.vehicles (
  id uuid primary key default gen_random_uuid(),
  plate text not null unique,              -- normalizada: maiúsculas, sem espaço/traço
  make text not null,
  model text not null,
  year integer not null,
  vehicle_type text not null,              -- ex. 'truck', 'pickup', 'van', 'car' — sem CHECK rígido, ver nota abaixo
  height_m numeric,
  width_m numeric,

  -- Configuração atual de acoplamento (mutável; sem histórico na v1 — ver seção 2)
  attachment_type text,                    -- ex. 'sider', 'cacamba', 'tanque', null = sem acoplamento
  weight_capacity_kg numeric not null,      -- capacidade considerando o acoplamento atual (ou do próprio veículo, se null)
  volume_capacity_m3 numeric,

  status text not null default 'active' check (status in ('active', 'inactive', 'maintenance')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Histórico de propriedade. Uma linha com ended_at = null é a propriedade vigente.
create table public.vehicle_ownerships (
  id uuid primary key default gen_random_uuid(),
  vehicle_id uuid not null references public.vehicles(id) on delete cascade,
  owner_type text not null check (owner_type in ('trucker', 'carrier')),
  owner_id uuid not null references public.profiles(id),  -- profiles é do api-auth; mesmo projeto Supabase (ver seção 8)
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_at timestamptz not null default now()
);

-- Garante no máximo um dono vigente por veículo.
create unique index vehicle_ownerships_active_owner
  on public.vehicle_ownerships (vehicle_id)
  where ended_at is null;
```

> **Nota sobre `vehicle_type`/`attachment_type`**: propositalmente `text` sem `CHECK` fechado — o planejamento original é explícito em não travar esses valores numa enumeração rígida, para não impedir a expansão futura do domínio (novos tipos de equipamento/veículo). Validação de valores conhecidos, se necessária, fica na camada de aplicação (Pydantic), não no banco.

> **Nota sobre `owner_id → profiles.id`**: como Fleet e Auth compartilham o mesmo projeto Supabase (`core-db`), é possível referenciar `public.profiles` diretamente com FK real, em vez de duplicar dado ou fazer chamada HTTP para validar o dono. Ver seção 8 para a decisão de banco compartilhado e o trade-off que isso implica.

### Trigger de `updated_at`

Mesmo padrão do `api-auth`: `updated_at` calculado pelo Postgres no `UPDATE`, nunca pelo client.

```sql
create trigger set_vehicles_updated_at
  before update on public.vehicles
  for each row execute function public.set_updated_at();  -- função já existe no projeto (criada pelo api-auth)
```

### RLS (Row Level Security)

Habilitado em `vehicles` e `vehicle_ownerships`. Padrão: nenhuma policy de escrita para `anon`/`authenticated` — toda escrita passa pelo backend com a secret key (mesmo padrão do `api-auth`). Leitura: dono vigente (via join com `vehicle_ownerships` ativo) pode ler seus próprios veículos; sem policy de leitura pública.

---

## 4. Fluxos

### Cadastrar veículo — `POST /vehicles`

1. Valida o Bearer token (mesmo mecanismo do `api-auth`: `supabase.auth.get_user(token)`).
2. Resolve `user_type` do usuário autenticado consultando `profiles` (leitura direta, mesmo banco) — só `trucker`/`carrier` podem cadastrar veículo.
3. Normaliza a placa (maiúsculas, remove espaço/traço) e verifica unicidade antes de inserir.
4. Cria a linha em `vehicles` e a primeira linha em `vehicle_ownerships` (`owner_type`/`owner_id` = usuário autenticado, `started_at = now()`, `ended_at = null`) — mesma transação lógica.

### Listar/consultar veículos — `GET /vehicles`, `GET /vehicles/{id}`

Lista os veículos cujo dono vigente é o usuário autenticado (join com `vehicle_ownerships` ativo). `CARRIER` vê toda sua frota.

### Atualizar veículo — `PATCH /vehicles/{id}`

Só o dono vigente pode atualizar. `plate` não é editável por aqui (mudar placa é edge case administrativo, fora de escopo v1). Atualiza specs e/ou configuração de acoplamento (`attachment_type`, capacidades).

### Transferir propriedade — `POST /vehicles/{id}/transfer`

```json
{ "new_owner_type": "trucker", "new_owner_id": "<uuid>" }
```

1. Só o dono vigente pode iniciar.
2. Fecha a linha ativa de `vehicle_ownerships` (`ended_at = now()`).
3. Cria nova linha (`owner_type`/`owner_id` do body, `started_at = now()`, `ended_at = null`).
4. **Sem aprovação do novo dono na v1** — efeito imediato (ver seção 2, corte de escopo deliberado).

### Desativar veículo — `PATCH /vehicles/{id}` com `status = "inactive"`

Soft delete — não existe `DELETE` físico, porque o histórico de propriedade deve sobreviver mesmo que o veículo saia de operação.

---

## 5. Tratamento de erros

Reaproveita a hierarquia `AppError` do `api-auth` (`ValidationError` 422, `ConflictError` 409, `NotFoundError` 404, `ForbiddenError` 403) e o mesmo formato de resposta:

```json
{ "error": { "code": "PLATE_ALREADY_EXISTS", "message": "...", "details": null } }
```

Casos específicos do Fleet: placa duplicada → 409 (`PLATE_ALREADY_EXISTS`), transferência por quem não é o dono vigente → 403, veículo inexistente → 404.

---

## 6. Segurança

- Mesma secret key do projeto Supabase (`core-db`) usada pelo `api-auth` — Fleet nunca expõe a secret ao client, só o backend fala com o Supabase.
- RLS habilitado, sem policy de escrita para `anon`/`authenticated` — toda mutação passa pelo backend.
- Validação de Bearer token: mesmo mecanismo do `api-auth` (`supabase.auth.get_user`), já que os tokens são emitidos pelo mesmo Supabase Auth.
- CORS restrito por variável de ambiente, sem default hardcoded — mesmo padrão do `api-auth`.

---

## 7. Roteiro de implementação em fases

| Fase | Entrega |
|---|---|
| **0 — Setup** | Estrutura `app/`, config, client Supabase (reaproveitar padrão do `api-auth`) |
| **1 — Schema + RLS** | `vehicles`, `vehicle_ownerships`, trigger `updated_at`, RLS |
| **2 — CRUD de veículo** | `POST/GET/PATCH /vehicles`, `GET /vehicles/{id}`, unicidade de placa |
| **3 — Transferência** | `POST /vehicles/{id}/transfer` |
| **4 — Desativação** | `status = inactive` via `PATCH` |
| **5 — Integração com matching** | Endpoint(s) de leitura usados pelo `api-matching` para checar capacidade/compatibilidade |
| **6 — Backlog (pós-TCC)** | `vehicle_assignments` (empréstimo/atribuição de motorista); fluxo de aprovação de transferência em duas etapas; transferência administrativa para dono ausente/indisponível; histórico de troca de acoplamento como entidade própria; integração com base externa de especificações por marca/modelo/ano; testes automatizados |

---

## 8. Decisões tomadas

- **Stack**: Python/FastAPI, mesmo padrão do `api-auth` (routers finos, services concentram lógica, sem repository pattern). Decidido em vez de Rust porque Fleet é CRUD + histórico relacional (request/response comum), sem volume/concorrência que justifique a complexidade extra — critério aplicado consistentemente no resto da plataforma: Rust reservado para `api-chat`/`api-tracking`, os únicos casos reais de alta concorrência/I/O assíncrono contínuo (WebSockets, GPS em alta frequência).
- **Banco compartilhado**: Fleet usa o mesmo projeto Supabase (`core-db`) do `api-auth`, com tabelas próprias, em vez de um Postgres dedicado por serviço. Trade-off consciente de TCC/verba zero — evita multiplicar bancos gratuitos para gerenciar/migrar. Consequência aceita: `vehicle_ownerships.owner_id` referencia `public.profiles` com FK real (acoplamento de schema entre serviços que não existiria se fossem bancos separados); documentado aqui para não ser confundido com acidente de design.
- **Escopo reduzido deliberadamente** (ver seção 2): sem `vehicle_assignments`, sem fluxo de aprovação de transferência, sem histórico de troca de acoplamento — em favor de entregar uma fatia vertical funcional (cadastro → propriedade → dado pronto para matching) dentro do prazo de TCC.
- **Acoplamento como campo mutável, não entidade**: ver seção 3. Reavaliar se o TCC evoluir para cobrir o caso "contratante fornece equipamento" com mais profundidade.
- **Sem `DELETE` físico de veículo**: só desativação (`status`), para preservar o histórico de propriedade.

Ver também a memória de projeto `escort-in-road-architecture` (histórico completo da discussão de arquitetura da plataforma, incluindo os cortes de escopo e a decisão de gateway via Caddy).
