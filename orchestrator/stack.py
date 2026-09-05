"""Манифест объявленного стека пульта (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,
требование 1): минимальная версия Python, внешние инструменты (`git`,
`gh`, `claude`) с минимальной версией и способом проверки, список
допустимых исключений правила «сторонних пакетов нет» (пуст).

Единственный источник значений — этот модуль; `docs/stack.md` описывает
то же самое человекочитаемо и ссылается сюда, не дублируя числа.

`check_stack()` (требование 4) сравнивает факт с манифестом: только
`subprocess.run` локальных CLI, без сети (docs/invariants.md,
инвариант 35).
"""
import re
import subprocess
import sys
from collections import namedtuple

# `X | None` в аннотациях кода пульта (например,
# orchestrator/doctor.py::cli_version) требует Python 3.10+ без
# `from __future__ import annotations` — 3.11 фиксирует уже принятое
# решение с запасом, не голый минимум для этого синтаксиса (TZ.md).
REQUIRED_PYTHON = (3, 11)

# Список допустимых исключений правила «сторонних пакетов нет» — записи
# вида (модуль, причина); пуст на момент этой задачи (AC-3). Будущая
# запись обязана нести причину вторым элементом пары.
THIRD_PARTY_EXCEPTIONS = ()

ToolRequirement = namedtuple("ToolRequirement", "minimum command")

REQUIRED_TOOLS = {
    "git": ToolRequirement((2, 30, 0), ("git", "--version")),
    "gh": ToolRequirement((2, 0, 0), ("gh", "--version")),
    "claude": ToolRequirement((1, 0, 0), ("claude", "--version")),
}

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

StackCheck = namedtuple("StackCheck", "name status detail")


def _python_check() -> StackCheck:
    running = tuple(sys.version_info[:2])
    version_text = ".".join(str(part) for part in sys.version_info[:3])
    if running >= REQUIRED_PYTHON:
        return StackCheck("python", "ok", f"Python {version_text}")
    required_text = ".".join(str(part) for part in REQUIRED_PYTHON)
    return StackCheck(
        "python", "warn",
        f"Python {version_text} ниже минимальной {required_text}")


def _tool_check(name: str, requirement: ToolRequirement) -> StackCheck:
    command = list(requirement.command)
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return StackCheck(
            name, "fail",
            f"{name} не найден в PATH/системе (команда "
            f"`{' '.join(command)}` не выполнилась)")

    match = VERSION_RE.search(result.stdout)
    if match is None:
        return StackCheck(
            name, "warn",
            f"{name}: версия не распозналась в выводе `{' '.join(command)}`")

    version = tuple(int(part) for part in match.group(0).split("."))
    if version >= requirement.minimum:
        return StackCheck(name, "ok", f"{name} {match.group(0)}")
    required_text = ".".join(str(part) for part in requirement.minimum)
    return StackCheck(
        name, "warn",
        f"{name} {match.group(0)} ниже минимальной {required_text}")


def check_stack() -> list:
    """Требование 4: по одной проверке на каждый инструмент манифеста
    (Python + `git`/`gh`/`claude`) — WARN при заниженной версии, FAIL при
    отсутствии инструмента.
    """
    checks = [_python_check()]
    for name, requirement in REQUIRED_TOOLS.items():
        checks.append(_tool_check(name, requirement))
    return checks
