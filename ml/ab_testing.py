"""A/B testing framework for model comparison. Traffic splitting + significance."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import Any

from core.logger import get_logger

log = get_logger("ml.ab_testing")


class ABTest:
    """Manages A/B testing between champion (A) and challenger (B) models.

    Usage:
        test = ABTest(vehicle_id, champion_id, challenger_id, traffic_pct=20)
        model_id = test.select_model(user_id)  # deterministically picks A or B
        test.record_result(model_id, failure_prob, actual_outcome)
    """

    def __init__(
        self,
        vehicle_id: int,
        champion_id: int,
        challenger_id: int,
        traffic_pct: int = 20,
        min_samples: int = 500,
    ):
        self.vehicle_id = vehicle_id
        self.champion_id = champion_id
        self.challenger_id = challenger_id
        self.traffic_pct = max(1, min(50, traffic_pct))  # cap challenger at 50%
        self.min_samples = min_samples
        self.results: dict[str, list[dict]] = {"champion": [], "challenger": []}

    def select_model(self, user_id: int) -> int:
        """Deterministically select champion or challenger based on user_id hash."""
        bucket = (
            int(
                hashlib.md5(f"{user_id}:{self.vehicle_id}".encode()).hexdigest()[:8], 16
            )
            % 100
        )
        if bucket < self.traffic_pct:
            return self.challenger_id  # B
        return self.champion_id  # A

    def record_result(
        self, model_id: int, failure_prob: float, actual_failure: bool | None = None
    ):
        """Record a prediction result for analysis."""
        arm = "challenger" if model_id == self.challenger_id else "champion"
        self.results[arm].append(
            {
                "failure_prob": failure_prob,
                "actual_failure": actual_failure,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def get_significance(self) -> dict[str, Any]:
        """Calculate statistical significance using z-test for proportions."""
        champ = self.results["champion"]
        chal = self.results["challenger"]
        if len(champ) < 30 or len(chal) < 30:
            return {"significant": False, "reason": "Insufficient samples"}

        def error_rate(rows):
            if not rows:
                return 0.0
            errors = sum(1 for r in rows if r["actual_failure"] is True)
            return errors / len(rows)

        p1, n1 = error_rate(champ), len(champ)
        p2, n2 = error_rate(chal), len(chal)

        p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return {"significant": False, "reason": "Zero variance"}

        z = (p2 - p1) / se
        # Approximate p-value from z-score (two-tailed)
        p_value = 2 * (1 - _normal_cdf(abs(z)))

        return {
            "significant": p_value < 0.05,
            "champion_error_rate": round(p1, 4),
            "challenger_error_rate": round(p2, 4),
            "improvement": round((p1 - p2) / (p1 or 0.001) * 100, 1),
            "champion_samples": n1,
            "challenger_samples": n2,
            "z_score": round(z, 3),
            "p_value": round(p_value, 4),
            "confidence": "95%"
            if p_value < 0.05
            else "90%"
            if p_value < 0.1
            else "insufficient",
        }


def _normal_cdf(x: float) -> float:
    """Standard normal CDF approximation (Abramowitz & Stegun)."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


class ABTestManager:
    """Manages multiple A/B tests across vehicles."""

    def __init__(self):
        self._tests: dict[str, ABTest] = {}

    def get_or_create(
        self,
        vehicle_id: int,
        champion_id: int,
        challenger_id: int,
        traffic_pct: int = 20,
    ) -> ABTest:
        key = f"{vehicle_id}:{champion_id}:{challenger_id}"
        if key not in self._tests:
            self._tests[key] = ABTest(
                vehicle_id, champion_id, challenger_id, traffic_pct
            )
        return self._tests[key]

    def get_test(self, vehicle_id: int) -> ABTest | None:
        for _key, test in self._tests.items():
            if test.vehicle_id == vehicle_id:
                return test
        return None


ab_manager = ABTestManager()
