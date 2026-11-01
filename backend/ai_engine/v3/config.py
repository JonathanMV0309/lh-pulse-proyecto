import os
from dataclasses import dataclass
from datetime import date


def _previous_month(today=None):
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def _period_from_env():
    raw = (os.getenv("AI_DATA_CUTOFF") or "").strip()
    if raw:
        if len(raw) != 6 or not raw.isdigit():
            raise ValueError("AI_DATA_CUTOFF debe tener formato AAAAMM")
        year, month = int(raw[:4]), int(raw[4:])
        if month < 1 or month > 12:
            raise ValueError("Mes inválido en AI_DATA_CUTOFF")
        return year, month
    return _previous_month()


@dataclass(frozen=True)
class ForecastConfig:
    cutoff_year: int
    cutoff_month: int
    validation_months: int = 6
    min_history_months: int = 12
    min_coverage: float = 0.95
    total_ratio_min: float = 0.70
    total_ratio_max: float = 1.35
    max_interval_ratio: float = 0.55
    lines: tuple = (1, 2, 3, 4)

    @classmethod
    def from_environment(cls):
        year, month = _period_from_env()
        return cls(
            cutoff_year=year,
            cutoff_month=month,
            validation_months=int(os.getenv("AI_V3_VALIDATION_MONTHS", "6")),
            min_coverage=float(os.getenv("AI_V3_MIN_COVERAGE", "0.95")),
        )

    @property
    def cutoff_period(self):
        return self.cutoff_year * 100 + self.cutoff_month

    @property
    def forecast_period(self):
        if self.cutoff_month == 12:
            return self.cutoff_year + 1, 1
        return self.cutoff_year, self.cutoff_month + 1

