"""
Map an anomaly score magnitude to a severity bucket.

Both detectors in this package produce scores that are, at heart, "how many
robust standard deviations away from expected" a point is (a z-score for
stl_zscore, a studentized-residual-like statistic for s_h_esd). That lets us
share one severity mapping keyed on |score|, configurable via env vars so
thresholds can be tuned without touching code.
"""

from __future__ import annotations

import os

# Defaults chosen so that: the STL detector's own flagging threshold
# (STL_ZSCORE_THRESHOLD, default 3.5) lines up with the low/medium boundary
# here -- i.e. anything that clears the bar to be flagged at all starts out
# "medium" unless it's mild, and only clearly extreme points reach "high".
SEVERITY_LOW_MAX = float(os.environ.get("SEVERITY_LOW_MAX", 4.0))
SEVERITY_MEDIUM_MAX = float(os.environ.get("SEVERITY_MEDIUM_MAX", 6.0))


def severity_from_score(score: float) -> str:
    """
    score: an anomaly score, typically a (robust) z-score or ESD test
    statistic. Sign doesn't matter -- magnitude drives severity.
    """
    magnitude = abs(score)
    if magnitude < SEVERITY_LOW_MAX:
        return "low"
    if magnitude < SEVERITY_MEDIUM_MAX:
        return "medium"
    return "high"
