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
