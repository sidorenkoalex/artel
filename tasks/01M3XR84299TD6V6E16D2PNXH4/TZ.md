---
task: 01M3XR84299TD6V6E16D2PNXH4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Правило о тестовых методах в tests/ и счёт его срабатываний

# ТЗ: Правило о тестовых методах в tests/ и счёт его срабатываний

Источник: решение Оператора 02.10.2026; строки копилки 30.09 (П1) и 02.10
(П1) «answer не принимает мандат „Ослабление тестов разрешено“ в in_dev»;
триггер №31 `docs/triggers.md`.

Факты (origin/main 83a9c96e):
- Гейт неослабления тестов (инвариант 38, с 27.09) отказывает переходу
  `in_dev → verifying`, если из `tests/` пропал тестовый метод. Мандат
  Оператора на это команда `answer` принимает только в `escalated`, а
  гейт состояние задачи не меняет. Дважды (01M3SK48D7RDQPSEN78894GDA5,
  01M3V4ZPB6HFDJ36MTDAQG5VNT) мандат передан обходом «разовое
  исключение».
- Оба раза разработчик переименовал тесты молча, без вопроса Оператору;
  во втором случае при переименовании пропала проверка, которая
  оставалась верной (отказ «дефект пульта» в `orchestrator/canary.py`).
- С 27.09 из 27 смерженных задач, менявших существующие файлы `tests/`,
  метод пропадал в 2.

Решение Оператора: сначала правило в скиле разработчика и наблюдение по
числам; задача на код гейта — по триггеру №31, если правило не сработает.

Требуется:
1. `skills/coding-standards.md`, раздел «Тесты» — новый пункт:
   - существующий тестовый метод в `tests/` не удаляется и не
     переименовывается молча; при переписывании теста под новую
     механику имя метода сохраняется, проверки, которые остаются
     верными, не выбрасываются;
   - если метод действительно нужно удалить или переименовать —
     эскалация ДО сдачи шага (`skills/escalation-rules.md`) с перечнем
     `tests/<файл>.py::<Класс>::<метод>`, причиной и заменой; мандат
     приходит штатным ответом на эскалацию.
   Правка — приложением PLAN (защищённый путь): разработчик кладёт
   готовый текст в приложение, пульт применяет его на мерже.
2. `scripts/test_rule_stats.py` — программа подсчёта только на чтение
   (БД пульта `.artel/state.db`, таблица `steps`, и мержи `origin/main`),
   аргумент `--since YYYY-MM-DD`. Печатает: (1) задачи, где разработчик
   эскалировал с перечнем тестовых методов до отказа гейта; (2) фон —
   смерженные задачи, менявшие существующие файлы `tests/`, без отказа
   гейта; (3) задачи с отказом гейта неослабления без предварительного
   вопроса; (4) задачи с записью журнала «Разовое исключение: запись
   ANSWER в in_dev»; и строку о достижении порога триггера №31 при
   (3) > 0. Черновик Оператора прилагается к задаче ниже — взять за
   основу, привести к `skills/coding-standards.md`.
3. Тест в `tests/` на синтетической БД и синтетическом репозитории
   (без настоящего `.artel/state.db` и сети): каждая из четырёх групп
   считается по своему признаку; эскалация ПОСЛЕ отказа гейта
   относится к группе 3, а не 1; программа ничего не пишет в БД
   (открытие только на чтение).

Зоны: scripts/test_rule_stats.py, tests/test_test_rule_stats.py, docs/codebase-map.md.
Приложением: skills/coding-standards.md (защищённый путь, применяет пульт на мерже).

Только чтение (не менять): skills/escalation-rules.md, docs/triggers.md,
orchestrator/canary.py, orchestrator/answer.py, orchestrator/advance_gates/,
docs/invariants.md, остальные файлы skills/.

Не входит:
- изменение гейта неослабления, команды `answer` и инварианта 38;
- подключение программы к `doctor`, `report` или алертам;
- правка других скилов.

Потолок: $15.

Черновик программы Оператора (основа для требования 2):

```python
"""Статистика правила «тест в tests/ меняется только с вопросом Оператору».

Только чтение: БД пульта (`.artel/state.db`, таблица `steps`) и git главной
копии. Запуск из корня главной копии:

    python3 test_rule_stats.py [--since YYYY-MM-DD]

По умолчанию — с даты коммита правки скила (передать явно).
"""
import argparse
import re
import sqlite3
import subprocess
from collections import defaultdict

REFUSAL = "переход отклонён: гейт неослабления тестов"
MANDATE = "ослабление тестов разрешено мандатом Оператора"
EXCEPTION = "Разовое исключение: запись ANSWER в in_dev"
ASKED_RE = re.compile(r"tests/\S+\.py::\w+::\w+")


def journal(conn, since):
    rows = conn.execute(
        "SELECT task_id, ts, actor, action, detail FROM steps "
        "WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
    by_task = defaultdict(list)
    for task_id, ts, actor, action, detail in rows:
        by_task[task_id].append((ts, actor, action, detail or ""))
    return by_task


def classify(events):
    """Для одной задачи: спросила ли роль ДО отказа гейта, был ли отказ,
    был ли обход, дошёл ли мандат."""
    asked_at = refused_at = None
    exception = mandate = False
    for ts, actor, action, detail in events:
        if (action.startswith("state -> escalated")
                and "эскалация от разработчика" in detail
                and ASKED_RE.search(detail)):
            asked_at = asked_at or ts
        if action == REFUSAL:
            refused_at = refused_at or ts
        if action == EXCEPTION:
            exception = True
        if action == MANDATE:
            mandate = True
    return asked_at, refused_at, exception, mandate


def merged_tasks_touching_tests(since):
    """Задачи, смерженные в main с даты, чей мерж меняет СУЩЕСТВУЮЩИЕ
    файлы tests/ (статус M, не новые файлы)."""
    log = subprocess.run(
        ["git", "log", "origin/main", "--merges", f"--since={since}",
         "--format=%H %s"], capture_output=True, text=True, check=True)
    out = {}
    for line in log.stdout.splitlines():
        sha, subject = line.split(" ", 1)
        task_id = subject.split(":", 1)[0]
        diff = subprocess.run(
            ["git", "diff", "--name-status", f"{sha}^1", sha, "--", "tests/"],
            capture_output=True, text=True, check=True)
        modified = [l.split("\t", 1)[1] for l in diff.stdout.splitlines()
                    if l.startswith("M\t")]
        if modified:
            out[task_id] = modified
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    args = ap.parse_args()
    conn = sqlite3.connect("file:.artel/state.db?mode=ro", uri=True)
    by_task = journal(conn, args.since)
    touched = merged_tasks_touching_tests(args.since)

    asked, refused_silent, workaround, kept_names = [], [], [], []
    for task_id, events in by_task.items():
        asked_at, refused_at, exception, mandate = classify(events)
        if asked_at and (not refused_at or asked_at < refused_at):
            asked.append(task_id)
        elif refused_at:
            refused_silent.append(task_id)
        if exception:
            workaround.append(task_id)
    for task_id in touched:
        if task_id not in asked and task_id not in refused_silent:
            kept_names.append(task_id)

    print(f"Окно: с {args.since}")
    print(f"1. Роль спросила заранее (правило сработало):       {len(asked)}  {asked}")
    print(f"2. Фон: мержи, менявшие существующие tests/, гейт молчал: {len(kept_names)}")
    print(f"3. Гейт отказал без вопроса (правило не сработало):  {len(refused_silent)}  {refused_silent}")
    print(f"4. Обход «разовое исключение»:                       {len(workaround)}  {workaround}")
    events = len(asked) + len(refused_silent)
    print(f"Случаев «метод теста пропадает» (1+3): {events}; "
          f"доля от задач, менявших tests/: {events}/{events + len(kept_names)}")
    if refused_silent:
        print("Порог пересмотра достигнут: есть отказ гейта без вопроса — "
              "вернуться к задаче «гейт неослабления переводит в escalated».")


if __name__ == "__main__":
    main()
```
