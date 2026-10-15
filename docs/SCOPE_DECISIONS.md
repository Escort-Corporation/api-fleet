# Decisões de escopo — sprints 1 a 5 do TCC

Separado do `ARCHITECTURE.md` (que documenta outros cortes arquiteturais
anteriores, ex: `vehicle_assignments` adiado pós-TCC). Aqui: o que foi
cortado/simplificado/entregue especificamente das sprints 1-5.

## Implementado neste serviço

### Filtro de compatibilidade por eixos (item 3 do escopo original)
`vehicles.axle_count` (coluna nova, nullable, `migrations/002_fleet_axle_count.sql`)
é o dado que sustenta o filtro — carroceria (`attachment_type`) e tonelagem
(`weight_capacity_kg`) já existiam antes desta leva de mudanças. **O filtro em
si (frete exige N eixos mínimos) vive no `api-matching`**, que lê esta coluna
direto do mesmo Postgres compartilhado; este serviço só expõe o dado via
`GET /vehicles/{id}/capacity` (projeção já usada pelo matching).

## Não se aplica a este serviço

Cálculo de desvio de rota, antecipação de recebíveis, marketplace de
anúncios, planos SaaS e integração ANTT são domínio de frete/pagamento/
identidade — o `api-fleet` só cuida do veículo físico e sua propriedade, não
toca em nenhum desses itens. Ver `api-freight/docs/SCOPE_DECISIONS.md` e
`api-auth/docs/SCOPE_DECISIONS.md` pra detalhes de cada um.
