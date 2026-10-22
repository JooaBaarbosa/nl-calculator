# nl-calculator — Interface web — Design

- **Data:** 2026-10-21
- **Status:** aprovado em conversa; aguardando revisão da spec escrita
- **Autor:** JoaoBarbosa (com Claude)
- **Base:** `docs/superpowers/specs/2026-10-19-nl-calculator-design.md` (v1: avaliador, solver, API, CLI)

## 1. Objetivo

Dar ao nl-calculator uma **página web para o usuário final**, que roda localmente com um
comando (`docker compose up --build`) e abre em `http://localhost:8000`. A v1 deixou interface
web fora do escopo; esta spec a adiciona sem mudar nenhuma rota existente da API.

**Critérios de sucesso**

- Quem clona o repositório, preenche o `.env` e roda `docker compose up --build` usa a
  calculadora no navegador sem instalar Python nem Node.
- Quem não tem Docker consegue rodar com `npm run build` + `uvicorn`.
- Um revisor técnico vê: React + TypeScript estrito, componentes pequenos e testados, imagem
  Docker multi-stage enxuta e segura, CI cobrindo Python, front-end e imagem.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Tecnologia da página | React + TypeScript com Vite |
| Como roda localmente | Docker Compose (principal); sem Docker como alternativa |
| Arquitetura dos containers | Uma imagem multi-stage: Node compila, Python serve página e API |
| Endereço | Página e API na mesma origem (`localhost:8000`), sem CORS e sem proxy |
| Node | 24 (LTS), fixado em `.nvmrc` e `engines` |
| Testes do front-end | Vitest + React Testing Library + jsdom |
| Idioma da interface | pt-BR |

Descartados: HTML/JS puro (o usuário preferiu React + TS); dois processos sempre (dois
terminais e CORS); dois serviços com nginx (configuração demais para uso local — fica para o
projeto 3 do portfólio); containers em modo de desenvolvimento (ruim para o usuário final).

## 3. A página

### 3.1 Tela

Tela única:

- Título "nl-calculator" e a frase "Pergunte em português. O Claude interpreta, o código calcula."
- Campo de pergunta com rótulo e botão "Calcular".
- Quatro exemplos clicáveis: "Quanto é 15% de 3.200?", "Qual a raiz quadrada de 144?",
  "15% de 3.200 dividido em 6 parcelas", "2 elevado a 10".
- Cartão de resultado: número em destaque (`result`), explicação (`answer`), lista de passos,
  e rodapé com `model` e total de tokens (`input_tokens + output_tokens`).
- Lista "Histórico desta sessão" com as perguntas anteriores, da mais recente para a mais antiga.

### 3.2 Comportamento

| Situação | Comportamento |
|---|---|
| Enviar | Enter no campo ou clique no botão; envia a pergunta sem espaços nas pontas |
| Pergunta vazia ou só espaços | Botão desabilitado; Enter não envia |
| Requisição em andamento | Botão desabilitado com o texto "Calculando…"; novos envios ignorados |
| Sucesso com `result` | Cartão com o número em destaque, explicação, passos e rodapé |
| Sucesso com `result: null` | Cartão com a explicação e os passos (se houver); sem número em destaque |
| Passo com `error` | Exibido com estilo de erro: `expressão → erro: mensagem` |
| Erro da API | Alerta (`role="alert"`) com a mensagem amigável da seção 3.3; o resultado anterior some |
| Clique em exemplo | Preenche o campo e envia |
| Clique em item do histórico | Mostra o resultado guardado daquela pergunta **sem chamar a API** |
| Histórico | Só em memória (estado do React); recarregar a página apaga; guarda apenas sucessos |

Tema claro/escuro por `prefers-color-scheme`. Layout responsivo (funciona a partir de 320 px de
largura). Acessibilidade: campo com `<label>`, foco visível, cartão de resultado em região
`aria-live="polite"`.

### 3.3 Erros

`calculate()` devolve `{ ok: SolveResult }` ou `{ error: { code, message } }`. Mapeamento:

| Situação da resposta | `code` | Mensagem na tela |
|---|---|---|
| HTTP 503 `not_configured` | `not_configured` | "A chave da Anthropic não está configurada. Preencha ANTHROPIC_API_KEY no arquivo .env e reinicie." |
| HTTP 429 `rate_limited` | `rate_limited` | "Muitas requisições à Anthropic. Tente de novo em instantes." |
| HTTP 502 `upstream_error` | `upstream_error` | "A Anthropic não respondeu. Tente de novo." |
| HTTP 422 com `{error}` (`refused`, `truncated`, `max_iterations`) | o código recebido | a `message` recebida |
| HTTP 422 de validação do FastAPI (`{detail: [...]}`) | `invalid_question` | "A pergunta precisa ter entre 1 e 500 caracteres." |
| `fetch` rejeita (servidor fora do ar) | `network_error` | "Não foi possível falar com o servidor. Ele está rodando?" |
| Corpo que não é JSON, ou status inesperado | `unexpected_response` | "Resposta inesperada do servidor (HTTP <status>)." |
| Código desconhecido com `{error}` | o código recebido | a `message` recebida |

### 3.4 Organização (`web/`)

| Arquivo | Responsabilidade |
|---|---|
| `src/types.ts` | Tipos `Step`, `Usage`, `SolveResult`, `ApiError`, `CalculateOutcome`, espelhando os modelos Pydantic |
| `src/api.ts` | `calculate(question: string): Promise<CalculateOutcome>` — `POST /calculate` e tradução de respostas |
| `src/errors.ts` | `friendlyMessage(error: ApiError): string` |
| `src/App.tsx` | Estado (pergunta, carregando, resultado atual, erro, histórico) e composição da tela |
| `src/components/QuestionForm.tsx` | Campo + botão; recebe `value`, `loading`, `onChange`, `onSubmit` |
| `src/components/Examples.tsx` | Botões de exemplo; recebe `onPick` |
| `src/components/ResultCard.tsx` | Cartão de resultado; recebe `SolveResult` |
| `src/components/StepList.tsx` | Lista de passos; recebe `Step[]` |
| `src/components/History.tsx` | Lista do histórico; recebe itens e `onSelect` |
| `src/styles.css` | CSS próprio com variáveis de tema; sem framework de CSS |
| `src/main.tsx` | Ponto de entrada |

Sem roteador, sem biblioteca de estado, sem biblioteca de componentes.
Os tipos em `types.ts` são mantidos à mão; o risco de divergir do Python é aceito nesta versão.

## 4. Como a página é servida

- `vite build` grava em `src/nl_calculator/static/` (`build.outDir` relativo, `emptyOutDir: true`).
  A pasta entra no `.gitignore`.
- `pyproject.toml`: `[tool.hatch.build] artifacts = ["src/nl_calculator/static/**"]`, para os
  arquivos gerados entrarem no pacote instalado apesar do `.gitignore`.
- `api.py` ganha `mount_static(app: FastAPI, directory: Path) -> None`, chamada no fim do módulo
  com `Path(__file__).parent / "static"`, **depois** de todas as rotas da API:
  - se `directory/index.html` existe: monta `StaticFiles(directory=directory, html=True)` em `/`;
  - senão: registra `GET /` devolvendo uma página HTML curta (status 200) com a instrução
    "Interface não compilada: rode `npm run build` em `web/`, ou use `docker compose up --build`."
- Nenhuma rota existente muda: `/calculate`, `/health`, `/docs`, `/openapi.json` continuam iguais.
- Modo de desenvolvimento: `vite` em `localhost:5173` com `server.proxy` repassando `/calculate`
  e `/health` para `http://127.0.0.1:8000`.

## 5. Docker

**`Dockerfile`** (multi-stage):

1. Etapa `web` (`node:24-alpine`): `npm ci` a partir de `package.json` + `package-lock.json`,
   depois `npm run build` (gera `/app/src/nl_calculator/static`).
2. Etapa final (`ghcr.io/astral-sh/uv:python3.14-bookworm-slim`):
   - `uv sync --locked --no-dev --no-install-project` só com `pyproject.toml`, `uv.lock`,
     `.python-version`, `README.md` (camada de dependências reaproveitável);
   - copia `src/` e os estáticos da etapa `web`;
   - `uv sync --locked --no-dev --no-editable`;
   - roda como usuário sem privilégios;
   - `EXPOSE 8000`; `HEALTHCHECK` chamando `/health` com `urllib`;
   - `CMD` = uvicorn em `0.0.0.0:8000`.

A imagem final não contém Node, `node_modules`, ferramentas de teste nem a chave.

**`compose.yaml`**: serviço `app`, `build: .`, porta `127.0.0.1:8000:8000`,
`env_file` apontando para `.env` com `required: false`.

**`.dockerignore`**: `.env`, `.git`, `.venv`, `web/node_modules`, `src/nl_calculator/static`,
caches (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`), `docs/`, `.superpowers/`.

**Segurança:** a chave só entra em tempo de execução via `.env`; a porta só escuta em
`127.0.0.1` porque qualquer pessoa na rede que acessasse a página gastaria os créditos do dono.

## 6. Testes

### 6.1 Front-end (Vitest + React Testing Library + jsdom; `fetch` substituído por dublê)

| Alvo | Casos |
|---|---|
| `api.ts` | 200 → `ok`; 503, 429, 502 e 422 com `{error}` → `error` com o código recebido; 422 com `{detail}` → `invalid_question`; `fetch` rejeitado → `network_error`; corpo não-JSON → `unexpected_response`; requisição é `POST /calculate` com JSON `{question}` |
| `errors.ts` | mensagem de cada código da seção 3.3; código desconhecido usa a `message` recebida |
| `ResultCard` / `StepList` | número em destaque quando há `result`; ausente quando `result` é `null`; passo com erro marcado e com a mensagem; rodapé com modelo e soma de tokens |
| `App` | envio mostra "Calculando…" e depois o resultado; botão desabilitado com pergunta vazia/só espaços; pergunta enviada sem espaços nas pontas; exemplo preenche e envia; item do histórico mostra o resultado antigo sem nova chamada a `fetch`; erro aparece em `role="alert"` |

Qualidade: `tsc --noEmit` com `strict: true`; ESLint com `typescript-eslint` e
`eslint-plugin-react-hooks`; cobertura mínima de 90% (linhas) no Vitest.

### 6.2 Python (novos, em `tests/test_api.py`)

- Com diretório temporário contendo `index.html`: `mount_static` faz `GET /` devolver esse HTML;
  `/health` continua respondendo.
- Sem `index.html`: `GET /` devolve 200 com a instrução de compilar; `/health` continua respondendo.

A cobertura mínima do Python (90%) e as verificações atuais (`ruff`, `mypy --strict`) continuam.

### 6.3 Verificação manual antes de entregar

`docker compose up --build`, abrir `http://localhost:8000` no navegador, conferir a página e,
se houver `.env` com chave, fazer uma pergunta real. Print da página para o README.

## 7. CI

Três jobs em paralelo em `.github/workflows/ci.yml`:

1. `python` — o job atual, sem mudanças.
2. `web` — Node 24 (`actions/setup-node`, cache do npm) → `npm ci` → `npm run lint` →
   `npm run typecheck` → `npm run test -- --coverage` → `npm run build`.
3. `docker` — `docker build -t nl-calculator .`; sobe o container sem chave; espera `/health`
   responder 200; confere que `GET /` devolve HTML contendo `<div id="root">`; derruba o container.

## 8. README

- Print da página no topo.
- Diagrama com o navegador: `navegador ──► página (React) ──► API ──► solver …`.
- Seção "Rodando" com três caminhos: Docker (principal), sem Docker, desenvolvimento.

## 9. Fora do escopo

Login, deploy na internet, histórico persistente, streaming da resposta, internacionalização,
testes ponta a ponta com navegador automatizado, geração automática dos tipos TypeScript a
partir do OpenAPI.
