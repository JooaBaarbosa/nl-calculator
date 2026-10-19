import io
import json
import sys

import pytest
from fakes import FakeSolver, sample_result

from nl_calculator import cli
from nl_calculator.solver import SolverError, SolveResult, Step, Usage


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
