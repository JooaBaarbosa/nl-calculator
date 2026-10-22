from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fakes import FakeCreate, response, text, tool_use

from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import Solver, SolverError, build_solver

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


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
                "rate", response=httpx2.Response(429, request=REQUEST), body=None
            ),
            "rate_limited",
        ),
        (anthropic.APIConnectionError(request=REQUEST), "upstream_error"),
        (
            anthropic.InternalServerError(
                "boom", response=httpx2.Response(500, request=REQUEST), body=None
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


def test_system_prompt_asks_for_plain_text() -> None:
    # A página e o terminal mostram a resposta como texto: Markdown apareceria cru (**80**).
    fake = FakeCreate(response(text("ok")))
    make_solver(fake).solve("q")
    assert "Markdown" in fake.calls[0]["system"]
    assert "texto puro" in fake.calls[0]["system"]
