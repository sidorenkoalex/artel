#!/usr/bin/env python3
"""Сторож Bash-команд роли: PreToolUse-хук курируемого слоя (`.artel/home/
.claude/settings.json`, `hooks.PreToolUse`, matcher `Bash`).

Назначение одно: не дать роли запустить ПОЛНЫЙ набор тестов внутри шага.
Правило скилов (`skills/coding-standards.md`, `skills/test-authoring.md`,
`skills/review-checklist.md`) — «полный набор `tests/` в шаге не
запускать, его гоняет CI» — до 05.09 держалось только текстом: роль
developer задачи 01M1PNBSHR2PMFECMP7C204MF1 дважды запустила голый
`python3 -m unittest` (это discovery всего дерева), прогон завис, шаг
ушёл в таймаут 45 минут и съел $35 частичной стоимости. Хук делает
правило исполняемым на уровне CLI: команда отклоняется до запуска, а
причина возвращается роли текстом (код выхода 2 — блокирующий отказ
хука Claude Code, stderr уходит модели).

Что отклоняется (каждый сегмент команды, разделённой `;`, `&&`, `||`,
`|`, проверяется отдельно):
- `python3 -m unittest` без имён модулей/файлов (голый вызов = discover);
- `python3 -m unittest discover …` в любой форме;
- `python3 -m pytest` / `pytest` без аргументов-путей, либо с каталогом
  `tests`, `tests/`, `.` в аргументах.

Что проходит: конкретные модули (`python3 -m unittest tests.test_x`),
файлы планки (`… tasks/<id>/acceptance_tests/test_ac1.py`), pytest по
файлу, любые не-тестовые команды. Хук не вмешивается, если stdin не
разобрался как JSON, — молчаливый отказ был бы отказом без причины.
"""
from __future__ import annotations

import json
import re
import shlex
import sys

_PYTHON = re.compile(r"^(python|python3)(\.\d+)?$")
_SPLIT = re.compile(r"\s*(?:;|&&|\|\||\|)\s*")
# Флаги, за которыми следует отдельное значение (если не в форме --x=y).
_UNITTEST_VALUE_FLAGS = {"-k", "-p", "--pattern", "-s", "--start-directory",
                         "-t", "--top-level-directory"}
_PYTEST_VALUE_FLAGS = {"-k", "-m", "-p", "-o", "-c", "-n", "--maxfail",
                       "--rootdir", "--confcutdir", "-W"}
_WHOLE_TREE = {".", "./", "tests", "tests/", "./tests", "./tests/"}
# Перенаправления вывода: `2>&1`, `>`, `>>`, `<`, `&>`, `2>file`. Оператор
# без цели (`>` , `2>`) забирает следующий токен как файл.
_REDIRECT = re.compile(r"^(\d*|&)(>>?|<)(.*)$")

REASON = (
    "Сторож роли: полный прогон набора тестов внутри шага запрещён — его "
    "гоняет CI (инцидент 05.09: голый `python3 -m unittest` завис до "
    "таймаута шага). Запускай только нужные модули или файлы, в переднем "
    "плане: `python3 -m unittest tests.test_x tests.test_y` или "
    "`python3 -m unittest tasks/<id>/acceptance_tests/test_ac1.py`."
)


def _positionals(args: list[str], value_flags: set[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        redirect = _REDIRECT.match(tok)
        if redirect:
            if not redirect.group(3):
                skip = True  # цель перенаправления — следующий токен
            continue
        if tok.startswith("-"):
            if tok in value_flags:
                skip = True
            continue
        out.append(tok)
    return out


def _segment_verdict(segment: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    # Снимаем префиксы окружения вида FOO=bar и `env`.
    while tokens and ("=" in tokens[0] and not tokens[0].startswith("-")
                      or tokens[0] == "env"):
        tokens = tokens[1:]
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]
    if head == "pytest":
        return _pytest_verdict(tokens[1:])
    if _PYTHON.match(head) and len(tokens) >= 3 and tokens[1] == "-m":
        module, rest = tokens[2], tokens[3:]
        if module == "unittest":
            return _unittest_verdict(rest)
        if module == "pytest":
            return _pytest_verdict(rest)
    return None


def _unittest_verdict(rest: list[str]) -> str | None:
    if "discover" in rest:
        return REASON
    if not _positionals(rest, _UNITTEST_VALUE_FLAGS):
        return REASON
    return None


def _pytest_verdict(rest: list[str]) -> str | None:
    positionals = _positionals(rest, _PYTEST_VALUE_FLAGS)
    if not positionals:
        return REASON
    if any(p in _WHOLE_TREE for p in positionals):
        return REASON
    return None


def verdict(command: str) -> str | None:
    """Причина отказа для команды целиком или None, если команда проходит."""
    for segment in _SPLIT.split(command or ""):
        reason = _segment_verdict(segment)
        if reason:
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    reason = verdict(command or "")
    if reason:
        sys.stderr.write(reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
