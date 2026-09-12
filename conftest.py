"""Признак роли в окружении вместо клиентского PreToolUse-хука (SPEC
01M2B6K3EM7F2J72RC2F520Y2K, требования 1-2): гейт сбора pytest читает
`ARTEL_ROLE` сам CLI, LLM-независимо — прежний хук `docs/reference/
role-home/claude/hooks/bash_guard.py` работал только через протокол
Claude Code и снят этой же задачей.

Гейт активен, ТОЛЬКО когда `ARTEL_ROLE` есть в окружении процесса (шаг
роли конвейера, `orchestrator/runner.py::role_env`) — без него
(Оператор, CI, автогейт пульта) сбор не трогается вовсе. Под ролью —
отказ (`pytest.exit`), если аргументов-путей нет вовсе ИЛИ среди них
есть хотя бы один нецелевой (не путь к конкретному файлу/каталогу НИЖЕ
`tests/` или `tasks/<id>/acceptance_tests/`) — голый `pytest`, `pytest
tests`, `pytest .`, а также смешанный вызов вида `pytest
tests/test_x.py tests` (целевой путь рядом с нецелевым не спасает от
отказа, иначе нецелевой аргумент всё равно потянул бы за собой сбор
всего дерева) — тот же класс запуска, что раньше ловил
`bash_guard._pytest_verdict`; сфера здесь уже — только СВОЙ процесс
pytest, не произвольная Bash-команда, поэтому формы `python3 -m
unittest` вне зоны действия этого гейта)."""
import os
import sys

import pytest

from orchestrator.config import ARTEL_ROLE_ENV

# Флаги pytest, за которыми следует отдельное значение — не позиционный
# аргумент-путь (тот же список, что нёс `bash_guard._PYTEST_VALUE_FLAGS`).
_VALUE_FLAGS = {"-k", "-m", "-p", "-o", "-c", "-n", "--maxfail",
               "--rootdir", "--confcutdir", "-W"}

REASON = (
    "Сторож роли: полный прогон набора тестов внутри шага запрещён — его "
    "гоняет CI. Запускай только нужные модули или файлы, в переднем "
    "плане: `pytest tests/test_x.py tests/test_y.py` или "
    "`pytest tasks/<id>/acceptance_tests/test_ac1.py`."
)


def _positionals(argv: list) -> list:
    out = []
    skip = False
    for tok in argv:
        if skip:
            skip = False
            continue
        if tok.startswith("-"):
            if tok in _VALUE_FLAGS:
                skip = True
            continue
        out.append(tok)
    return out


def _is_targeted_path(path: str) -> bool:
    """Путь ниже `tests/` (файл или каталог), либо несущий сегмент
    `acceptance_tests` под `tasks/` — форма, которой роль обязана
    запускать тесты (skills/coding-standards.md, skills/test-authoring.md)."""
    norm = path.split("::", 1)[0]
    if norm.startswith("./"):
        norm = norm[2:]
    norm = norm.rstrip("/")
    parts = norm.split("/")
    if parts[0] == "tests" and len(parts) > 1 and parts[1]:
        return True
    if parts[0] == "tasks" and "acceptance_tests" in parts:
        return True
    return False


def pytest_configure(config):
    role = os.environ.get(ARTEL_ROLE_ENV)
    if not role:
        return
    positionals = _positionals(sys.argv[1:])
    if not positionals or not all(_is_targeted_path(p) for p in positionals):
        pytest.exit(REASON, returncode=2)
