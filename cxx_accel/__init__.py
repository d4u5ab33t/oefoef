"""
cxx_accel — OIDASHEIM C++ Native Acceleration Package
"""

from .bridge import (
    CxxAccelerationEngine,
    get_cxx_engine,
    CxxClipCandidate,
    CxxScoringContext,
    CxxMatchResult,
    CxxTimelineSegmentInput,
    CxxTimelineClassificationOutput,
    CxxTimelineRewardOutput,
)

__all__ = [
    "CxxAccelerationEngine",
    "get_cxx_engine",
    "CxxClipCandidate",
    "CxxScoringContext",
    "CxxMatchResult",
    "CxxTimelineSegmentInput",
    "CxxTimelineClassificationOutput",
    "CxxTimelineRewardOutput",
]

