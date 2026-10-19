"""API HTTP. Rode com: uv run uvicorn nl_calculator.api:app"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
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
