# nl-calculator — Design

- **Data:** 2026-10-19
- **Status:** aprovado em conversa; aguardando revisão da spec escrita
- **Autor:** JoaoBarbosa (com Claude)

## 1. Objetivo

Primeiro projeto do portfólio de AI Engineer: uma **calculadora em linguagem natural**.
O usuário escreve uma pergunta ("quanto é 15% de 3.200 dividido em 6 parcelas?") e recebe
o resultado exato, a(s) expressão(ões) usada(s) e uma explicação curta.

A mensagem técnica do projeto: **o LLM interpreta, código determinístico executa.**
O Claude nunca faz conta; ele traduz a pergunta para uma expressão e chama uma ferramenta.
O cálculo é feito por um avaliador seguro, exato (`Decimal`) e testável.

**Critérios de sucesso**

- Um recrutador entende o projeto pelo README em menos de 5 minutos.
- Um revisor técnico vê: avaliador seguro sem `eval`, loop de tool calling explícito,
  tratamento de erros completo, testes ≥ 90% de cobertura, CI verde, avaliação com o modelo real.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Interface | API FastAPI + CLI (sem interface web) |
| LLM | Claude, modelo `claude-opus-5-5` (configurável) |
| Escopo matemático | `+ - * /`, `**`, `sqrt()`, parênteses, sinal unário; porcentagem via tradução do LLM |
| Abordagem | Uma única ferramenta `calculate(expression)` + avaliador seguro próprio |
| Linguagem | Python 3.14 (`requires-python = ">=3.14,<3.15"`, `.python-version` = `3.14.8`) |
| Ferramentas | `uv`, `ruff`, `mypy --strict`, `pytest` + `pytest-cov`, GitHub Actions |
| Loop de tool use | Manual (não usa o Tool Runner beta) |

Abordagens descartadas: uma ferramenta por operação (mais idas e voltas, mais custo e erro)
e deixar o LLM calcular sozinho (LLMs erram contas).

## 3. Arquitetura

```
pergunta ──► cli.py / api.py ──► solver.py ◄──► Claude (tool: calculate)
                                    │
                                    ▼
                              evaluator.py ──► Decimal | CalculationError
```

Estrutura do pacote (`src/nl_calculator/`):

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `evaluator.py` | `evaluate(expression: str) -> Decimal`; não conhece o LLM | stdlib (`ast`, `decimal`) |
| `solver.py` | Conversa com o Claude, executa as chamadas, monta `SolveResult` | `evaluator`, `anthropic` |
| `api.py` | FastAPI: `POST /calculate`, `GET /health` | `solver`, `config` |
| `cli.py` | Comando `calc` (argparse) | `solver`, `config` |
| `config.py` | `Settings` via `pydantic-settings` (variáveis de ambiente / `.env`) | `pydantic-settings` |

### Configuração (`Settings`)

| Variável | Padrão | Uso |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (obrigatória para CLI/API) | Autenticação |
| `NLCALC_MODEL` | `claude-opus-5-5` | Modelo |
| `NLCALC_EFFORT` | `low` | `output_config.effort` |
| `NLCALC_MAX_ITERATIONS` | `5` | Limite de voltas do loop |
| `NLCALC_MAX_EXPRESSION_LENGTH` | `200` | Limite do avaliador |
| `NLCALC_MAX_NODES` | `100` | Limite do avaliador |
| `NLCALC_MAX_EXPONENT` | `1000` | Limite do avaliador |

## 4. Avaliador (`evaluator.py`)

**Entrada não confiável.** A string vem do LLM.

1. `ast.parse(expression, mode="eval")` — apenas gera a árvore, não executa.
2. Percorre a árvore aceitando somente uma lista fechada de nós. Qualquer outro nó → `forbidden_element`.
3. Literais numéricos viram `Decimal` a partir do texto do literal (`0.1 + 0.2 == Decimal("0.3")`).
4. Nunca usa `eval`, `exec` ou `compile` para executar.

**Aceito**

| Nó AST | Exemplo |
|---|---|
| `Expression`, `Constant` (int/float, não bool) | `3200`, `0.15` |
| `BinOp` com `Add`, `Sub`, `Mult`, `Div`, `Pow` | `3200 * 0.15 / 6`, `2 ** 10`, `27 ** (1/3)` |
| `UnaryOp` com `UAdd`, `USub` | `-(5 - 8)` |
| `Call` com `func` = `Name("sqrt")`, 1 argumento posicional, sem keywords | `sqrt(144)` |

**Rejeitado de propósito:** `%` (`Mod` — ambíguo com porcentagem), `^` (`BitXor`), qualquer
outro operador, `Name` fora de `sqrt(...)`, `Attribute`, outras funções, strings, bools,
números complexos, coleções, lambdas, comparações.

**Limites:** comprimento ≤ `max_expression_length`; nós na árvore ≤ `max_nodes`;
`|expoente| ≤ max_exponent`; contexto `Decimal` local com `prec=28` e `Emax`/`Emin` limitados,
com `Overflow` virando `too_large`.

**Erros** — `CalculationError(code: str, message: str)`:

| Código | Quando |
|---|---|
| `syntax_error` | `ast.parse` falha ou expressão vazia |
| `forbidden_element` | Nó/operador/função fora da lista |
| `division_by_zero` | Divisão por zero |
| `domain_error` | `sqrt` de negativo; base negativa com expoente fracionário; `0 ** negativo` |
| `too_large` | Expoente acima do limite ou overflow do contexto |
| `too_complex` | Expressão longa demais ou com nós demais |

A mensagem é escrita para o Claude entender e corrigir (ex.: "Operador '%' não é suportado;
para porcentagem use '/ 100'.").

**Exatidão:** `+ - *` e `**` com expoente inteiro são exatos (dentro de 28 dígitos);
`/`, `sqrt` e `**` com expoente fracionário são arredondados a 28 dígitos significativos
(ex.: `1/3`, `27 ** (1/3)`). Os testes desses casos comparam com tolerância ou com o valor
arredondado esperado.

**Saída:** `Decimal` sem arredondamento adicional. A serialização para string usa notação comum
(sem expoente) para valores de magnitude razoável e remove zeros à direita (`80`, não `80.00`).

## 5. Solver (`solver.py`)

**Ferramenta**

```json
{
  "name": "calculate",
  "description": "Avalia uma expressão aritmética com precisão exata. Suporta + - * / ** sqrt() e parênteses. Use ponto como separador decimal. Para porcentagem, converta: '15% de 3200' -> '3200 * 15 / 100'. Não use % nem ^.",
  "strict": true,
  "input_schema": {
    "type": "object",
    "properties": {"expression": {"type": "string"}},
    "required": ["expression"],
    "additionalProperties": false
  }
}
```

**System prompt:** sempre usar `calculate` para qualquer conta, nunca calcular de cabeça;
responder no idioma da pergunta; explicar em 1–2 frases; se a pergunta não for um cálculo,
dizer isso sem chamar a ferramenta.

**Requisição:** `client.beta.messages.create` com `model`, `max_tokens=16000`,
`output_config={"effort": settings.effort}`, `tools=[calculate]`, `tool_choice` automático
(o Opus 5.5 não aceita escolha forçada), `betas=["server-side-fallback-2026-07-01"]` e
`fallbacks="default"`. Sem streaming.

**Loop**

```
messages = [{"role": "user", "content": question}]
for _ in range(max_iterations):
    response = create(...)
    messages.append({"role": "assistant", "content": response.content})  # sem editar
    match response.stop_reason:
        "tool_use":  executar TODOS os blocos tool_use no evaluator;
                     enviar todos os tool_result numa única mensagem user;
                     CalculationError -> tool_result com is_error=true e a mensagem
        "end_turn":  montar SolveResult e retornar
        "refusal":   SolverError("refused")
        "max_tokens":SolverError("truncated")
raise SolverError("max_iterations")
```

- O `input` da ferramenta é lido do objeto já parseado pelo SDK; `expression` ausente ou
  não-string vira `tool_result` de erro.
- Cada chamada vira um `Step(expression, result | None, error | None)`.
- **`result` = resultado da última chamada bem-sucedida**, nunca extraído do texto do Claude.
  Sem chamadas bem-sucedidas → `result = None`.
- `answer` = concatenação dos blocos `text` da última resposta.
- `usage` = soma de `input_tokens` e `output_tokens` de todas as respostas.

**`SolveResult`** (Pydantic):

```json
{
  "answer": "15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.",
  "result": "80",
  "steps": [{"expression": "3200 * 15 / 100 / 6", "result": "80", "error": null}],
  "model": "claude-opus-5-5",
  "usage": {"input_tokens": 812, "output_tokens": 94}
}
```

**`SolverError(code, message)`**

| Código | Origem |
|---|---|
| `refused` | `stop_reason == "refusal"` |
| `truncated` | `stop_reason == "max_tokens"` |
| `max_iterations` | Limite de voltas atingido |
| `rate_limited` | `anthropic.RateLimitError` |
| `upstream_error` | `anthropic.APIConnectionError` ou `anthropic.APIStatusError` |

Exceções do SDK são tratadas por classe, da mais específica para a mais geral; nunca por texto.

O `Solver` recebe o cliente Anthropic por injeção (construtor), para permitir um cliente falso nos testes.

## 6. API (`api.py`)

| Rota | Entrada | Saída |
|---|---|---|
| `POST /calculate` | `{"question": str}` (1–500 caracteres) | `200` + `SolveResult` |
| `GET /health` | — | `200` + `{"status": "ok"}` (não chama o LLM) |

| Situação | HTTP | Corpo |
|---|---|---|
| Validação | `422` | padrão do FastAPI |
| `rate_limited` | `429` | `{"error": {"code", "message"}}` |
| `upstream_error` | `502` | idem |
| `refused`, `truncated`, `max_iterations` | `422` | idem |

O solver é fornecido por dependência do FastAPI (`Depends`), para ser substituído nos testes.
Execução: `uv run uvicorn nl_calculator.api:app`. Documentação automática em `/docs`.

## 7. CLI (`cli.py`)

```
$ calc "quanto é 15% de 3200 dividido em 6 parcelas?"
15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.

Resultado: 80
Passos:
  3200 * 15 / 100 / 6 = 80
```

- `main(argv: list[str] | None = None) -> int`; entry point `calc` no `pyproject.toml`.
- `--json`: imprime o `SolveResult` em JSON.
- Passo com erro aparece como `expressão -> erro: mensagem`.
- Saída: `0` sucesso; `1` `SolverError` (mensagem em stderr); `2` erro de uso ou configuração
  (ex.: `ANTHROPIC_API_KEY` ausente).

## 8. Testes

Todos sem rede e sem chave de API.

| Camada | Estratégia | Casos mínimos |
|---|---|---|
| `evaluator` | Unidade, parametrizado | precisão decimal; precedência; parênteses; unário; `**` inteiro e fracionário; `sqrt`; cada código de erro (`1/0`, `sqrt(-1)`, `(-8) ** 0.5`, `9**9**9`, `__import__('os')`, `x + 1`, `2 % 3`, `2 ^ 3`, `"a"`, `True`, `1j`, expressão longa, muitos nós, vazia) |
| `solver` | Cliente falso com respostas roteirizadas | uma chamada; várias chamadas na mesma resposta (um único user com todos os `tool_result`); erro devolvido e corrigido; sem cálculo → `result` nulo; `refusal`; `max_tokens`; `max_iterations`; `RateLimitError`; `APIConnectionError`; `usage` somado |
| `api` | `TestClient` + override da dependência | 200; 422 de validação; 429; 502; 422 de solver; `/health` |
| `cli` | `main(argv)` + `capsys` | saída de texto; `--json`; códigos 0, 1, 2 |

Cobertura mínima de 90% (falha no CI abaixo disso); meta de 100% no `evaluator`.

## 9. Avaliação com o modelo real

- `evals/questions.yaml`: ~15 perguntas com resposta esperada (porcentagem, parcelas, raiz,
  potência, frases ambíguas, uma pergunta que não é cálculo → `result` nulo).
- `evals/run.py`: roda as perguntas com o Claude real e imprime acerto por pergunta,
  taxa de acerto e custo estimado a partir do `usage`.
- Execução manual (`uv run python evals/run.py`); **não roda no CI** porque gasta créditos.
  Resultado mais recente registrado no README.

## 10. CI (GitHub Actions)

Em push e pull request: `uv sync` (Python 3.14) → `ruff check` → `ruff format --check`
→ `mypy --strict src/` → `pytest --cov --cov-fail-under=90`.

## 11. Repositório

- Pasta local: `claude-projetos/nl-calculator/`.
- GitHub: `JooaBaarbosa/nl-calculator`, público, criado somente após confirmação do usuário.
- `.env.example` com `ANTHROPIC_API_KEY=`; `.env` no `.gitignore`. A chave nunca é commitada.
- Licença MIT.
- README: apresentação em uma frase, exemplo de terminal, diagrama, "Por que o LLM não faz
  a conta" (segurança, sem `eval`), como rodar (CLI e API), decisões técnicas, resultados da avaliação.

## 12. Fora do escopo (v1)

Interface web, deploy, histórico/banco de dados, streaming, outros provedores de LLM,
matemática financeira, conversão de unidades, funções científicas.
