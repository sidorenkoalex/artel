"""Классификация провалившейся попытки агента (SPEC T082, требования 1-2).
Перенесено из orchestrator/runner.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner).
"""
import re
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

# Класс «модель не поддерживается CLI» (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
# требование 4): сигнатура инцидента 19.09 — «API Error: 400 … does not
# support this model; version 2.1.251 or newer is required». Отказ
# детерминирован (CLI старше модели), повторами не лечится: класс
# проверяется РАНЬШЕ общего якоря «API Error:» (иначе тот забирал бы его
# в «системный кандидат» с минутным бэкоффом и эскалацией) и в связку
# транзиентных не входит — `runner._run_attempts` обрывает цикл на
# первой же попытке, исход шага — тот же именованный отказ, что и у
# предполётной сверки модели (`stack.MODEL_UNSUPPORTED_PREFIX`).
MODEL_UNSUPPORTED_SIGNATURE = "does not support this model"
MODEL_UNSUPPORTED_CLASS = "model_unsupported"
# Требуемая версия из того же текста — для отказа шага: «version X or
# newer is required» (модель может отсутствовать в таблице
# `stack.MODEL_MIN_CLI_VERSION`, тогда число известно только отсюда).
MODEL_REQUIRED_VERSION_RE = re.compile(
    r"version\s+(\d+\.\d+\.\d+)\s+or newer is required", re.IGNORECASE)

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
    MODEL_UNSUPPORTED_CLASS: "класс «модель не поддерживается CLI» "
                             "(детерминированный отказ, без повторов)",
}


def required_cli_version(text: str) -> str | None:
    """Версия CLI, которую текст попытки называет минимальной («version
    2.1.251 or newer is required»); `None` — текст её не несёт."""
    match = MODEL_REQUIRED_VERSION_RE.search(text)
    return match.group(1) if match else None


def classify_attempt_failure(text: str) -> str | None:
    """Класс отказа попытки по её тексту; `None` — нераспознанный (SPEC
    T082, требования 1-2, критерии AC-1..AC-6).

    Класс «модель не поддерживается CLI» (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
    требование 4) проверяется первым: сигнатура однозначна, а любой из
    списков ниже (в том числе общий якорь «API Error:», которым текст
    инцидента начинается) увёл бы детерминированный отказ в повторы.
    """
    lowered = text.lower()
    if MODEL_UNSUPPORTED_SIGNATURE in lowered:
        return MODEL_UNSUPPORTED_CLASS
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
