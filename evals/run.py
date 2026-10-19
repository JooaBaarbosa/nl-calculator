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
