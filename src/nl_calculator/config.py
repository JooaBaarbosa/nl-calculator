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
