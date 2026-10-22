"""API HTTP. Rode com: uv run uvicorn nl_calculator.api:app"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from nl_calculator import __version__
from nl_calculator.config import ConfigError, Settings
from nl_calculator.solver import Solver, SolverError, SolveResult, build_solver

app = FastAPI(
    title="nl-calculator",
    version=__version__,
    description="Calculadora em linguagem natural: o Claude interpreta, código calcula.",
)

_STATUS_BY_CODE = {"rate_limited": 429, "upstream_error": 502}


@lru_cache(maxsize=1)
def get_solver() -> Solver:
    return build_solver(Settings())


class CalculateRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


@app.exception_handler(SolverError)
async def handle_solver_error(request: Request, exc: SolverError) -> JSONResponse:
    return JSONResponse(
        status_code=_STATUS_BY_CODE.get(exc.code, 422),
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ConfigError)
async def handle_config_error(request: Request, exc: ConfigError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "not_configured", "message": str(exc)}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/calculate")
def calculate(
    body: CalculateRequest, solver: Annotated[Solver, Depends(get_solver)]
) -> SolveResult:
    return solver.solve(body.question)


STATIC_DIR = Path(__file__).parent / "static"

_NOT_BUILT_PAGE = """<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><title>nl-calculator</title>
<p>Interface não compilada: rode <code>npm run build</code> em <code>web/</code>,
ou use <code>docker compose up --build</code>.</p>
<p>A API continua disponível em <a href="/docs">/docs</a>.</p>
</html>"""


def mount_static(app: FastAPI, directory: Path) -> None:
    """Serve a página compilada em /. Deve ser chamada depois de todas as rotas da API."""
    if (directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=directory, html=True), name="static")
        return

    @app.get("/", include_in_schema=False)
    def not_built() -> HTMLResponse:
        return HTMLResponse(_NOT_BUILT_PAGE)


mount_static(app, STATIC_DIR)
