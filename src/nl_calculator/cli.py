"""Linha de comando: calc "quanto é 15% de 3200?" """

import argparse
import io
import sys

from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import SolverError, SolveResult, build_solver


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
