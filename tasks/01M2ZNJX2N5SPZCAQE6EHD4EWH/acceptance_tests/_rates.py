"""Общие фикстуры и разбор строк журнала для планки задачи (не тест).

Здесь только то, что нужно БОЛЬШЕ ЧЕМ ОДНОМУ файлу планки: разбивка
usage одного шага, факт CLI, отстоящий от расчёта по курсу на заданную
долю порога, чтение дописанных `charge_step` величин из строки «agent
cost KNOWN», состаривание уже записанных строк журнала до даты
калибровки курса и выборка открытых алертов расхождения.

Все предпосылки о конфигурации берутся ДИНАМИЧЕСКИ: курс роли и дата
его калибровки — из `config.TOKEN_RATES`, порог алерта — из
`config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`. Оператор вправе
повернуть обе крутилки (ADR-0002, класс «лимит»), и планка обязана
пережить поворот: зашитый литерал порога/цены сломал бы залоченный тест
на ровном месте (урок 28.08, T062).
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, config, spend, store  # noqa: E402

# Роль-носитель курса для фикстур: любая из четырёх agent-ролей
# конвейера подошла бы, `developer` — та, на чьём таймауте 01M2DC6S
# расхождение курса и обнаружилось (SPEC, «Контекст»).
ROLE = "developer"
KNOWN_ACTION = "agent cost KNOWN"
PARTIAL_ACTION = "agent cost PARTIAL"

# Разбивка usage одного шага по видам (`config.USAGE_TOKEN_KEYS`):
# пропорции характерного шага — почти весь объём в чтениях кэша, малая
# доля входа/выхода. Числа крупные, чтобы расчёт по курсу измерялся
# долларами, а не шестым знаком после запятой: округление до центов в
# строке журнала не должно съедать проверяемую величину.
TOKENS = {"input_tokens": 40_000,
          "output_tokens": 20_000,
          "cache_creation_input_tokens": 60_000,
          "cache_read_input_tokens": 2_000_000}


def threshold() -> float:
    """Порог алерта расхождения — крутилка Оператора, не литерал."""
    return config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD


def rate_date(role: str = ROLE) -> str:
    """`calibrated_at` курса роли — дата, с которой идёт сверка (AC-4/AC-5)."""
    return config.TOKEN_RATES[role]["calibrated_at"]


def calculated_usd(role: str = ROLE, tokens: dict | None = None) -> float:
    """Расчёт по курсу роли для разбивки `tokens` — той же функцией
    (`spend.partial_cost_usd`), которой его считает сама реализация: тест
    сверяет ЗАПИСЬ расчёта в журнал, а не переписывает формулу курса."""
    return spend.partial_cost_usd(role, TOKENS if tokens is None else tokens)


def actual_usd_for_coefficient(coefficient: float, role: str = ROLE,
                               tokens: dict | None = None) -> float:
    """Факт CLI, дающий ровно заданный коэффициент расхождения.

    Коэффициент — |расчёт − факт| / факт (та же математика, что уже
    считает `report.token_rate_divergence`), поэтому факт = расчёт /
    (1 + коэффициент): расчёт выше факта на заданную долю.
    """
    return calculated_usd(role, tokens) / (1.0 + coefficient)


def cost(actual: float, tokens: dict | None = None) -> dict:
    """Событие стоимости шага в том виде, в каком его отдаёт
    `spend.parse_cost_event`: факт CLI (`total_cost_usd`) плюс разбивка
    usage по видам."""
    by_type = TOKENS if tokens is None else tokens
    return {"usd": actual,
            "tokens": sum(by_type.values()) if by_type else None,
            "tokens_by_type": by_type}


def journal(conn, task_id: str) -> list:
    """Журнал задачи как (актор, действие, деталь) в порядке записи."""
    return [(r["actor"], r["action"], r["detail"])
            for r in store.task_steps(conn, task_id)]


def details(conn, task_id: str, action: str, role: str = ROLE) -> list:
    """Детали записей журнала этого действия и этой роли."""
    return [detail for actor, act, detail in journal(conn, task_id)
            if act == action and actor == role]


def coefficient_in(detail: str, role: str = ROLE):
    """Коэффициент из «коэффициент роли с <дата>=…» строки журнала;
    `None` — строка его не несёт. Дата в образце — из курса роли, не
    литерал (AC-4 называет её именно так)."""
    found = re.search(
        re.escape(f"коэффициент роли с {rate_date(role)}=") + r"([0-9]+(?:\.[0-9]+)?)",
        detail)
    return float(found.group(1)) if found else None


def calculated_in(detail: str):
    """Расчёт по курсу из «расчёт по курсу=$…» строки журнала; `None` —
    строка его не несёт."""
    found = re.search(r"расчёт по курсу=\$([0-9]+(?:\.[0-9]+)?)", detail)
    return float(found.group(1)) if found else None


def backdate_known_rows(conn, role: str = ROLE) -> None:
    """Сдвигает УЖЕ записанные строки KNOWN на день раньше даты
    калибровки курса роли — «шаги другой модели» из AC-5. Формат `ts` —
    тот же, что пишет `store.now()`."""
    day = date.fromisoformat(rate_date(role)) - timedelta(days=1)
    conn.execute("UPDATE steps SET ts=? WHERE action=?",
                 (f"{day} 12:00:00Z", KNOWN_ACTION))
    conn.commit()


def divergence_alerts(conn) -> list:
    """Открытые алерты расхождения курса (`alerts.
    raise_token_rate_divergence_alert`): `kind=warning`, свой `source`,
    `target=None` — расхождение по роли поперёк всех задач."""
    return [row for row in alerts.open_alerts(conn, "warning")
            if row["source"] == alerts.TOKEN_RATE_DIVERGENCE_SOURCE]


def numbers_in(value) -> list:
    """Все числа значения любой формы — само число, значения словаря,
    элементы списка/кортежа.

    Форму возврата `report.token_rate_divergence` эта задача меняет
    (AC-8: строка отчёта называет дату и число шагов), и планка не
    вправе её диктовать: тест спрашивает «есть ли среди чисел роли тот
    самый коэффициент», а не «лежит ли он в поле с угаданным именем».
    """
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for item in value.values() for n in numbers_in(item)]
    if isinstance(value, (list, tuple)):
        return [n for item in value for n in numbers_in(item)]
    return []
