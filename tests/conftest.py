import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Nenhum teste lê a chave real nem o .env do projeto."""
    for name in list(os.environ):
        if name == "ANTHROPIC_API_KEY" or name.startswith("NLCALC_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
