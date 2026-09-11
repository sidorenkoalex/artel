"""Идентификатор сессии оркестратора — единая функция для всех команд
(SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC, требование 1, AC-1).

Раньше жила только в `orchestrator/lease.py` (SPEC T044) и была доступна
лишь мутирующим командам, уже проходящим через lease-обвязку
(`lease.run_locked`). Вынесена сюда отдельным листом графа импортов
(изначально только stdlib, тем же приёмом, что и `orchestrator/
liveness.py`), чтобы любой модуль — включая `orchestrator/store.py::
journal` — мог резолвить identity вызывающей сессии ТЕМ ЖЕ источником,
каким её резолвит lease, а не собственным (и потому способным разойтись)
чтением `ARTEL_SESSION_ID`. `lease.resolve_session_id` остаётся тем же
самым объектом функции (`from .session import resolve_session_id`), не
второй копией — правка источника identity здесь одинаково видна под
обоими именами.

С задачи 01M290PP4KBTG1KYS1PWKQJH6T модуль больше не «только stdlib» —
последний fallback (`ppid-<n>`) не переживал репарентинг отвязанного
`auto` (его `ppid` становится `1` после отвязки от сессии, `ppid` самой
интерактивной сессии — другой; копилка 11.09). Источник истины сдвинут
на файл `.artel/session-id` — общий для процессов одной и той же
рабочей копии пульта независимо от их собственного `ppid`; путь читает
`config.ROOT` внутри функции на каждый вызов (не кэширует на уровне
модуля), иначе патч `config.ROOT` тестовой песочницей (`tests.sandbox.
TmpRootTest`) не подхватился бы. `config.py` сама ничего не
импортирует — кругового импорта нет.
"""
import os

from . import config


def _session_id_file():
    return config.ROOT / ".artel" / "session-id"


def _persisted_session_id() -> str | None:
    """Identity из файла сессии — читает, заводит при первом обращении
    (SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование 2, AC-4).

    Значение, которым файл заводится впервые, — тот же формат, что и
    прежний `ppid-<n>`-fallback, посчитанный В МОМЕНТ создания: он же и
    остаётся identity сессии на весь срок жизни файла, независимо от
    того, что `os.getppid()` вернёт при следующих вызовах (ровно так
    отвязанный `auto`, репарентнутый на `ppid=1` ПОСЛЕ отвязки, и
    интерактивная сессия, вызывающая `watch --mine` заведомо другим
    `ppid`, видят одну и ту же identity — обе читают уже существующий
    файл, а не пересчитывают живой `ppid`).

    `None` — файл недоступен ни на чтение, ни на запись (ФС только для
    чтения, `.artel/` нет и не завести): вызывающий код сам деградирует
    к живому `ppid-<n>`, как и раньше при отсутствии переменной/файла.
    """
    path = _session_id_file()
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    except OSError:
        return None
    fresh = f"ppid-{os.getppid()}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fresh, encoding="utf-8")
    except OSError:
        return None
    return fresh


def resolve_session_id(session_id: str | None = None) -> str:
    """Identity вызывающей сессии.

    Порядок источников (SPEC T044, требование 9; SPEC
    01M290PP4KBTG1KYS1PWKQJH6T, требование 2): явный параметр (тестовый
    шов приёмочных тестов) > `ARTEL_SESSION_ID` из окружения > файл
    сессии в `.artel/` (заводится при первом обращении) > `ppid-<n>`
    родительского процесса — последний fallback только когда нет ни
    переменной, ни файла (ФС недоступна на запись).
    """
    if session_id:
        return session_id
    env_value = os.environ.get("ARTEL_SESSION_ID")
    if env_value:
        return env_value
    return _persisted_session_id() or f"ppid-{os.getppid()}"
