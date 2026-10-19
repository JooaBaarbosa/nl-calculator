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
