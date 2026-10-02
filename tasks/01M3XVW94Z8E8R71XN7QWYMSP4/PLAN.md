---
task: 01M3XVW94Z8E8R71XN7QWYMSP4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: прогон планки после подтяжки main исполняет долгоживущую группу; правило о `.md` в `acceptance_tests/`

## Подход
Единственная точка кода — `orchestrator/pull.py::_materialize_and_run_plank`,
вызов `acceptance.run` после подтяжки. Перед ним — тот же узел, что у
перехода `in_dev → verifying` (`orchestrator/advance_gates/acceptance.py:233-238`):
`acceptance_gates.long_lived_manifest(task_id, t, target)`, затем
`acceptance.run(tdir, cwd=wt_path, extra=sorted(digests))`, если лок есть и
перечень непуст; иначе — прежний вызов без `extra`. Своего правила выбора
файлов (имени файла перечня, его разбора, глоба по префиксу) `pull.py` не несёт.

Три исхода одной ветки:
- перечень непуст → долгоживущие файлы идут в тот же прогон pytest; красный
  файл даёт прежнюю эскалацию «приёмочные тесты красные после подтяжки»,
  в хвосте — строка `долгоживущие файлы: …` из `acceptance.run`;
- `long_lived_manifest` вернул `None` → `Refused` с текстом «перечень
  долгоживущих файлов планки не прочитан после подтяжки <ветка>: <причина>»,
  запись журнала «переход отклонён: перечень долгоживущих файлов не прочитан»,
  прогона нет (fail-closed, ADR-0002); состояние задачи не меняется — тот же
  класс исхода, что существующий отказ «планка не найдена в источнике»;
- `{}` (нет лока, лок до ADR-0020, внешний target) → прежний вызов без `extra`.

Строка задачи `t` (уже есть у `evaluate`) передаётся в
`_materialize_and_run_plank` новым параметром. Импорт `advance_gates.acceptance`
— внутри функции: модуль импортирует `fsm`, а `fsm` импортирует `pull`
(верхний импорт дал бы цикл при импорте `pull` первым).

Правило о `.md` в `acceptance_tests/` — приложение к `skills/test-authoring.md`
ниже (путь защищённый, применяет пульт на мерже).

## Шаги
1. `orchestrator/pull.py`: чтение перечня через `long_lived_manifest`,
   отказ на сбое, `extra=` в прогон; `t` параметром. Регенерация
   `docs/codebase-map.md`.
2. `tests/test_pull_long_lived_plank.py` — четыре теста (AC-1…AC-4) на
   `pull.evaluate` с настоящим прогоном pytest.
3. Приложение-диф к `skills/test-authoring.md` (раздел ниже).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (AC-1, AC-2, AC-5) |
| 2 | 1 (AC-3) |
| 3 | 1 (AC-4) |
| 4 | 3 (AC-6) |
| 5 | 2 |

Проверка:
- `python3 -m pytest tasks/01M3XVW94Z8E8R71XN7QWYMSP4/acceptance_tests/test_pull_long_lived_plank.py tests/test_pull.py tests/test_pull_additive_conflict.py tests/test_pull_conflict_marker_states.py -p no:cacheprovider -p timeout -o timeout=120` — 48 passed, 4 subtests passed.
- `python3 -m pytest tests/test_pull_long_lived_plank.py …` — 4 passed.
- Мутации (временные, код возвращён): прогон без `extra` — красны
  AC-1/AC-2; `if not green and not long_lived` — красен AC-2; `None` →
  `{}` — красен AC-3; отказ на пустом перечне (`if not digests`) — красны
  обе подсценки AC-4.
- `test_ac6_skill_appendix.py` читает PLAN.md из артефактной ветки — до
  автокоммита шага его в ветке нет, локально не прогоняется; опоры
  текста («acceptance_tests», «.md», «докстринг», «PLAN», «SPEC», «сним»,
  «main», «guard», «--all», «заголовоч») сверены по добавленным строкам.

## Влияние на систему
- Прогон после подтяжки становится строже, не мягче: добавляется группа
  файлов и отказ на сбое чтения перечня; задачи без перечня — байт в байт
  прежний вызов `acceptance.run(tdir, cwd=wt_path)`.
- Гейты `in_dev → verifying`, автогейт, сверка лока перечня
  (`_long_lived_manifest_refuses`) не тронуты; файлы «только чтение» SPEC
  не менялись.
- Существующие тесты `pull` зелёные без правки (сигнатура `evaluate` та же).
- Откат — revert коммита задачи.

## Риски
- Отказ на сбое перечня оставляет слияние в ветке (merge уже сделан); при
  повторном advance ветка свежа и прогон после подтяжки не повторится —
  но тот же сбой перечня поймает переход `in_dev → verifying`
  (`_long_lived_manifest_refuses` и прогон планки с перечнем), так что
  непрогнанная группа дальше не пройдёт. То же поведение уже у отказа
  «планка не найдена в источнике».

## Предложения системе
- `orchestrator/advance_gates/acceptance.py` и `orchestrator/pull.py` теперь
  повторяют одну и ту же связку «`long_lived_manifest` → `extra` для
  `acceptance.run`»; общий помощник (например, `acceptance_gates.run_groups`)
  убрал бы дублирование трёх строк, но оба файла вне одной зоны этой задачи.

## Приложение: диф `skills/test-authoring.md`

Проверено: `git apply --check` на чистом дереве ветки задачи (база — main
4abfce0c) — применяется без ошибок.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 395b5aa0..07d4a5fa 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -64,6 +64,14 @@ guard разбирает её текстом, без импорта файлов
 пока ты не переименуешь файл под `_*.py` или не встроишь его содержимое
 в сами тесты.
 
+## Файлы `.md` в `acceptance_tests/` — не класть
+В `acceptance_tests/` не клади файлы `.md` (README, заметки к планке):
+пояснения к планке — в докстрингах тестов (модуля и методов), а
+обоснование выбора — в PLAN/SPEC задачи. Причина: снимок артефактной
+ветки переносит каталог `tasks/<id>/` в main, где `scripts/guard.py
+--all` требует заголовочный блок (frontmatter) у каждого `.md` в
+`tasks/`; README без блока красит main (30.09 — 3 ч 47 мин).
+
 ## Две группы тестов планки — строка группы в каждом `test_*.py`
 Каждый файл `test_*.py` планки относится ровно к одной из двух групп
 (ADR-0020) и называет её в докстринге модуля отдельной строкой, ровно
```
