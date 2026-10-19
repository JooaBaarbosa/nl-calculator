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
