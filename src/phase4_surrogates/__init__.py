"""Surrogate models and solver abstractions for PHyAI-Universal."""

from .solvers.solver import CandidateSolution, SolverRequest, SurrogateSolver
from .compilers.compiler import CompiledSurrogate, SurrogateCompiler

__all__ = [
    "CandidateSolution",
    "CompiledSurrogate",
    "SolverRequest",
    "SurrogateCompiler",
    "SurrogateSolver",
]
