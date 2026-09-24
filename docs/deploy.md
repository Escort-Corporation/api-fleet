# Deploy — opções avaliadas e decisão

Contexto: prazo é a apresentação do TCC. Objetivo é ter o backend acessível pelo
app mobile (React Native) e pelo painel web (admins/usuários não caminhoneiros),
com custo zero, funcionando de ponta a ponta até o dia da banca.

## Opções de hospedagem consideradas

- **Render (escolhido)** — free tier para web services. Sem custo, mas cada
  serviço "dorme" após ~15min sem tráfego. Mitigado com keep-alive (ver
  abaixo).
- **Fly.io / Railway** — não escolhidos; objetivo é só a janela do TCC, não
  produção contínua.

## Banco de dados

- **MongoDB Atlas free tier (escolhido)** — gerenciado, replica set e backup
  inclusos, sempre ativo. Não usamos o "private service" de MongoDB do
  Render (sem backup automático confiável, sem replica set gerenciado).

## Manter os serviços "acordados" (keep-alive)

Free tier do Render dorme sem tráfego. Solução: GitHub Actions com
`schedule` (cron) fazendo `curl` no endpoint `/health` de cada serviço a
cada ~10-13min, 24/7 até o dia da apresentação. Workflow centralizado em
api-core.

## CORS

- App mobile (React Native) não sofre CORS.
- Painel web dos admins vai em **Vercel** — configurar `cors_origin_list`
  (env var) com o domínio `*.vercel.app` do painel (ou domínio final).

## Pendências

- Domínio final do painel web (Vercel) ainda não definido — CORS configurado
  provisoriamente com wildcard `*.vercel.app`.
