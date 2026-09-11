---
task: 01M1VBEKRN0GA029J98S0K2DAQ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на эскалацию «конфликт подтяжки main» (06.09.2026).

Причина: кодовая ветка стартовала от c4f89371 (пин на момент `new`), а
в origin/main с тех пор смержена команда `note` (01M1VBEHTD, 17:31Z),
которая правила те же четыре места `orchestrator/artel.py`, что и
`watch`: строка usage в докстринге, список команд в справке, список
импортов модулей, таблица диспетчера. Все четыре конфликта — «обе
стороны добавили» рядом, содержательного пересечения нет. Второй
конфликт — `docs/codebase-map.md`.

Что сделать разработчику в этом ходе (логику `watch` не менять):
1. Завершить подтяжку: `git merge origin/main` в worktree. В
   `orchestrator/artel.py` во всех четырёх кусках взять ОБЕ стороны:
   строки usage `note …` и `watch …` подряд; в справке — описания
   `notes` и `watch`; в импорте — `notes` и `watch` на своих местах по
   алфавиту (`… doctor, dry_run, fsm, notes, pause, pin, projects,
   prune, release, report, runner, venv, version, watch, workspace,
   zone_lock`); в диспетчере — обе записи `"note"` и `"watch"`.
2. `docs/codebase-map.md` взять из origin/main и перегенерировать
   штатным `python3 scripts/codebase_map.py`, закоммитить.
3. Проверить, что `docs/operator-session.md` после автослияния читается
   (в main правка от `note` рядом с правкой `watch`): один документ,
   без дублей абзацев.
4. Прогнать `tests/test_watch*.py`, тесты CLI (`tests/test_new_argv_parsing.py`,
   `tests/test_version.py`) и планку из worktree
   (`python3 -m unittest discover -s
   tasks/01M1VBEKRN0GA029J98S0K2DAQ/acceptance_tests`), сдать шаг.

Планку не править. Бюджет $45 — запас есть ($16.47 потрачено).
