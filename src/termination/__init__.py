"""A behavioural termination model for §489 BGB exercise.

The specification lives in ``docs/TERMINATION_MODEL.md`` and this package
implements it. Standard library only, matching the repository's dependency
rule.

The order here is deliberate. The empirical exercise curve in
:mod:`termination.curve` needs no model at all — it is a ratio of counts to
exposure — so it comes first and can contradict the parametric fit that
follows. A model that disagrees with the raw counts is wrong about the data,
not insightful about it.
"""

from termination.model import Contract, ExitCause, FlatCurve, TermCurve
from termination.panel import Cell, Panel, build_panel
from termination.curve import ExerciseCurve, empirical_exercise_curve, survival

__all__ = [
    "Contract",
    "ExitCause",
    "FlatCurve",
    "TermCurve",
    "Cell",
    "Panel",
    "build_panel",
    "ExerciseCurve",
    "empirical_exercise_curve",
    "survival",
]
__version__ = "0.1.0"
