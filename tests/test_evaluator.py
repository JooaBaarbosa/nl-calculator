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


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0.3333333333333333333333333333 * 3", "0.9999999999999999999999999999"),
        ("1.0000000000000000000001 - 1", "1E-22"),
        ("0.12345678901234567890123 * 1", "0.12345678901234567890123"),
        ("1e309 / 1e308", "10"),
        ("1_000.5 + 0", "1000.5"),
        ("sqrt(1e-998)", "1E-499"),
    ],
)
def test_decimal_literals_keep_full_precision(expression: str, expected: str) -> None:
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
        ("1e1000000", "too_large"),
        ("1e999999 * 10", "too_large"),
        ("__import__('os')", "forbidden_element"),
        ("x + 1", "forbidden_element"),
        ("2 % 3", "forbidden_element"),
        ("2 % (1 / 0)", "forbidden_element"),
        ("2 ^ 3", "forbidden_element"),
        ("7 // 2", "forbidden_element"),
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
