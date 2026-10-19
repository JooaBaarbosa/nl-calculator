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
