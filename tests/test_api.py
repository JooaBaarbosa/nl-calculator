from collections.abc import Iterator

import pytest
from fakes import FakeSolver, sample_result
from fastapi.testclient import TestClient

from nl_calculator.api import app, get_solver
from nl_calculator.solver import SolverError


@pytest.fixture
def fake() -> FakeSolver:
    return FakeSolver(result=sample_result())


@pytest.fixture
def client(fake: FakeSolver) -> Iterator[TestClient]:
    app.dependency_overrides[get_solver] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_calculate(client: TestClient, fake: FakeSolver) -> None:
    response = client.post("/calculate", json={"question": "  15% de 3200 em 6  "})
    assert response.status_code == 200
    assert response.json() == sample_result().model_dump()
    assert fake.questions == ["15% de 3200 em 6"]


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 501}])
def test_invalid_body(client: TestClient, fake: FakeSolver, body: dict[str, str]) -> None:
    assert client.post("/calculate", json=body).status_code == 422
    assert fake.questions == []


def test_whitespace_question_is_rejected(client: TestClient, fake: FakeSolver) -> None:
    assert client.post("/calculate", json={"question": "   "}).status_code == 422
    assert fake.questions == []


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("rate_limited", 429),
        ("upstream_error", 502),
        ("refused", 422),
        ("truncated", 422),
        ("max_iterations", 422),
    ],
)
def test_solver_errors(client: TestClient, fake: FakeSolver, code: str, status: int) -> None:
    fake.error = SolverError(code, "mensagem")
    response = client.post("/calculate", json={"question": "q"})
    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": "mensagem"}}


def test_missing_api_key_returns_503() -> None:
    get_solver.cache_clear()
    response = TestClient(app).post("/calculate", json={"question": "q"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"
