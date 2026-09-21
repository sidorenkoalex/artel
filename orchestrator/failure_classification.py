"""Классификация провалившейся попытки агента (SPEC T082, требования 1-2).
Перенесено из orchestrator/runner.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner).

Тексты-сигнатуры и извлечение требуемой версии CLI живут у провайдера
роли шага (`orchestrator/providers/`, SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ,
требование 9): об одном и том же отказе каждый CLI сообщает своими
словами. Здесь остаётся общее — набор классов, их подписи и
последствия: связка транзиентных системных с минутным бэкоффом, алерты
«обрыв потока» и «session limit», обрыв повторов у детерминированного
отказа.
"""
from pathlib import Path

from . import alerts, config, providers, store

# Класс «модель не поддерживается CLI» (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
# требование 4): инцидент 19.09 — «API Error: 400 … does not support this
# model; version 2.1.251 or newer is required». Отказ детерминирован (CLI
# старше модели), повторами не лечится: в связку транзиентных класс не
# входит — `runner._run_attempts` обрывает цикл на первой же попытке,
# исход шага — тот же именованный отказ, что и у предполётной сверки
# модели (`stack.MODEL_UNSUPPORTED_PREFIX`). Сам текст сигнатуры и
# порядок его проверки (раньше общего якоря своего CLI) — у провайдера.
MODEL_UNSUPPORTED_CLASS = "model_unsupported"

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


def required_cli_version(text: str, provider=None) -> str | None:
    """Версия CLI, которую текст попытки называет минимальной («version
    2.1.251 or newer is required»); `None` — текст её не несёт.

    Формулировка своя у каждого CLI, поэтому извлекает её провайдер
    (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 9); `provider=None` —
    провайдер по умолчанию, как у остальных точек разбора вывода."""
    return providers.or_default(provider).required_cli_version(text)


def class_signature_text(failure_class: str, provider=None) -> str:
    """Сигнатуры класса у провайдера одной строкой — для текста отказа
    шага Оператору («CLI отверг модель словами …»). Пустая строка —
    провайдер такого класса не знает."""
    for entry in providers.or_default(provider).failure_signatures():
        if entry.failure_class == failure_class:
            return ", ".join(entry.signatures)
    return ""


def classify_attempt_failure(text: str, provider=None) -> str | None:
    """Класс отказа попытки по её тексту; `None` — нераспознанный (SPEC
    T082, требования 1-2, критерии AC-1..AC-6).

    Классификация — по подстроке в объединённом stdout+stderr попытки,
    без учёта регистра. Сами подстроки и ПОРЯДОК их проверки отдаёт
    провайдер (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 9): порядок
    значим — специфичные списки обязаны перехватывать текст раньше
    общего якоря своего CLI, иначе детерминированный отказ «модель не
    поддерживается» ушёл бы в «системный кандидат» с минутным бэкоффом
    и тремя попытками. Первое совпадение и есть класс.

    Класс из набора провайдера, которого нет в `CLASS_LABELS`, — это
    `None`, а не тихое падение журналирования ниже по течению: набор
    классов общий (требование 9), и провайдер не вправе его расширять.
    """
    lowered = text.lower()
    for entry in providers.or_default(provider).failure_signatures():
        if entry.failure_class not in CLASS_LABELS:
            continue
        if any(sig and sig.lower() in lowered for sig in entry.signatures):
            return entry.failure_class
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

    Сигнатуры — у провайдера РОЛИ ШАГА (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требование 9): роль здесь уже известна,
    и разрешать провайдера отдельным параметром из вызывающего не за
    чем — тот передал бы ровно её же.
    """
    failure_class = classify_attempt_failure(text, providers.for_role(role))
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
