import calendar
from datetime import date, timedelta

from dateutil.easter import easter


def _next_monday(day):
    return day + timedelta(days=(7 - day.weekday()) % 7)


def _nth_weekday(year, month, weekday, n):
    """n-ésimo día de la semana (0=lunes) del mes."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year, month, weekday):
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def holidays_colombia(year):
    """Festivos nacionales suficientes para variables de calendario.

    No sustituye un calendario legal. Se usa como característica estadística.
    """
    fixed = {
        date(year, 1, 1), date(year, 5, 1), date(year, 7, 20),
        date(year, 8, 7), date(year, 12, 8), date(year, 12, 25),
    }
    monday_law = [
        date(year, 1, 6), date(year, 3, 19), date(year, 6, 29),
        date(year, 8, 15), date(year, 10, 12), date(year, 11, 1),
        date(year, 11, 11),
    ]
    holy_sunday = easter(year)
    relative = {
        holy_sunday - timedelta(days=3),
        holy_sunday - timedelta(days=2),
        _next_monday(holy_sunday + timedelta(days=39)),
        _next_monday(holy_sunday + timedelta(days=60)),
        _next_monday(holy_sunday + timedelta(days=68)),
    }
    return fixed | {_next_monday(day) for day in monday_law} | relative


def commercial_dates(year):
    """Fechas comerciales que mueven la venta de moda en Colombia."""
    return {
        "dia_madre": _nth_weekday(year, 5, 6, 2),          # 2.º domingo de mayo
        "dia_padre": _nth_weekday(year, 6, 6, 3),          # 3.er domingo de junio
        "amor_amistad": _nth_weekday(year, 9, 5, 3),       # 3.er sábado de septiembre
        "black_friday": _nth_weekday(year, 11, 3, 4),      # 4.º jueves + 1 día
    }


def month_calendar_features(year, month):
    days = calendar.monthrange(year, month)[1]
    dates = [date(year, month, day) for day in range(1, days + 1)]
    holidays = holidays_colombia(year)
    events = commercial_dates(year)
    black_friday = events["black_friday"] + timedelta(days=1)
    holy_sunday = easter(year)
    # Domingo de Ramos al Sábado Santo.
    holy_week = {holy_sunday - timedelta(days=offset) for offset in range(1, 8)}
    # Quincenas (15 y último día) que caen en viernes, sábado o domingo:
    # el pago coincide con fin de semana y suele concentrar la compra.
    paydays = [date(year, month, 15), dates[-1]]
    return {
        "days_in_month": days,
        "weekend_days": sum(day.weekday() >= 5 for day in dates),
        "fridays": sum(day.weekday() == 4 for day in dates),
        "saturdays": sum(day.weekday() == 5 for day in dates),
        "sundays": sum(day.weekday() == 6 for day in dates),
        "holiday_count": sum(day in holidays for day in dates),
        "long_weekends": sum(day in holidays and day.weekday() == 0 for day in dates),
        "holy_week_days": sum(day in holy_week for day in dates),
        "payday_weekend": sum(day.weekday() >= 4 for day in paydays),
        "payday_count": 2,
        "evento_dia_madre": int(events["dia_madre"].month == month),
        "evento_dia_padre": int(events["dia_padre"].month == month),
        "evento_amor_amistad": int(events["amor_amistad"].month == month),
        "evento_black_friday": int(black_friday.month == month),
        "evento_navidad": int(month == 12),
        "evento_prima": int(month in (6, 12)),
        "evento_temporada_escolar": int(month in (1, 2)),
        # Días entre el último sábado del mes y el cierre: un mes que termina
        # en fin de semana suele cerrar más fuerte.
        "dias_desde_ultimo_sabado": (dates[-1] - _last_weekday(year, month, 5)).days,
    }


CALENDAR_COLUMNS = tuple(month_calendar_features(2026, 1).keys())
