from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes import FakeSolver, sample_result
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nl_calculator.api import app, get_solver, mount_static
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


def test_mount_static_serves_index_without_shadowing_routes(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    fresh = FastAPI()

    @fresh.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @fresh.post("/calculate")
    def calculate() -> dict[str, str]:
        return {"result": "80"}

    mount_static(fresh, tmp_path)
    client = TestClient(fresh)
    page = client.get("/")
    assert page.status_code == 200
    assert '<div id="root">' in page.text
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/calculate").json() == {"result": "80"}
    assert client.get("/openapi.json").status_code == 200


def test_static_entry_is_registered_after_every_api_route() -> None:
    # Uma rota registrada depois da página em "/" ficaria escondida por ela.
    paths = [getattr(route, "path", "") for route in app.routes]
    last = app.routes[-1]
    assert getattr(last, "name", "") in {"static", "not_built"}
    for api_path in ("/calculate", "/health", "/docs", "/openapi.json"):
        assert paths.index(api_path) < len(paths) - 1


def test_mount_static_without_build_explains(tmp_path: Path) -> None:
    fresh = FastAPI()
    mount_static(fresh, tmp_path / "missing")
    response = TestClient(fresh).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "npm run build" in response.text
    assert "docker compose up --build" in response.text


def test_api_routes_survive_static_mount(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
