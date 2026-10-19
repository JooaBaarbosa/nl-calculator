# nl-calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calculadora em linguagem natural: o Claude traduz a pergunta para uma expressão e chama a ferramenta `calculate`; um avaliador seguro (AST + `Decimal`) faz a conta. Exposta por API FastAPI e CLI.

**Architecture:** `evaluator` (stdlib pura, sem LLM) ← `solver` (loop manual de tool calling com o SDK `anthropic`) ← `api` (FastAPI) e `cli` (argparse). `config` lê variáveis de ambiente com `pydantic-settings`. O solver recebe a função `create` por injeção, então tudo é testável sem rede.

**Tech Stack:** Python 3.14, uv, anthropic (Python SDK), FastAPI, uvicorn, pydantic, pydantic-settings, pytest, pytest-cov, ruff, mypy, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-19-nl-calculator-design.md`

## Global Constraints

- `requires-python = ">=3.14,<3.15"`; `.python-version` = `3.14.8`.
- Modelo padrão `claude-opus-5-5`; `effort` padrão `low`; `max_tokens=16000`; sem streaming.
- Requisições ao Claude via `client.beta.messages.create` com `betas=["server-side-fallback-2026-07-01"]` e `fallbacks="default"`. Nunca `tool_choice` forçado (`any`/`tool` → 400 no Opus 5.5).
- Avaliador: nunca `eval`/`exec`/`compile`; `prec=28`; limites padrão 200 caracteres / 100 nós / expoente ±1000.
- `result` do `SolveResult` vem sempre da última chamada bem-sucedida de `calculate`, nunca do texto do Claude.
- Exceções do SDK tratadas por classe (`RateLimitError` → `APIConnectionError` → `APIStatusError`), nunca por texto.
- Nenhum teste usa rede nem a chave real. `.env` nunca é commitado.
- Cobertura mínima 90% (`fail_under = 90`); `mypy --strict` em `src/`; `ruff check` + `ruff format --check` limpos.
- Mensagens ao usuário e ao Claude em pt-BR; identificadores de código em inglês.
- Todo commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Número no formato brasileiro vindo do LLM** (`3,5`) → o avaliador recusa com `forbidden_element` e uma mensagem que manda usar ponto, para o Claude corrigir. Teste na Task 2 (`test_comma_decimal_hints_dot`).
2. **`.env` copiado do `.env.example` com `ANTHROPIC_API_KEY=` vazio** → `ConfigError` clara, e não um 401 da Anthropic. Teste na Task 3 (`test_empty_api_key_is_rejected`).
3. **Pergunta só com espaços na API** → `422` sem gastar uma chamada ao LLM. Teste na Task 5 (`test_whitespace_question_is_rejected`).
4. **Servidor da API sem chave configurada** → `503 not_configured`, e não um 500 genérico. Teste na Task 5 (`test_missing_api_key_returns_503`).
5. **Saída do CLI redirecionada no Windows (cp1252) com caracteres como `≈`** → não pode quebrar com `UnicodeEncodeError`. Teste na Task 6 (`test_configure_streams_replaces_unencodable`).

---

## File Structure

```
nl-calculator/
├── .github/workflows/ci.yml        # Task 8
├── .env.example                    # Task 1
├── .gitignore                      # Task 1
├── .python-version                 # Task 1
├── LICENSE                         # Task 1
├── README.md                       # Task 1 (mínimo) → Task 8 (completo)
├── pyproject.toml                  # Task 1, deps adicionadas nas Tasks 3–6
├── uv.lock                         # gerado pelo uv
├── evals/
│   ├── questions.yaml              # Task 7
│   └── run.py                      # Task 7
├── src/nl_calculator/
│   ├── __init__.py                 # Task 1
│   ├── evaluator.py                # Task 2
│   ├── config.py                   # Task 3
│   ├── solver.py                   # Task 4
│   ├── api.py                      # Task 5
│   └── cli.py                      # Task 6
└── tests/
    ├── conftest.py                 # Task 1
    ├── fakes.py                    # Task 4
    ├── test_package.py             # Task 1
    ├── test_evaluator.py           # Task 2
    ├── test_config.py              # Task 3
    ├── test_solver.py              # Task 4
    ├── test_api.py                 # Task 5
    └── test_cli.py                 # Task 6
```

Todos os comandos rodam na pasta `nl-calculator/`. O repositório git já existe (commit da spec).

---

### Task 1: Esqueleto do projeto

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `LICENSE`, `README.md`, `src/nl_calculator/__init__.py`, `tests/conftest.py`, `tests/test_package.py`

**Interfaces:**
- Consumes: nada
- Produces: pacote `nl_calculator` com `__version__ = "0.1.0"`; fixture autouse `isolated_env` (remove `ANTHROPIC_API_KEY` e `NLCALC_*` do ambiente e muda o diretório para `tmp_path`)

- [ ] **Step 1: Instalar o uv e o Python 3.14**

```powershell
winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements --silent
```

Abra um terminal novo (ou use `$env:USERPROFILE\.local\bin\uv.exe`) e rode:

```bash
uv --version
uv python install 3.14.8
```

Expected: `uv x.y.z` e o Python 3.14.8 instalado. Se a 3.14.8 não existir no índice do uv, use a 3.14.x mais recente disponível e ajuste o `.python-version` para essa versão, avisando o usuário.

- [ ] **Step 2: Criar `pyproject.toml`**

```toml
[project]
name = "nl-calculator"
version = "0.1.0"
description = "Calculadora em linguagem natural: o Claude interpreta, código determinístico calcula."
readme = "README.md"
license = "MIT"
authors = [{ name = "JoaoBarbosa", email = "joao.paula2010@hotmail.com" }]
requires-python = ">=3.14,<3.15"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/nl_calculator"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=nl_calculator --cov-report=term-missing"

[tool.coverage.report]
fail_under = 90
```

- [ ] **Step 3: Criar os arquivos de apoio**

`.python-version`:
```
3.14.8
```

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
.env
```

`.env.example`:
```
# Copie para .env e preencha. O .env nunca vai para o git.
ANTHROPIC_API_KEY=
# Opcionais:
# NLCALC_MODEL=claude-opus-5-5
# NLCALC_EFFORT=low
# NLCALC_MAX_ITERATIONS=5
```

`LICENSE`:
```
MIT License

Copyright (c) 2026 JoaoBarbosa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`README.md` (provisório; o completo vem na Task 8):
```markdown
# nl-calculator

Calculadora em linguagem natural: o Claude interpreta, código determinístico calcula.
```

`src/nl_calculator/__init__.py`:
```python
"""Calculadora em linguagem natural: o Claude interpreta, código determinístico calcula."""

__version__ = "0.1.0"
```

`tests/conftest.py`:
```python
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Nenhum teste lê a chave real nem o .env do projeto."""
    for name in list(os.environ):
        if name == "ANTHROPIC_API_KEY" or name.startswith("NLCALC_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
```

- [ ] **Step 4: Escrever o teste de fumaça**

`tests/test_package.py`:
```python
import nl_calculator


def test_version() -> None:
    assert nl_calculator.__version__ == "0.1.0"
```

- [ ] **Step 5: Instalar as ferramentas de desenvolvimento**

```bash
uv add --dev pytest pytest-cov ruff mypy
```

Expected: `uv.lock` criado, `.venv` com Python 3.14.

- [ ] **Step 6: Rodar todas as verificações**

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: 1 teste passando, cobertura 100%, ruff e mypy sem erros.

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: scaffold nl-calculator project

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Avaliador seguro

**Files:**
- Create: `src/nl_calculator/evaluator.py`
- Test: `tests/test_evaluator.py`

**Interfaces:**
- Consumes: nada (só stdlib)
- Produces:
  - `@dataclass(frozen=True) class Limits: max_length: int = 200; max_nodes: int = 100; max_exponent: int = 1000`
  - `DEFAULT_LIMITS: Limits`
  - `class CalculationError(Exception)` com atributos `code: str`, `message: str`; `str(err) == f"{code}: {message}"`
  - `def evaluate(expression: str, limits: Limits = DEFAULT_LIMITS) -> Decimal`
  - `def format_decimal(value: Decimal) -> str`

- [ ] **Step 1: Escrever os testes**

`tests/test_evaluator.py`:
```python
from decimal import Decimal

import pytest

from nl_calculator.evaluator import CalculationError, Limits, evaluate, format_decimal


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2", "3"),
        ("0.1 + 0.2", "0.3"),
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("10 / 4", "2.5"),
        ("10 - 12", "-2"),
        ("-(5 - 8)", "3"),
        ("+7", "7"),
        ("2 ** 10", "1024"),
        ("2 ** -2", "0.25"),
        ("-2 ** 2", "-4"),
        ("(-2) ** 3", "-8"),
        ("sqrt(144)", "12"),
        ("3200 * 15 / 100 / 6", "80"),
        ("1_000 + 1", "1001"),
        ("1e3 + 1", "1001"),
        ("  4 * 2  ", "8"),
    ],
)
def test_evaluates_supported_expressions(expression: str, expected: str) -> None:
    assert format_decimal(evaluate(expression)) == expected


def test_division_is_rounded_to_28_digits() -> None:
    assert evaluate("1 / 3") == Decimal("0.3333333333333333333333333333")


def test_fractional_power_is_close() -> None:
    assert abs(evaluate("27 ** (1/3)") - 3) < Decimal("1e-25")


def test_sqrt_irrational() -> None:
    assert str(evaluate("sqrt(2)")).startswith("1.414213562373095048801688724")


@pytest.mark.parametrize(
    ("expression", "code"),
    [
        ("", "syntax_error"),
        ("   ", "syntax_error"),
        ("2 +", "syntax_error"),
        ("1 / 0", "division_by_zero"),
        ("1 / (2 - 2)", "division_by_zero"),
        ("sqrt(-1)", "domain_error"),
        ("(-8) ** 0.5", "domain_error"),
        ("0 ** -1", "domain_error"),
        ("0 ** 0", "domain_error"),
        ("9 ** 9 ** 9", "too_large"),
        ("2 ** 1001", "too_large"),
        ("(10 ** 1000) ** 1000", "too_large"),
        ("1e999", "too_large"),
        ("__import__('os')", "forbidden_element"),
        ("x + 1", "forbidden_element"),
        ("2 % 3", "forbidden_element"),
        ("2 % (1 / 0)", "forbidden_element"),
        ("2 ^ 3", "forbidden_element"),
        ("'a'", "forbidden_element"),
        ("True", "forbidden_element"),
        ("1j", "forbidden_element"),
        ("3,5", "forbidden_element"),
        ("abs(-1)", "forbidden_element"),
        ("sqrt(1, 2)", "forbidden_element"),
        ("sqrt(x=4)", "forbidden_element"),
        ("(1).real", "forbidden_element"),
        ("[1, 2]", "forbidden_element"),
        ("1 < 2", "forbidden_element"),
        ("lambda: 1", "forbidden_element"),
        ("~1", "forbidden_element"),
        ("1" + " + 1" * 70, "too_complex"),
        ("+".join(["1"] * 60), "too_complex"),
    ],
)
def test_rejects_with_code(expression: str, code: str) -> None:
    with pytest.raises(CalculationError) as info:
        evaluate(expression)
    assert info.value.code == code


def test_modulo_hints_percentage() -> None:
    with pytest.raises(CalculationError) as info:
        evaluate("15 % 3200")
    assert "/ 100" in info.value.message


def test_xor_hints_power() -> None:
    with pytest.raises(CalculationError) as info:
        evaluate("2 ^ 3")
    assert "**" in info.value.message


def test_comma_decimal_hints_dot() -> None:
    with pytest.raises(CalculationError) as info:
        evaluate("3,5 * 2")
    assert "ponto" in info.value.message


def test_custom_limits() -> None:
    with pytest.raises(CalculationError) as info:
        evaluate("2 ** 20", Limits(max_exponent=10))
    assert info.value.code == "too_large"


def test_error_str() -> None:
    assert str(CalculationError("syntax_error", "x")) == "syntax_error: x"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("80.00"), "80"),
        (Decimal("1.50"), "1.5"),
        (Decimal("-0"), "0"),
        (Decimal("0.000"), "0"),
        (Decimal("0.001"), "0.001"),
        (Decimal("1E+5"), "100000"),
        (Decimal("1E+30"), "1E+30"),
        (Decimal("1E-25"), "1E-25"),
    ],
)
def test_format_decimal(value: Decimal, expected: str) -> None:
    assert format_decimal(value) == expected
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_evaluator.py -q --no-cov`
Expected: FAIL com `ModuleNotFoundError: No module named 'nl_calculator.evaluator'`

- [ ] **Step 3: Implementar**

`src/nl_calculator/evaluator.py`:
```python
"""Avaliador seguro de expressões aritméticas.

Recebe texto não confiável (vindo do LLM) e devolve um Decimal.
Nunca usa eval/exec: percorre a árvore AST aceitando apenas uma lista fechada de nós.
"""

import ast
import decimal
import math
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Limits:
    max_length: int = 200
    max_nodes: int = 100
    max_exponent: int = 1000


DEFAULT_LIMITS = Limits()


class CalculationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


_CONTEXT = decimal.Context(
    prec=28,
    Emax=999_999,
    Emin=-999_999,
    traps=[decimal.DivisionByZero, decimal.Overflow, decimal.InvalidOperation],
)

_ALLOWED_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


def evaluate(expression: str, limits: Limits = DEFAULT_LIMITS) -> Decimal:
    """Avalia `expression` e devolve o resultado, ou levanta CalculationError."""
    source = expression.strip()
    if not source:
        raise CalculationError("syntax_error", "A expressão está vazia.")
    if len(source) > limits.max_length:
        raise CalculationError(
            "too_complex", f"A expressão passa de {limits.max_length} caracteres."
        )
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise CalculationError("syntax_error", f"Expressão inválida: {exc}.") from exc
    if sum(1 for _ in ast.walk(tree)) > limits.max_nodes:
        raise CalculationError("too_complex", "A expressão tem elementos demais.")
    with decimal.localcontext(_CONTEXT):
        try:
            return _eval(tree.body, limits)
        except decimal.Overflow as exc:
            raise CalculationError("too_large", "O resultado é grande demais.") from exc
        except decimal.InvalidOperation as exc:
            raise CalculationError("domain_error", "Operação matemática indefinida.") from exc


def format_decimal(value: Decimal) -> str:
    """Notação comum para magnitudes razoáveis, sem zeros à direita."""
    if value == 0:
        return "0"
    normalized = value.normalize()
    if -20 <= normalized.adjusted() <= 28:
        return format(normalized, "f")
    return str(normalized)


def _eval(node: ast.expr, limits: Limits) -> Decimal:
    match node:
        case ast.Constant(value=bool()):
            raise CalculationError("forbidden_element", "Valores booleanos não são suportados.")
        case ast.Constant(value=int() | float() as value):
            return _to_decimal(value)
        case ast.Constant():
            raise CalculationError("forbidden_element", "Apenas números são suportados.")
        case ast.UnaryOp(op=ast.UAdd(), operand=operand):
            return +_eval(operand, limits)
        case ast.UnaryOp(op=ast.USub(), operand=operand):
            return -_eval(operand, limits)
        case ast.BinOp(left=left, op=op, right=right):
            _check_operator(op)
            return _binop(op, _eval(left, limits), _eval(right, limits), limits)
        case ast.Call(func=ast.Name(id="sqrt"), args=[arg], keywords=[]):
            return _sqrt(_eval(arg, limits))
        case ast.Call():
            raise CalculationError(
                "forbidden_element", "Só a função sqrt(x), com um argumento, é suportada."
            )
        case ast.Name(id=name):
            raise CalculationError(
                "forbidden_element", f"Variáveis não são suportadas ('{name}'). Use só números."
            )
        case ast.Tuple():
            raise CalculationError(
                "forbidden_element", "Use ponto como separador decimal (3.5, não 3,5)."
            )
        case _:
            raise CalculationError(
                "forbidden_element", f"Elemento não suportado: {type(node).__name__}."
            )


def _to_decimal(value: int | float) -> Decimal:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CalculationError("too_large", "Número grande demais.")
        return Decimal(repr(value))
    return Decimal(value)


def _check_operator(op: ast.operator) -> None:
    if isinstance(op, _ALLOWED_OPERATORS):
        return
    if isinstance(op, ast.Mod):
        raise CalculationError(
            "forbidden_element",
            "Operador '%' não é suportado. Para porcentagem use '/ 100' "
            "(15% de 3200 -> 3200 * 15 / 100).",
        )
    if isinstance(op, ast.BitXor):
        raise CalculationError(
            "forbidden_element", "Operador '^' não é suportado. Para potência use '**'."
        )
    raise CalculationError("forbidden_element", f"Operador não suportado: {type(op).__name__}.")


def _binop(op: ast.operator, left: Decimal, right: Decimal, limits: Limits) -> Decimal:
    match op:
        case ast.Add():
            return left + right
        case ast.Sub():
            return left - right
        case ast.Mult():
            return left * right
        case ast.Div():
            if right == 0:
                raise CalculationError("division_by_zero", "Divisão por zero.")
            return left / right
        case _:
            return _power(left, right, limits)


def _power(base: Decimal, exponent: Decimal, limits: Limits) -> Decimal:
    if abs(exponent) > limits.max_exponent:
        raise CalculationError(
            "too_large", f"O expoente passa do limite de ±{limits.max_exponent}."
        )
    if base == 0 and exponent < 0:
        raise CalculationError("domain_error", "Zero elevado a expoente negativo é indefinido.")
    if base < 0 and exponent != exponent.to_integral_value():
        raise CalculationError(
            "domain_error", "Base negativa com expoente fracionário não tem resultado real."
        )
    return base**exponent


def _sqrt(value: Decimal) -> Decimal:
    if value < 0:
        raise CalculationError("domain_error", "Raiz quadrada de número negativo.")
    return value.sqrt()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_evaluator.py -q`
Expected: todos passam; `evaluator.py` com 100% de cobertura no relatório.

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: sem erros (rode `uv run ruff format .` se o format reclamar).

- [ ] **Step 5: Commit**

```bash
git add src/nl_calculator/evaluator.py tests/test_evaluator.py
git commit -m "feat: add safe AST/Decimal expression evaluator

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Configuração

**Files:**
- Create: `src/nl_calculator/config.py`
- Modify: `pyproject.toml` (dependência e plugin do mypy)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `Limits` (Task 2)
- Produces:
  - `class ConfigError(Exception)`
  - `class Settings(BaseSettings)` com campos `anthropic_api_key: SecretStr | None`, `model: str`, `effort: Literal["low","medium","high","xhigh","max"]`, `max_iterations: int`, `max_expression_length: int`, `max_nodes: int`, `max_exponent: int`
  - `Settings.limits() -> Limits`
  - `Settings.require_api_key() -> str` (levanta `ConfigError` se ausente ou vazia)

- [ ] **Step 1: Adicionar a dependência e o plugin**

```bash
uv add pydantic-settings
```

Em `pyproject.toml`, troque a seção do mypy por:
```toml
[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
```

- [ ] **Step 2: Escrever os testes**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from nl_calculator.config import ConfigError, Settings
from nl_calculator.evaluator import Limits


def test_defaults() -> None:
    settings = Settings()
    assert settings.model == "claude-opus-5-5"
    assert settings.effort == "low"
    assert settings.max_iterations == 5
    assert settings.anthropic_api_key is None
    assert settings.limits() == Limits()


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("NLCALC_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("NLCALC_EFFORT", "high")
    monkeypatch.setenv("NLCALC_MAX_EXPONENT", "10")
    settings = Settings()
    assert settings.require_api_key() == "sk-test"
    assert settings.model == "claude-sonnet-5-5"
    assert settings.effort == "high"
    assert settings.limits() == Limits(max_exponent=10)


def test_reads_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    assert Settings().require_api_key() == "from-file"


def test_invalid_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NLCALC_EFFORT", "turbo")
    with pytest.raises(ValidationError):
        Settings()


def test_missing_api_key_is_rejected() -> None:
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        Settings().require_api_key()


def test_empty_api_key_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        Settings().require_api_key()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_config.py -q --no-cov`
Expected: FAIL com `ModuleNotFoundError: No module named 'nl_calculator.config'`

- [ ] **Step 4: Implementar**

`src/nl_calculator/config.py`:
```python
"""Configuração lida de variáveis de ambiente e do arquivo .env."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from nl_calculator.evaluator import Limits


class ConfigError(Exception):
    """Configuração ausente ou inválida."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NLCALC_", env_file=".env", extra="ignore")

    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    model: str = "claude-opus-5-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_iterations: int = Field(default=5, ge=1)
    max_expression_length: int = Field(default=200, ge=1)
    max_nodes: int = Field(default=100, ge=1)
    max_exponent: int = Field(default=1000, ge=1)

    def limits(self) -> Limits:
        return Limits(
            max_length=self.max_expression_length,
            max_nodes=self.max_nodes,
            max_exponent=self.max_exponent,
        )

    def require_api_key(self) -> str:
        key = self.anthropic_api_key.get_secret_value().strip() if self.anthropic_api_key else ""
        if not key:
            raise ConfigError(
                "ANTHROPIC_API_KEY não está definida. Copie .env.example para .env e preencha."
            )
        return key
```

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: todos os testes passam; ruff e mypy limpos.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/nl_calculator/config.py tests/test_config.py
git commit -m "feat: add environment-based settings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Solver (loop de tool calling)

**Files:**
- Create: `src/nl_calculator/solver.py`, `tests/fakes.py`
- Modify: `pyproject.toml` (dependência `anthropic`)
- Test: `tests/test_solver.py`

**Interfaces:**
- Consumes: `evaluate`, `format_decimal`, `CalculationError`, `Limits`, `DEFAULT_LIMITS` (Task 2); `Settings`, `ConfigError` (Task 3)
- Produces:
  - `class Step(BaseModel): expression: str; result: str | None = None; error: str | None = None`
  - `class Usage(BaseModel): input_tokens: int = 0; output_tokens: int = 0`
  - `class SolveResult(BaseModel): answer: str; result: str | None; steps: list[Step]; model: str; usage: Usage`
  - `class SolverError(Exception)` com `code: str`, `message: str`; códigos `refused`, `truncated`, `max_iterations`, `rate_limited`, `upstream_error`
  - `class Solver: __init__(self, create: Callable[..., Any], *, model: str, effort: str, max_iterations: int = 5, limits: Limits = DEFAULT_LIMITS)`; `solve(self, question: str) -> SolveResult`
  - `def build_solver(settings: Settings) -> Solver` (levanta `ConfigError` sem chave)
  - `tests/fakes.py`: `text()`, `tool_use()`, `response()`, `FakeCreate`, `FakeSolver`, `sample_result()`

- [ ] **Step 1: Adicionar a dependência**

```bash
uv add anthropic
```

- [ ] **Step 2: Criar os dublês de teste**

`tests/fakes.py`:
```python
"""Dublês de teste para o cliente Anthropic e para o Solver."""

from types import SimpleNamespace
from typing import Any

from nl_calculator.solver import SolveResult, Step, Usage


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def tool_use(block_id: str, expression: Any, name: str = "calculate") -> SimpleNamespace:
    payload = {} if expression is None else {"expression": expression}
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def response(
    *content: SimpleNamespace,
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    model: str = "claude-opus-5-5",
) -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeCreate:
    """Substitui client.beta.messages.create devolvendo respostas roteirizadas."""

    def __init__(self, *outcomes: Any) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeSolver:
    def __init__(self, result: SolveResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.questions: list[str] = []

    def solve(self, question: str) -> SolveResult:
        self.questions.append(question)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def sample_result() -> SolveResult:
    return SolveResult(
        answer="15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.",
        result="80",
        steps=[Step(expression="3200 * 15 / 100 / 6", result="80")],
        model="claude-opus-5-5",
        usage=Usage(input_tokens=812, output_tokens=94),
    )
```

- [ ] **Step 3: Escrever os testes**

`tests/test_solver.py`:
```python
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fakes import FakeCreate, response, text, tool_use

from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import Solver, SolverError, build_solver

REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def make_solver(fake: FakeCreate, max_iterations: int = 5) -> Solver:
    return Solver(fake, model="claude-opus-5-5", effort="low", max_iterations=max_iterations)


def test_single_tool_call() -> None:
    first = response(tool_use("t1", "3200 * 15 / 100 / 6"), stop_reason="tool_use")
    fake = FakeCreate(first, response(text("Dá 80 por parcela."), input_tokens=20, output_tokens=7))

    result = make_solver(fake).solve("15% de 3200 em 6 parcelas")

    assert result.result == "80"
    assert result.answer == "Dá 80 por parcela."
    assert [s.model_dump() for s in result.steps] == [
        {"expression": "3200 * 15 / 100 / 6", "result": "80", "error": None}
    ]
    assert result.model == "claude-opus-5-5"
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 12
    assert fake.calls[1]["messages"] == [
        {"role": "user", "content": "15% de 3200 em 6 parcelas"},
        {"role": "assistant", "content": first.content},
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "80"}],
        },
    ]


def test_request_parameters() -> None:
    fake = FakeCreate(response(text("Não é um cálculo.")))
    make_solver(fake).solve("Oi")

    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["max_tokens"] == 16000
    assert call["output_config"] == {"effort": "low"}
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["fallbacks"] == "default"
    assert "tool_choice" not in call
    assert "calculate" in call["system"]
    [tool] = call["tools"]
    assert tool["name"] == "calculate"
    assert tool["strict"] is True
    assert tool["input_schema"]["required"] == ["expression"]
    assert tool["input_schema"]["additionalProperties"] is False


def test_parallel_tool_calls_share_one_user_message() -> None:
    fake = FakeCreate(
        response(tool_use("a", "1 + 1"), tool_use("b", "2 * 5"), stop_reason="tool_use"),
        response(text("Feito.")),
    )
    result = make_solver(fake).solve("q")

    tool_message = fake.calls[1]["messages"][2]
    assert tool_message["role"] == "user"
    assert [r["tool_use_id"] for r in tool_message["content"]] == ["a", "b"]
    assert [r["content"] for r in tool_message["content"]] == ["2", "10"]
    assert result.result == "10"


def test_error_is_returned_to_claude_and_corrected() -> None:
    fake = FakeCreate(
        response(tool_use("t1", "15 % 3200"), stop_reason="tool_use"),
        response(tool_use("t2", "3200 * 15 / 100"), stop_reason="tool_use"),
        response(text("480.")),
    )
    result = make_solver(fake).solve("15% de 3200")

    error_result = fake.calls[1]["messages"][2]["content"][0]
    assert error_result["is_error"] is True
    assert "/ 100" in error_result["content"]
    assert result.steps[0].result is None
    assert result.steps[0].error is not None
    assert result.steps[0].error.startswith("forbidden_element")
    assert result.result == "480"


def test_result_is_last_successful_step() -> None:
    fake = FakeCreate(
        response(tool_use("a", "1 + 1"), tool_use("b", "1 / 0"), stop_reason="tool_use"),
        response(text("Não dá para dividir por zero.")),
    )
    result = make_solver(fake).solve("q")
    assert result.result == "2"
    assert result.steps[1].error is not None


def test_no_calculation_gives_null_result() -> None:
    fake = FakeCreate(response(text("Isso não é um cálculo.")))
    result = make_solver(fake).solve("Qual a capital da França?")
    assert result.result is None
    assert result.steps == []
    assert result.answer == "Isso não é um cálculo."


def test_non_text_blocks_are_ignored_in_answer() -> None:
    fake = FakeCreate(response(SimpleNamespace(type="thinking"), text("Oi.")))
    assert make_solver(fake).solve("q").answer == "Oi."


def test_missing_expression_is_a_tool_error() -> None:
    fake = FakeCreate(
        response(tool_use("t1", None), stop_reason="tool_use"),
        response(text("ok")),
    )
    result = make_solver(fake).solve("q")
    assert fake.calls[1]["messages"][2]["content"][0]["is_error"] is True
    assert result.steps[0].error is not None
    assert result.steps[0].error.startswith("invalid_input")


def test_unknown_tool_is_a_tool_error() -> None:
    fake = FakeCreate(
        response(tool_use("t1", "1 + 1", name="other"), stop_reason="tool_use"),
        response(text("ok")),
    )
    make_solver(fake).solve("q")
    assert fake.calls[1]["messages"][2]["content"][0]["is_error"] is True


@pytest.mark.parametrize(
    ("stop_reason", "code"),
    [("refusal", "refused"), ("max_tokens", "truncated"), ("pause_turn", "upstream_error")],
)
def test_stop_reasons(stop_reason: str, code: str) -> None:
    fake = FakeCreate(response(stop_reason=stop_reason))
    with pytest.raises(SolverError) as info:
        make_solver(fake).solve("q")
    assert info.value.code == code


def test_max_iterations() -> None:
    fake = FakeCreate(
        response(tool_use("a", "1"), stop_reason="tool_use"),
        response(tool_use("b", "2"), stop_reason="tool_use"),
    )
    with pytest.raises(SolverError) as info:
        make_solver(fake, max_iterations=2).solve("q")
    assert info.value.code == "max_iterations"
    assert len(fake.calls) == 2


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            anthropic.RateLimitError(
                "rate", response=httpx.Response(429, request=REQUEST), body=None
            ),
            "rate_limited",
        ),
        (anthropic.APIConnectionError(request=REQUEST), "upstream_error"),
        (
            anthropic.InternalServerError(
                "boom", response=httpx.Response(500, request=REQUEST), body=None
            ),
            "upstream_error",
        ),
    ],
)
def test_sdk_errors(error: Exception, code: str) -> None:
    with pytest.raises(SolverError) as info:
        make_solver(FakeCreate(error)).solve("q")
    assert info.value.code == code


def test_build_solver_requires_key() -> None:
    with pytest.raises(ConfigError):
        build_solver(Settings())


def test_build_solver_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(build_solver(Settings()), Solver)
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `uv run pytest tests/test_solver.py -q --no-cov`
Expected: FAIL com `ModuleNotFoundError: No module named 'nl_calculator.solver'`

- [ ] **Step 5: Implementar**

`src/nl_calculator/solver.py`:
```python
"""Conversa com o Claude: ele traduz a pergunta, o avaliador faz a conta."""

from collections.abc import Callable
from typing import Any

import anthropic
from pydantic import BaseModel

from nl_calculator.config import Settings
from nl_calculator.evaluator import (
    DEFAULT_LIMITS,
    CalculationError,
    Limits,
    evaluate,
    format_decimal,
)

MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """Você é uma calculadora em linguagem natural.
- Para QUALQUER conta, chame a ferramenta calculate. Nunca calcule de cabeça.
- Interprete separadores de milhar e decimais conforme o idioma da pergunta e escreva a \
expressão com ponto decimal e sem separador de milhar (em português, 3.200,5 -> 3200.5).
- Porcentagem: '15% de 3200' -> 3200 * 15 / 100.
- Se a ferramenta devolver erro, corrija a expressão e tente de novo.
- Depois de calcular, responda no idioma da pergunta em 1 ou 2 frases, usando o resultado \
da ferramenta.
- Se a pergunta não for um cálculo, diga isso em uma frase, sem chamar a ferramenta."""

CALCULATE_TOOL: dict[str, Any] = {
    "name": "calculate",
    "description": (
        "Avalia uma expressão aritmética com precisão exata. Suporta + - * / ** sqrt() e "
        "parênteses. Use ponto como separador decimal. Para porcentagem, converta: "
        "'15% de 3200' -> '3200 * 15 / 100'. Não use % nem ^."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
        "additionalProperties": False,
    },
}


class Step(BaseModel):
    expression: str
    result: str | None = None
    error: str | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class SolveResult(BaseModel):
    answer: str
    result: str | None
    steps: list[Step]
    model: str
    usage: Usage


class SolverError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class Solver:
    def __init__(
        self,
        create: Callable[..., Any],
        *,
        model: str,
        effort: str,
        max_iterations: int = 5,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        self._create = create
        self._model = model
        self._effort = effort
        self._max_iterations = max_iterations
        self._limits = limits

    def solve(self, question: str) -> SolveResult:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        steps: list[Step] = []
        usage = Usage()
        for _ in range(self._max_iterations):
            response = self._call(messages)
            usage = Usage(
                input_tokens=usage.input_tokens + response.usage.input_tokens,
                output_tokens=usage.output_tokens + response.usage.output_tokens,
            )
            # O histórico é só acrescentado, nunca editado (exigência do preserved thinking).
            messages.append({"role": "assistant", "content": response.content})
            match response.stop_reason:
                case "tool_use":
                    messages.append(
                        {"role": "user", "content": self._run_tools(response.content, steps)}
                    )
                case "end_turn":
                    return _build_result(response, steps, usage)
                case "refusal":
                    raise SolverError("refused", "O modelo recusou a pergunta.")
                case "max_tokens":
                    raise SolverError("truncated", "A resposta do modelo foi cortada.")
                case other:
                    raise SolverError("upstream_error", f"stop_reason inesperado: {other}.")
        raise SolverError(
            "max_iterations", f"Sem resposta final após {self._max_iterations} tentativas."
        )

    def _call(self, messages: list[dict[str, Any]]) -> Any:
        try:
            return self._create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=[CALCULATE_TOOL],
                output_config={"effort": self._effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                messages=messages,
            )
        except anthropic.RateLimitError as exc:
            raise SolverError(
                "rate_limited", "Limite de requisições da Anthropic atingido."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise SolverError("upstream_error", "Falha de conexão com a Anthropic.") from exc
        except anthropic.APIStatusError as exc:
            raise SolverError(
                "upstream_error", f"A Anthropic respondeu com erro {exc.status_code}."
            ) from exc

    def _run_tools(self, content: list[Any], steps: list[Step]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if block.type != "tool_use":
                continue
            raw = block.input.get("expression") if isinstance(block.input, dict) else None
            expression = raw if isinstance(raw, str) else ""
            try:
                if block.name != "calculate":
                    raise CalculationError(
                        "invalid_input", f"Ferramenta desconhecida: {block.name}."
                    )
                if not isinstance(raw, str):
                    raise CalculationError("invalid_input", "Informe 'expression' como texto.")
                value = format_decimal(evaluate(raw, self._limits))
            except CalculationError as exc:
                steps.append(Step(expression=expression, error=str(exc)))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": exc.message,
                        "is_error": True,
                    }
                )
            else:
                steps.append(Step(expression=expression, result=value))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": value})
        return results


def _build_result(response: Any, steps: list[Step], usage: Usage) -> SolveResult:
    answer = "\n".join(block.text for block in response.content if block.type == "text")
    result = next((step.result for step in reversed(steps) if step.result is not None), None)
    return SolveResult(
        answer=answer.strip(), result=result, steps=steps, model=response.model, usage=usage
    )


def build_solver(settings: Settings) -> Solver:
    client = anthropic.Anthropic(api_key=settings.require_api_key())
    return Solver(
        client.beta.messages.create,
        model=settings.model,
        effort=settings.effort,
        max_iterations=settings.max_iterations,
        limits=settings.limits(),
    )
```

Ajuste de formatação: se o ruff acusar linhas acima de 100 caracteres, quebre as strings longas dentro de parênteses e rode `uv run ruff format .`.

- [ ] **Step 6: Rodar e ver passar**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: todos os testes passam; ruff e mypy limpos.

- [ ] **Step 7: Verificar que o SDK instalado aceita os parâmetros**

Run:
```bash
uv run python -c "import inspect, anthropic; p = inspect.signature(anthropic.Anthropic(api_key='x').beta.messages.create).parameters; print({k: k in p for k in ('fallbacks', 'output_config', 'betas', 'tools')})"
```

Expected: todos `True`. Se `fallbacks` ou `output_config` vier `False`, o SDK instalado é antigo: rode `uv add anthropic@latest` e repita. Se continuar `False`, mova esses dois parâmetros para `extra_body={"fallbacks": "default", "output_config": {...}}` em `_call` e ajuste `test_request_parameters` para ler de `call["extra_body"]`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/nl_calculator/solver.py tests/fakes.py tests/test_solver.py
git commit -m "feat: add Claude tool-calling solver

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: API FastAPI

**Files:**
- Create: `src/nl_calculator/api.py`
- Modify: `pyproject.toml` (dependências)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Solver`, `SolverError`, `SolveResult`, `build_solver` (Task 4); `Settings`, `ConfigError` (Task 3); `FakeSolver`, `sample_result` (tests/fakes.py)
- Produces: `app: FastAPI`; `get_solver() -> Solver` (dependência com cache, sobrescrevível nos testes); rotas `GET /health` e `POST /calculate`

- [ ] **Step 1: Adicionar as dependências**

```bash
uv add fastapi uvicorn
uv add --dev httpx
```

- [ ] **Step 2: Escrever os testes**

`tests/test_api.py`:
```python
from collections.abc import Iterator

import pytest
from fakes import FakeSolver, sample_result
from fastapi.testclient import TestClient

from nl_calculator.api import app, get_solver
from nl_calculator.solver import SolverError


@pytest.fixture
def fake() -> FakeSolver:
    return FakeSolver(result=sample_result())


@pytest.fixture
def client(fake: FakeSolver) -> Iterator[TestClient]:
    app.dependency_overrides[get_solver] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_calculate(client: TestClient, fake: FakeSolver) -> None:
    response = client.post("/calculate", json={"question": "  15% de 3200 em 6  "})
    assert response.status_code == 200
    assert response.json() == sample_result().model_dump()
    assert fake.questions == ["15% de 3200 em 6"]


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 501}])
def test_invalid_body(client: TestClient, fake: FakeSolver, body: dict[str, str]) -> None:
    assert client.post("/calculate", json=body).status_code == 422
    assert fake.questions == []


def test_whitespace_question_is_rejected(client: TestClient, fake: FakeSolver) -> None:
    assert client.post("/calculate", json={"question": "   "}).status_code == 422
    assert fake.questions == []


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("rate_limited", 429),
        ("upstream_error", 502),
        ("refused", 422),
        ("truncated", 422),
        ("max_iterations", 422),
    ],
)
def test_solver_errors(client: TestClient, fake: FakeSolver, code: str, status: int) -> None:
    fake.error = SolverError(code, "mensagem")
    response = client.post("/calculate", json={"question": "q"})
    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": "mensagem"}}


def test_missing_api_key_returns_503() -> None:
    get_solver.cache_clear()
    response = TestClient(app).post("/calculate", json={"question": "q"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_api.py -q --no-cov`
Expected: FAIL com `ModuleNotFoundError: No module named 'nl_calculator.api'`

- [ ] **Step 4: Implementar**

`src/nl_calculator/api.py`:
```python
"""API HTTP. Rode com: uv run uvicorn nl_calculator.api:app"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from nl_calculator import __version__
from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import SolveResult, Solver, SolverError, build_solver

app = FastAPI(
    title="nl-calculator",
    version=__version__,
    description="Calculadora em linguagem natural: o Claude interpreta, código calcula.",
)

_STATUS_BY_CODE = {"rate_limited": 429, "upstream_error": 502}


@lru_cache(maxsize=1)
def get_solver() -> Solver:
    return build_solver(Settings())


class CalculateRequest(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]


@app.exception_handler(SolverError)
async def handle_solver_error(request: Request, exc: SolverError) -> JSONResponse:
    return JSONResponse(
        status_code=_STATUS_BY_CODE.get(exc.code, 422),
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ConfigError)
async def handle_config_error(request: Request, exc: ConfigError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "not_configured", "message": str(exc)}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/calculate")
def calculate(
    body: CalculateRequest, solver: Annotated[Solver, Depends(get_solver)]
) -> SolveResult:
    return solver.solve(body.question)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: todos os testes passam; ruff e mypy limpos.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/nl_calculator/api.py tests/test_api.py
git commit -m "feat: add FastAPI endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: CLI

**Files:**
- Create: `src/nl_calculator/cli.py`
- Modify: `pyproject.toml` (entry point `calc`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `build_solver`, `SolveResult`, `SolverError`, `Step` (Task 4); `Settings`, `ConfigError` (Task 3); `FakeSolver`, `sample_result` (tests/fakes.py)
- Produces: `main(argv: list[str] | None = None) -> int`; `render(result: SolveResult) -> str`; `run() -> None` (entry point); `_configure_streams() -> None`

- [ ] **Step 1: Registrar o comando**

Em `pyproject.toml`, depois do bloco `[project]`:
```toml
[project.scripts]
calc = "nl_calculator.cli:run"
```

- [ ] **Step 2: Escrever os testes**

`tests/test_cli.py`:
```python
import io
import json
import sys

import pytest
from fakes import FakeSolver, sample_result

from nl_calculator import cli
from nl_calculator.solver import SolveResult, SolverError, Step, Usage


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeSolver:
    solver = FakeSolver(result=sample_result())
    monkeypatch.setattr(cli, "build_solver", lambda settings: solver)
    return solver


def test_text_output(fake: FakeSolver, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["15% de 3200 em 6"]) == 0
    assert capsys.readouterr().out == (
        "15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.\n"
        "\n"
        "Resultado: 80\n"
        "Passos:\n"
        "  3200 * 15 / 100 / 6 = 80\n"
    )
    assert fake.questions == ["15% de 3200 em 6"]


def test_json_output(fake: FakeSolver, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["q", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == sample_result().model_dump()


def test_render_without_result() -> None:
    result = SolveResult(
        answer="Não é um cálculo.", result=None, steps=[], model="m", usage=Usage()
    )
    assert cli.render(result) == "Não é um cálculo."


def test_render_step_error() -> None:
    result = SolveResult(
        answer="Não dá.",
        result=None,
        steps=[Step(expression="1 / 0", error="division_by_zero: Divisão por zero.")],
        model="m",
        usage=Usage(),
    )
    assert cli.render(result) == (
        "Não dá.\n\nPassos:\n  1 / 0 -> erro: division_by_zero: Divisão por zero."
    )


def test_solver_error_exit_1(fake: FakeSolver, capsys: pytest.CaptureFixture[str]) -> None:
    fake.error = SolverError("refused", "O modelo recusou a pergunta.")
    assert cli.main(["q"]) == 1
    assert "refused" in capsys.readouterr().err


def test_missing_key_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["q"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_usage_error_exit_2() -> None:
    with pytest.raises(SystemExit) as info:
        cli.main([])
    assert info.value.code == 2


def test_run_exits_with_main_code(fake: FakeSolver, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["calc", "q"])
    with pytest.raises(SystemExit) as info:
        cli.run()
    assert info.value.code == 0


def test_configure_streams_replaces_unencodable(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    cli._configure_streams()
    stream.write("≈ 3")
    stream.flush()
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_cli.py -q --no-cov`
Expected: FAIL com `ImportError: cannot import name 'cli' from 'nl_calculator'`

- [ ] **Step 4: Implementar**

`src/nl_calculator/cli.py`:
```python
"""Linha de comando: calc "quanto é 15% de 3200?" """

import argparse
import io
import sys

from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import SolveResult, SolverError, build_solver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="calc", description="Calculadora em linguagem natural com Claude."
    )
    parser.add_argument("question", help="pergunta em linguagem natural")
    parser.add_argument("--json", action="store_true", help="imprime o resultado em JSON")
    args = parser.parse_args(argv)

    try:
        solver = build_solver(Settings())
    except ConfigError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 2
    try:
        result = solver.solve(args.question)
    except SolverError as exc:
        print(f"Erro ({exc.code}): {exc.message}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2) if args.json else render(result))
    return 0


def render(result: SolveResult) -> str:
    extra: list[str] = []
    if result.result is not None:
        extra.append(f"Resultado: {result.result}")
    if result.steps:
        extra.append("Passos:")
        for step in result.steps:
            if step.error is None:
                extra.append(f"  {step.expression} = {step.result}")
            else:
                extra.append(f"  {step.expression} -> erro: {step.error}")
    lines = [result.answer]
    if extra:
        lines += ["", *extra]
    return "\n".join(lines)


def run() -> None:
    _configure_streams()
    sys.exit(main())


def _configure_streams() -> None:
    """No Windows, saída redirecionada usa cp1252; troca o que não couber em vez de quebrar."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
Expected: todos os testes passam, cobertura total ≥ 90%; ruff e mypy limpos.

Run: `uv run calc --help`
Expected: ajuda do argparse com `question` e `--json`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/nl_calculator/cli.py tests/test_cli.py
git commit -m "feat: add calc command-line interface

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Avaliação com o modelo real

**Files:**
- Create: `evals/questions.yaml`, `evals/run.py`
- Modify: `pyproject.toml` (dev deps)

**Interfaces:**
- Consumes: `Settings`, `ConfigError` (Task 3); `build_solver`, `SolverError` (Task 4)
- Produces: script manual `uv run python evals/run.py` (código de saída 0 se acertar tudo, 1 se errar alguma, 2 sem chave)

- [ ] **Step 1: Adicionar dependências**

```bash
uv add --dev pyyaml types-PyYAML
```

- [ ] **Step 2: Criar as perguntas**

`evals/questions.yaml`:
```yaml
# expected: resultado esperado (string) ou null quando não deve haver resultado.
# tolerance: diferença máxima aceita (padrão "0").
- question: "Quanto é 15% de 3200?"
  expected: "480"
- question: "15% de 3.200 dividido em 6 parcelas"
  expected: "80"
- question: "Qual a raiz quadrada de 144?"
  expected: "12"
- question: "2 elevado a 10"
  expected: "1024"
- question: "Quanto é 0,1 + 0,2?"
  expected: "0.3"
- question: "Um produto de R$ 250 com 12% de desconto sai por quanto?"
  expected: "220"
- question: "Aumento de 8% sobre um salário de 4.500"
  expected: "4860"
- question: "Quanto é 1/3 de 90?"
  expected: "30"
  tolerance: "1e-20"
- question: "Raiz cúbica de 27"
  expected: "3"
  tolerance: "1e-20"
- question: "What is 7 times 8 minus 6?"
  expected: "50"
- question: "Divida 100 por 8"
  expected: "12.5"
- question: "(3 + 5) ao quadrado menos 4"
  expected: "60"
- question: "Quantos segundos tem um dia?"
  expected: "86400"
- question: "Qual a capital da França?"
  expected: null
- question: "Quanto é 10 dividido por zero?"
  expected: null
```

- [ ] **Step 3: Criar o script**

`evals/run.py`:
```python
"""Avaliação com o modelo real. Gasta créditos da API: rode manualmente.

Uso: uv run python evals/run.py
"""

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import SolverError, build_solver

QUESTIONS = Path(__file__).with_name("questions.yaml")
# Preço em US$ por milhão de tokens (entrada, saída).
PRICES_PER_MTOK = {"claude-opus-5-5": (Decimal("4"), Decimal("20"))}


def is_correct(result: str | None, expected: str | None, tolerance: str) -> bool:
    if expected is None or result is None:
        return result is expected
    try:
        return abs(Decimal(result) - Decimal(expected)) <= Decimal(tolerance)
    except InvalidOperation:
        return False


def main() -> int:
    settings = Settings()
    try:
        solver = build_solver(settings)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    cases = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    correct = input_tokens = output_tokens = 0
    for case in cases:
        expected = case.get("expected")
        try:
            result = solver.solve(case["question"])
        except SolverError as exc:
            ok, got = False, f"erro {exc.code}"
        else:
            ok = is_correct(result.result, expected, case.get("tolerance", "0"))
            got = result.result
            input_tokens += result.usage.input_tokens
            output_tokens += result.usage.output_tokens
        correct += ok
        print(f"{'OK  ' if ok else 'FAIL'} | esperado={expected} obtido={got} | {case['question']}")

    total = len(cases)
    print(f"\nAcertos: {correct}/{total} ({correct / total:.0%})")
    print(f"Tokens: {input_tokens} de entrada, {output_tokens} de saída")
    prices = PRICES_PER_MTOK.get(settings.model)
    if prices:
        cost = (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
        print(f"Custo estimado: US$ {cost:.4f}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verificar estilo e sintaxe (sem chamar a API)**

Run: `uv run ruff check . && uv run ruff format --check . && uv run python -c "import ast, pathlib; ast.parse(pathlib.Path('evals/run.py').read_text(encoding='utf-8'))"`
Expected: sem erros.

Run (sem chave definida): `uv run python evals/run.py`
Expected: mensagem sobre `ANTHROPIC_API_KEY` e código de saída 2.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock evals/
git commit -m "feat: add live-model evaluation script

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Rodar a avaliação de verdade (precisa de aprovação do usuário)**

Pergunte ao usuário se ele tem uma `ANTHROPIC_API_KEY` no `.env` e se autoriza gastar alguns centavos. Só com o "sim" dele:

Run: `uv run python evals/run.py`
Expected: tabela OK/FAIL, taxa de acerto, tokens e custo. Guarde a saída para o README (Task 8). Se alguma pergunta falhar, mostre ao usuário antes de mexer no prompt.

---

### Task 8: CI e README

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: todos os comandos de verificação; saída da Task 7 Step 6 (se houver)
- Produces: CI no GitHub Actions; README final

- [ ] **Step 1: Criar o workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src
      - run: uv run pytest
```

- [ ] **Step 2: Escrever o README completo**

`README.md`:
````markdown
# nl-calculator

[![CI](https://github.com/JooaBaarbosa/nl-calculator/actions/workflows/ci.yml/badge.svg)](https://github.com/JooaBaarbosa/nl-calculator/actions/workflows/ci.yml)

**Calculadora em linguagem natural: o Claude interpreta, código determinístico calcula.**

```
$ calc "quanto é 15% de 3.200 dividido em 6 parcelas?"
15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.

Resultado: 80
Passos:
  3200 * 15 / 100 / 6 = 80
```

## Como funciona

```
pergunta ──► CLI / API ──► solver ◄──► Claude (ferramenta: calculate)
                              │
                              ▼
                         evaluator ──► Decimal exato
```

1. O **solver** envia a pergunta ao Claude com uma única ferramenta, `calculate(expression)`.
2. O Claude traduz a pergunta para uma expressão (`3200 * 15 / 100 / 6`) e chama a ferramenta.
3. O **evaluator** calcula a expressão e devolve o resultado. Se a expressão for inválida,
   o erro volta para o Claude, que corrige e tenta de novo.
4. A resposta traz o resultado, cada expressão usada e uma explicação curta.

## Por que o LLM não faz a conta

LLMs erram aritmética. Aqui o modelo só **interpreta**; o número final vem sempre do código.
O campo `result` é o valor da última chamada bem-sucedida da ferramenta, nunca um número
extraído do texto do modelo.

A expressão gerada pelo modelo é tratada como **entrada não confiável**:

- **Sem `eval`.** O texto vira uma árvore com `ast.parse` (que não executa nada) e só uma
  lista fechada de nós é aceita: números, `+ - * / **`, sinal, parênteses e `sqrt()`.
  Qualquer outra coisa (`__import__`, variáveis, atributos, outras funções) é recusada.
- **Precisão exata.** Os números viram `Decimal`: `0.1 + 0.2` dá `0.3`.
- **Limites.** Tamanho da expressão, número de nós e expoente (±1000) são limitados;
  `9 ** 9 ** 9` vira erro em vez de travar o servidor.

## Rodando

Requisitos: [uv](https://docs.astral.sh/uv/) e uma chave da API da Anthropic.

```bash
git clone https://github.com/JooaBaarbosa/nl-calculator.git
cd nl-calculator
uv sync
cp .env.example .env   # preencha ANTHROPIC_API_KEY
```

**CLI**

```bash
uv run calc "raiz quadrada de 144 mais 10% de 50"
uv run calc "2 elevado a 10" --json
```

**API**

```bash
uv run uvicorn nl_calculator.api:app
curl -X POST http://127.0.0.1:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{"question": "quanto é 15% de 3200?"}'
```

Documentação interativa em `http://127.0.0.1:8000/docs`.

| Situação | HTTP |
|---|---|
| Sucesso | 200 |
| Pergunta inválida, recusa do modelo, resposta cortada, tentativas esgotadas | 422 |
| Limite de requisições da Anthropic | 429 |
| Falha da Anthropic | 502 |
| Chave não configurada | 503 |

## Decisões técnicas

| Decisão | Por quê |
|---|---|
| Uma ferramenta que avalia expressões | Poucas chamadas ao modelo; o avaliador é testável sem LLM |
| Loop de tool calling escrito à mão | Deixa o protocolo explícito; sem depender de helper em beta |
| `Decimal` em vez de `float` | Resultado exato para dinheiro e porcentagem |
| Cliente da Anthropic injetado no solver | Todos os testes rodam sem rede e sem chave |
| `fallbacks: "default"` | Se o modelo recusar, a API tenta outro modelo automaticamente |
| Modelo e esforço configuráveis | `NLCALC_MODEL` e `NLCALC_EFFORT` sem mudar código |

## Qualidade

- `pytest` com cobertura mínima de 90% (o avaliador tem 100%)
- `mypy --strict` e `ruff`
- CI no GitHub Actions a cada push e pull request

## Avaliação com o modelo real

`evals/questions.yaml` tem 15 perguntas com resposta conhecida, incluindo números no formato
brasileiro, porcentagens, raízes, uma pergunta que não é cálculo e uma divisão por zero.

```bash
uv run python evals/run.py   # usa a API de verdade (custa centavos)
```

## Licença

MIT
````

Se a Task 7 Step 6 foi executada, acrescente ao fim da seção "Avaliação com o modelo real" um bloco com a data e as três linhas finais da saída (`Acertos`, `Tokens`, `Custo estimado`) exatamente como apareceram. Se não foi, deixe a seção como está.

- [ ] **Step 3: Verificação final completa**

Run: `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
Expected: tudo verde, cobertura ≥ 90%.

Run: `git status --short`
Expected: nenhum `.env` listado.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "docs: add README and CI workflow

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Publicar no GitHub (precisa de confirmação do usuário)**

Mostre o `git log --oneline` ao usuário e pergunte se pode criar o repositório público `JooaBaarbosa/nl-calculator`. Só com o "sim" dele:

```bash
"/c/Program Files/GitHub CLI/gh.exe" repo create JooaBaarbosa/nl-calculator --public --source . --remote origin --push --description "Calculadora em linguagem natural: o Claude interpreta, código determinístico calcula."
"/c/Program Files/GitHub CLI/gh.exe" run list --limit 1
```

Expected: repositório criado, push feito, uma execução de CI listada. Acompanhe até terminar (`gh run watch`) e informe o resultado ao usuário.
