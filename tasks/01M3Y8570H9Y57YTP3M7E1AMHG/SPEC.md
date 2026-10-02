---
task: 01M3Y8570H9Y57YTP3M7E1AMHG
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/runner.py, tests/test_test_author_long_lived_artifact.py, docs/codebase-map.md
budget_usd: 25
---

# SPEC: Шаг test_author с целиком долгоживущей планкой не считается проваленным

## Контекст
`orchestrator/runner.py::_missing_required_artifact` (строки 996–1021)
засчитывает шаг роли `test_author`, только если в
`tasks/<id>/acceptance_tests/` рабочего каталога роли есть хотя бы один
файл; иначе `run_agent_once` (строка 1126) уводит шаг в
`_finish_missing_artifact` — «шаг завершён без артефакта acceptance_tests/»,
`agent run FAILED` и повтор попытки. По ADR-0020 планка может быть
целиком долгоживущей: тесты лежат в `tests/test_<префикс задачи>_<имя>.py`
(`scripts/guard.py::is_long_lived_test_path`, строка 1826), а перечень
`acceptance_tests/long_lived.sha256.txt` пишет пульт уже после шага роли.
Прежний обход (`acceptance_tests/README.md`) закрыт запретом `.md` в
`acceptance_tests/` (`skills/test-authoring.md`, мерж
01M3XVW94Z8E8R71XN7QWYMSP4). 02.10 12:03Z шаг test_author задачи
01M3Y75GCRESC2KDS9VPRJK4PS написал только долгоживущий файл и был признан
проваленным ($2.20, попытка 2/3).

## Требования
1. Для роли `test_author` шаг считается сданным, если в рабочем каталоге
   роли есть хотя бы один файл под `tasks/<id>/acceptance_tests/` ЛИБО
   хотя бы один долгоживущий файл задачи — путь, для которого
   `guard.is_long_lived_test_path(task_id, rel)` истинно (новый или
   изменённый относительно базы ветки, тем же признаком, которым пульт
   коммитит долгоживущие файлы test_author —
   `orchestrator/checkpoint.py::_test_author_own_paths`). Правило пути —
   только через `guard.is_long_lived_test_path`, без второй копии.
2. Нет ни того, ни другого — прежний отказ «шаг завершён без артефакта …»;
   текст отказа называет обе ожидаемые формы (файл в
   `tasks/<id>/acceptance_tests/` и долгоживущий файл
   `tests/test_<префикс задачи>_<имя>.py`).
3. Роли `analyst`, `developer`, `reviewer` — без изменений поведения
   проверки обязательного артефакта.
4. Тесты — в новом файле `tests/test_test_author_long_lived_artifact.py`,
   каждый тест несёт пометку «Ловит мутацию: …».

## Критерии приёмки
AC-1. Шаг `test_author`: в рабочем каталоге роли есть только
долгоживущий файл задачи (`tests/test_<префикс задачи>_<имя>.py`, новый
относительно базы ветки), каталога `tasks/<id>/acceptance_tests/` нет —
шаг сдан (обязательный артефакт не считается отсутствующим).

AC-2. Шаг `test_author`: в рабочем каталоге роли есть только файл
`tests/test_<чужой префикс>_x.py` или `tests/test_other.py`, каталога
`tasks/<id>/acceptance_tests/` нет — файл не засчитывается, шаг получает
отказ «шаг завершён без артефакта …».

AC-3. Шаг `test_author`: в рабочем каталоге роли есть только файл под
`tasks/<id>/acceptance_tests/` — шаг сдан, как раньше.

AC-4. Шаг `test_author`: нет ни файла под `tasks/<id>/acceptance_tests/`,
ни долгоживущего файла задачи — отказ «шаг завершён без артефакта …»,
текст которого называет обе ожидаемые формы (`acceptance_tests/` и
долгоживущий файл `tests/test_<префикс задачи>_<имя>.py`).

AC-5. Проверка обязательного артефакта ролей `analyst`, `developer`,
`reviewer` не изменилась: при наличии своего артефакта
(`SPEC.md`/`QUESTIONS.md`, `PLAN.md`, `REVIEW.md`) шаг сдан, при
отсутствии — прежний отказ с прежним именем артефакта.

## Оценка объёма и деление
Прогноз диффа: 6 КиБ.

Сработавший сигнал: зона `orchestrator/runner.py` задевает механизм, на
который опирается запись в `docs/invariants.md`. Прочие сигналы не
срабатывают: 3 файла зоны, 5 критериев, `budget_usd` $25.

Обоснование монолита: изменение — одна ветка `test_author` функции
`_missing_required_artifact` плюс её тесты; резать нечего — тесты без
правки условия красны (AC-1, AC-4), правка без тестов нарушает
требование 4 ТЗ, а `docs/codebase-map.md` — производная той же правки.
Инвариантный механизм затрагивается только расширением условия «шаг
сдан» для одной роли; поведение остальных ролей фиксирует AC-5.

## Не входит
- Изменение момента записи перечня `acceptance_tests/long_lived.sha256.txt`.
- Правка `skills/test-authoring.md`.
- Пересмотр числа и механики попыток шага.
- Изменения в `scripts/guard.py`, `orchestrator/checkpoint.py`,
  `orchestrator/advance_gates/`, `orchestrator/fsm_advance.py`, остальных
  файлах `tests/` (включая `tests/test_invariants.py`), `skills/`,
  `docs/adr/`, `docs/invariants.md`, `tasks/` — только чтение по ТЗ.
- Зелёный полный набор `tests/` и свежесть `docs/codebase-map.md` в CI —
  её держит пульт.

## Материалы
- ТЗ: `tasks/01M3Y8570H9Y57YTP3M7E1AMHG/TZ.md` (строка копилки 02.10, П1).
- `orchestrator/runner.py:996-1021` (`_missing_required_artifact`),
  `orchestrator/runner.py:1126` (вызов), `scripts/guard.py:1826`
  (`is_long_lived_test_path`), `orchestrator/checkpoint.py:232-270`
  (`_test_author_own_paths` — признак «свой долгоживущий файл»).
- Рамка ТЗ — $15; `budget_usd: 25` — нижняя планка класса по
  `skills/spec-authoring.md` («Планка не ниже $25 ни для одной задачи»).
