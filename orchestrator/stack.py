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

# Версия основных джобов CI и локальной разработки (01M1RDCCKBQMJ5G2K9
# ANJP059H, ANSWER-1, вопрос 2) — отдельная от REQUIRED_PYTHON (минимум
# поддержки): поднимается Оператором вместе с pyenv, не автоматически.
CURRENT_STABLE_PYTHON = (3, 13)

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

# Инструменты, чей абсолютный путь `orchestrator.runner.role_env` резолвит
# через `shutil.which` для сборки PATH роли (SPEC
# 01M1RDCEF0JZ4AVQRE43JFH8TN, требование 1, AC-1/AC-2): те же три внешних
# CLI, что и `REQUIRED_TOOLS`, плюс `python3` — интерпретатор роли, для
# которого сам which-путь не используется (роль получает каталог
# `sys.executable` пульта, AC-3), но присутствие в PATH/системе всё равно
# проверяется тем же способом (AC-6 — отсутствие ЛЮБОГО из четырёх обязано
# останавливать шаг, включая python3).
DECLARED_TOOLS = ("python3",) + tuple(REQUIRED_TOOLS.keys())

# Белый список переменных окружения роли (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN,
# требования 2, 5, AC-4/AC-5): единственный источник для
# `orchestrator.runner.role_env` — роль не наследует `os.environ` Оператора
# целиком, только эти имена, у каждого есть причина.
ROLE_ENV_ALLOWLIST = {
    "HOME": "домашний каталог курируемого слоя роли (git-конфиг, CLI claude)",
    "CLAUDE_CONFIG_DIR": "путь курируемого `.claude/` роли (ADR-0003 п.14)",
    "GIT_AUTHOR_NAME": "автор коммита роли — предписанный git commit шага",
    "GIT_AUTHOR_EMAIL": "почта автора коммита роли",
    "GIT_COMMITTER_NAME": "коммитер коммита роли — то же требование git",
    "GIT_COMMITTER_EMAIL": "почта коммитера коммита роли",
    "CLAUDE_CODE_OAUTH_TOKEN": "токен подписки CLI claude для роли",
    "ANTHROPIC_API_KEY": "альтернативный канал токена CLI claude (ambient)",
    "LANG": "локаль — предсказуемый разбор вывода CLI claude/git",
    "TMPDIR": "временный каталог — CLI claude/git пишут туда рабочие файлы",
    "TERM": "тип терминала — вывод CLI claude зависит от него",
}

# Семейство локали (LC_ALL, LC_CTYPE, ...) — префиксом, а не перечислением:
# та же причина, что и у LANG выше, но имён в семействе много и заранее не
# перечислить (требование 2 SPEC называет «LANG/LC_*» одной строкой).
ROLE_ENV_ALLOWLIST_PREFIXES = {
    "LC_": "семейство локали (LC_ALL и т.п.) — тот же повод, что и LANG",
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


def python_version_string() -> str:
    """Версия для `actions/setup-python` (`python-version`) — текущая
    стабильная версия основных джобов CI (01M1RDCCKBQMJ5G2K9ANJP059H,
    требование 1): `CURRENT_STABLE_PYTHON` в формате `major.minor`, без
    посторонних символов — так, как `setup-python` принимает значение.
    """
    return ".".join(str(part) for part in CURRENT_STABLE_PYTHON)


def check_stack() -> list:
    """Требование 4: по одной проверке на каждый инструмент манифеста
    (Python + `git`/`gh`/`claude`) — WARN при заниженной версии, FAIL при
    отсутствии инструмента.
    """
    checks = [_python_check()]
    for name, requirement in REQUIRED_TOOLS.items():
        checks.append(_tool_check(name, requirement))
    return checks
