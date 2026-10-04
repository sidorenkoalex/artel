"""Генератор идентификатора задачи (SPEC T094, требование 2).

Единственное место кодовой базы, которому разрешено знать формат id:
`new_task_id()` возвращает валидный ULID (26 символов Crockford base32,
без буквенного префикса) — время (48 бит, миллисекунды Unix-эпохи) +
случайность (80 бит, `os.urandom`). Уникальность — по построению
(128 бит энтропии времени+случайности): клейма, отката или гонки за
номер, в отличие от прежнего счётчика `store.task_counters` (требование
6 — тот контур замораживается как legacy, не удаляется), для ULID не
существует.

Старые идентификаторы формата `Tnnn` (`store.TASK_ID`, требование 6)
этой функцией не порождаются и не парсятся — остальной код обращается
с любым id (новым и историческим) как с непрозрачной строкой:
`store.get_task`/резолвер префикса не проверяют ни длину, ни алфавит.
"""
import os
import re
import time

# Crockford base32: без I/L/O/U — визуально похожи на 1/1/0/V, стандартный
# алфавит ULID (https://github.com/ulid/spec).
_ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_TIME_CHARS = 10  # 50 бит вместимости — с запасом над 48-битным timestamp
_RANDOM_CHARS = 16  # 80 бит случайности


def _encode(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _ENCODING[value & 0x1F]
        value >>= 5
    return "".join(chars)


def new_task_id() -> str:
    """Новый ULID задачи — единственный генератор id в кодовой базе."""
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(timestamp_ms, _TIME_CHARS) + _encode(randomness, _RANDOM_CHARS)


_LEGACY_ID = re.compile(r"T\d+\Z")


def is_task_id_form(text: str) -> bool:
    """`text` по форме — id задачи пульта или его префикс: непустая строка
    алфавита ULID не длиннее полного id, либо исторический `Tnnn`.

    Нужна проверке формы поля `merge_after` (SPEC
    01M44EP0D47F498TEE08MNGBYT, требование 1), у которой нет доступа к
    БД: формат id знает только этот модуль, поэтому и правило формы
    живёт здесь, рядом с генератором."""
    if not text:
        return False
    if _LEGACY_ID.match(text):
        return True
    return (len(text) <= _TIME_CHARS + _RANDOM_CHARS
            and all(ch in _ENCODING for ch in text))
