"""Классификация провалившейся попытки агента (SPEC T082, требования 1-2).
Перенесено из orchestrator/runner.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner).
"""
from pathlib import Path

from . import alerts, config, store

# Эвристики ошибок агента (SPEC T082, требования 1-2): классификация по
# подстроке в объединённом stdout+stderr провалившейся попытки, без учёта
# регистра. Сигнатуры 1а/1б/«обрыв потока» — дословные, снятые Оператором
# с логов инцидентов T043 (27.08) и T075-T078 (31.08); список класса 2
# (session limit подписки) — версия 1, предположительная, без живого
# инцидента (tasks/T082/ANSWER-1.md). Специфичные списки проверяются
# раньше общего якоря «API Error:» (класс 1, «системный кандидат») —
# иначе он перехватывал бы и их (требование 1, «страховка от промаха»).
CLASS_1A_SIGNATURES = ("403", "failed to authenticate")
CLASS_1B_SIGNATURES = ("connection refused", "connectionrefused")
STREAM_BROKEN_SIGNATURE = "connection lost mid-response"
SESSION_LIMIT_SIGNATURES = ("session limit", "usage limit", "5-hour limit",
                            "resets at")
SYSTEM_CANDIDATE_ANCHOR = "api error:"

# Связка «транзиентное системное» (требование 3): auth/403, сетевой отказ
# до API, «системный кандидат» — минутный бэкофф вместо секундного,
# число попыток шага не меняется (инвариант 3). «Обрыв потока» в связку
# НЕ входит — требование 3 её не называет, у неё свой путь (требование 5).
TRANSIENT_SYSTEM_CLASSES = ("1a", "1b", "system_candidate")

CLASS_LABELS = {
    "1a": "класс 1а (auth/403)",
    "1b": "класс 1б (сетевой отказ до API)",
    "stream_broken": "обрыв потока",
    "system_candidate": "класс 1, системный кандидат",
    "session_limit": "класс 2 (session limit подписки)",
}


def classify_attempt_failure(text: str) -> str | None:
    """Класс отказа попытки по её тексту; `None` — нераспознанный (SPEC
    T082, требования 1-2, критерии AC-1..AC-6).
    """
    lowered = text.lower()
    if any(sig in lowered for sig in CLASS_1A_SIGNATURES):
        return "1a"
    if any(sig in lowered for sig in CLASS_1B_SIGNATURES):
        return "1b"
    if STREAM_BROKEN_SIGNATURE in lowered:
        return "stream_broken"
    if any(sig in lowered for sig in SESSION_LIMIT_SIGNATURES):
        return "session_limit"
    if SYSTEM_CANDIDATE_ANCHOR in lowered:
        return "system_candidate"
    return None


def _attempt_output_text(log_path: Path) -> str:
    """Полный текст лога ЭТОЙ попытки — `agent_log.new_agent_log` заводит
    файл заново на каждый вызов `run_agent_once`, поэтому чтение целиком
    (не хвоста) не подмешивает соседние попытки; классификатор смотрит на
    объединённый stdout+stderr, а не на усечённый `log_tail`."""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _record_failure_classification(conn, task_id: str, role: str,
                                    numbered: str, text: str) -> str | None:
    """Классифицирует провалившуюся попытку, журналирует сырой текст
    структурно (требование 6, AC-13) и заводит алерты классов «обрыв
    потока»/2 (требования 4-5, AC-11, AC-12). Возвращает класс или `None`.
    """
    failure_class = classify_attempt_failure(text)
    if failure_class is None:
        return None
    # Срез С ХВОСТА, не с головы (ревью T082 итерации 1, замечание major):
    # причина падения — в конце вывода (тот же приём, что и `agent_log.
    # log_tail`), а реалистичный лог попытки почти всегда длиннее
    # LOG_TAIL_CHARS до совпавшей сигнатуры — головной срез её обрезал бы.
    store.journal(conn, task_id, role, "agent failure classified",
                  f"{numbered}: {CLASS_LABELS[failure_class]}; текст: "
                  f"{text.strip()[-config.LOG_TAIL_CHARS:]}")
    target = store.task_target(conn, task_id)
    if failure_class == "stream_broken":
        # Требование 5: алерт обязан открыться независимо от того, каким
        # путём `spend.py` учёл (или не учёл) стоимость этой попытки —
        # заводится здесь явно, а не внутри spend.charge_missing_result.
        alerts.raise_alert(
            conn, target, "incident", "spend.unknown_cost",
            f"{task_id}/{role}: {numbered}, обрыв потока (Connection lost "
            f"mid-response) — стоимость попытки не гарантированно "
            f"восстановлена")
    if failure_class == "session_limit":
        # Триггер №15 (docs/triggers.md): счётчик частоты, не решение по
        # кредам ролей — решение остаётся за Оператором.
        alerts.raise_alert(
            conn, target, "trigger", "triggers.md#15",
            f"{task_id}/{role}: {numbered}, обнаружен лимит сессии "
            f"подписки — триггер №15 (раздельные креды ролей)")
    return failure_class
