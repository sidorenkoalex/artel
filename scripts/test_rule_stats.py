#!/usr/bin/env python3
"""Статистика правила «тестовый метод в tests/ меняется только с вопросом
Оператору» (SPEC 01M3XR84299TD6V6E16D2PNXH4; правило — раздел «Тесты»
`skills/coding-standards.md`, порог пересмотра — триггер №31
`docs/triggers.md`).

Только чтение: журнал `steps` БД пульта (`config.DB`, открывается в режиме
`mode=ro`) и мержи `origin/main` git главной копии. Запуск из корня главной
копии:

    python3 scripts/test_rule_stats.py --since YYYY-MM-DD

Окно — с начала суток `--since` по UTC (журнал пишет время в UTC), для
журнала и для мержей одинаково. Группы задач за окно:
1. разработчик эскалировал с перечнем `tests/<файл>.py::<Класс>::<метод>`
   до отказа гейта неослабления (или без отказа вовсе);
2. фон — мержи в `origin/main`, меняющие существующие файлы `tests/`
   (статус `M` против первого родителя), без задач групп 1 и 3;
3. отказ гейта неослабления без предварительного вопроса (в том числе
   эскалация с перечнем ПОСЛЕ отказа);
4. запись журнала «Разовое исключение: запись ANSWER в in_dev».
Непустая группа 3 — строка о достижении порога триггера №31.

Код возврата: 0 — сводка напечатана; 2 — БД или git не прочитаны (причина в
stderr): неполная сводка выглядела бы как «правило работает».
"""
import argparse
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

# У скрипта в sys.path лежит scripts/, а не корень; тот же приём, что у
# `scripts/guard.py`. Строки действий гейта берутся из его модуля, чтобы
# переименование действия не обнулило счёт молча.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from orchestrator.advance_gates.test_integrity import (  # noqa: E402
    TEST_INTEGRITY_REFUSAL_ACTION)

ESCALATED_ACTION = "state -> escalated"
DEVELOPER_ESCALATION = "эскалация от разработчика"
EXCEPTION_ACTION = "Разовое исключение: запись ANSWER в in_dev"
METHOD_LIST_RE = re.compile(r"tests/\S+\.py::\w+::\w+")
# Тема мержа пульта — «<id>: merge task/<id>-…»; прочие мержи первой линии
# (ручные, без id задачи) в счёт не идут.
MERGE_SUBJECT_RE = re.compile(r"^([0-9A-Za-z]+): ")


class StatsError(Exception):
    """Источник данных не прочитан — сводки не будет."""


def since_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"ожидается дата YYYY-MM-DD, получено {text!r}") from None


def journal(db_path: Path, since: date) -> dict:
    """{task_id: [(ts, action, detail), …]} записей `steps` не раньше
    начала суток `since`, по времени. Соединение — только на чтение: URI
    `mode=ro` отказывает в любой записи на уровне SQLite."""
    if not db_path.is_file():
        raise StatsError(f"нет БД пульта {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(
                "SELECT task_id, ts, action, detail FROM steps "
                "WHERE ts >= ? ORDER BY ts, id",
                (since.isoformat(),)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise StatsError(f"БД пульта {db_path} не прочитана: {exc}") from exc
    by_task = defaultdict(list)
    for task_id, ts, action, detail in rows:
        by_task[task_id].append((ts, action or "", detail or ""))
    return by_task


def classify(events: list) -> tuple:
    """(момент первой эскалации разработчика с перечнем методов, момент
    первого отказа гейта неослабления, была ли запись разового исключения)."""
    asked_at = refused_at = None
    exception = False
    for ts, action, detail in events:
        if (action == ESCALATED_ACTION and DEVELOPER_ESCALATION in detail
                and METHOD_LIST_RE.search(detail)):
            asked_at = asked_at or ts
        if action == TEST_INTEGRITY_REFUSAL_ACTION:
            refused_at = refused_at or ts
        if action == EXCEPTION_ACTION:
            exception = True
    return asked_at, refused_at, exception


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=config.ROOT,
                              capture_output=True, text=True)
    except OSError as exc:
        raise StatsError(f"git {' '.join(args)}: {exc}") from exc
    if proc.returncode != 0:
        raise StatsError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def merged_tasks_touching_tests(since: date) -> dict:
    """{task_id: [файлы]} мержей первой линии `origin/main` не раньше начала
    суток `since` (UTC), которые меняют СУЩЕСТВУЮЩИЕ файлы `tests/` —
    статус `M` против первого родителя; новые файлы в счёт не идут.

    Окно сверяется по времени коммиттера в секундах эпохи, а не флагом
    `git log --since`: его разбор даты без времени зависит от часового пояса
    машины и текущего времени суток."""
    start = int(datetime.combine(since, datetime.min.time(),
                                 tzinfo=timezone.utc).timestamp())
    log = _git("log", f"origin/{config.MAIN_BRANCH}", "--merges",
               "--first-parent", "--format=%H %ct %s")
    out: dict = {}
    for line in log.splitlines():
        sha, stamp, subject = (line.split(" ", 2) + [""])[:3]
        if int(stamp) < start:
            continue
        match = MERGE_SUBJECT_RE.match(subject)
        if match is None:
            continue
        diff = _git("diff", "--name-status", f"{sha}^1", sha, "--", "tests/")
        modified = [row.split("\t", 1)[1] for row in diff.splitlines()
                    if row.startswith("M\t")]
        if modified:
            out.setdefault(match.group(1), []).extend(modified)
    return out


def groups(by_task: dict, touched: dict) -> tuple:
    """(группа 1, группа 2, группа 3, группа 4) — отсортированные списки id."""
    asked, refused_silent, workaround = [], [], []
    for task_id, events in by_task.items():
        asked_at, refused_at, exception = classify(events)
        if asked_at and (refused_at is None or asked_at < refused_at):
            asked.append(task_id)
        elif refused_at:
            refused_silent.append(task_id)
        if exception:
            workaround.append(task_id)
    background = [task_id for task_id in touched
                  if task_id not in asked and task_id not in refused_silent]
    return (sorted(asked), sorted(background), sorted(refused_silent),
            sorted(workaround))


def _print_group(number: int, title: str, task_ids: list) -> None:
    print(f"{number}. {title}: {len(task_ids)}")
    for task_id in task_ids:
        print(f"   {task_id}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True, type=since_date,
                    help="начало окна, YYYY-MM-DD (UTC)")
    args = ap.parse_args(argv)
    try:
        by_task = journal(Path(config.DB), args.since)
        touched = merged_tasks_touching_tests(args.since)
    except StatsError as exc:
        print(f"test_rule_stats: {exc}", file=sys.stderr)
        return 2
    asked, background, refused_silent, workaround = groups(by_task, touched)

    print(f"Окно: с {args.since.isoformat()} (UTC)")
    _print_group(1, "Разработчик спросил заранее (правило сработало)", asked)
    _print_group(2, "Фон: мержи, менявшие существующие tests/, без отказа "
                    "гейта", background)
    _print_group(3, "Гейт отказал без вопроса (правило не сработало)",
                 refused_silent)
    _print_group(4, "Обход «разовое исключение»", workaround)
    events = len(asked) + len(refused_silent)
    print(f"Случаев «метод теста пропадает» (1+3): {events}; доля от задач, "
          f"менявших tests/: {events}/{events + len(background)}")
    if refused_silent:
        print("Порог триггера №31 достигнут: есть отказ гейта неослабления без "
              "вопроса — вернуться к задаче «гейт неослабления переводит в "
              "escalated».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
