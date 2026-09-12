---
task: 01M2A22CG2P0E69H00RDHFF3K4
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/canary.py, tests/
budget_usd: 30
---

# SPEC: канарейка читает SPEC из артефактной ветки: задача с AC-разметкой идёт в tests_writing, а не мимо test_author в in_dev

## Контекст
После ADR-0016 `tasks/<id>/` живёт только в артефактной ветке
`artifact/<id>` — ни на кодовой ветке `task/…`, ни на диске
`config.TASKS/<id>/SPEC.md` файла больше нет. `canary._spec_gate_next_state`
(orchestrator/canary.py:513–523) по-прежнему решает, откуда читать SPEC,
через `gitcmd.on_foreign_branch(t["branch"])` — на обеих ветках файла
нет, `yamlmini.frontmatter` получает пустой словарь, `guard.
requires_ac_markup({})` даёт `False`, и канареечная задача с
AC-разметкой в SPEC уходит `spec_gate -> in_dev`, минуя `tests_writing`
и роль test_author. `fsm._cmd_approve` для `spec_gate` (orchestrator/
fsm.py:684–692) читает SPEC корректно — через `artifact_source.
resolve(conn, task_id)` — и этот же приём нужно перенести в копию
ветки условий канарейки (`canary.py` намеренно не зовёт `cmd_approve`,
модульный докстринг). Прогон 20260911T230900Z (01M29BPKYG, $3.09) снят
по «3 прохода подряд без прогресса в in_dev» — прямое следствие
пропуска tests_writing.

Условие старта (вне контроля SPEC): зона `orchestrator/canary.py`
занята задачей 01M29284PT до её мержа — разработчик этой задачи ждёт
освобождения зоны штатным механизмом `zone_lock`.

## Требования
1. `canary._spec_gate_next_state` определяет источник SPEC через
   `artifact_source.resolve(conn, task_id)`, не через `gitcmd.
   on_foreign_branch(t["branch"])`: для foreign SPEC читается текстом с
   артефактной ветки; иначе — `artifacts.frontmatter(config.TASKS /
   task_id / "SPEC.md")` с диска (симметрично `fsm._cmd_approve` для
   `spec_gate`). `gitcmd.on_foreign_branch(t["branch"])` для чтения SPEC
   в этой функции больше не вызывается.
2. Если SPEC не найден ни в одном источнике (текст с артефактной ветки
   не прочитан), это не трактуется как «SPEC без AC-разметки»:
   `_pass_spec_gate` зовёт `_kill_inconclusive` с текстом «canary: SPEC
   не найден в источнике артефактов (<ветка>)» вместо перевода задачи в
   `in_dev`; прогон помечается red по этой причине.
3. Строка отчёта прогона канарейки («шагов=… исход=…») несёт признак,
   прошла ли задача состояние `tests_writing`: «test_author=да» либо
   «test_author=нет».
4. Существующие тесты `tests/test_canary.py` не ослабляются (не
   смягчаются, не удаляются).

## Критерии приёмки

AC-1. `_spec_gate_next_state` для задачи, чей SPEC (`schema_version: 2`,
с AC-разметкой в разделе «Критерии приёмки») лежит только в
артефактной ветке — не на кодовой ветке и не на диске
`config.TASKS/<id>/SPEC.md` — возвращает `"tests_writing"`.

AC-2. `_spec_gate_next_state` для задачи, чей SPEC на артефактной ветке
несёт `skip_tests: <причина>`, возвращает `"in_dev"`.

AC-3. Если SPEC не найден ни в одном источнике, `_pass_spec_gate` не
переводит задачу в `in_dev`: вызывается `_kill_inconclusive` с текстом
«canary: SPEC не найден в источнике артефактов (<ветка>)», причина
поимённо видна в журнале задачи.

AC-4. `_spec_gate_next_state` для чтения SPEC с артефактной ветки не
вызывает `gitcmd.on_foreign_branch(t["branch"])` — источник определяется
исключительно через `artifact_source.resolve(conn, task_id)`.

AC-5. Строка отчёта прогона канарейки («шагов=… исход=…») дополнена
признаком «test_author=да» — если в журнале задачи есть переход
«state -> tests_writing» — либо «test_author=нет», если такого перехода
нет.

AC-6. `tests/test_canary.py` содержит тест-регресс на AC-1: мутация,
возвращающая чтение SPEC на чтение с кодовой ветки (обратно к
`gitcmd.on_foreign_branch`), делает этот тест красным.

AC-7. `tests/test_canary.py` содержит тесты на AC-2, AC-3 и AC-5.

AC-8. Все тесты `tests/test_canary.py`, существовавшие до этой задачи,
проходят без правок в сторону смягчения (без удаления и без ослабления
проверяемых утверждений).

## Не входит
- Сдвиг пина и изменение порога `CANARY_MAX_MERGES_SINCE_GREEN`
  (`pin.cmd_pin_update`) — решение Оператора вне этой задачи.
- Правка `pin.py`.
- Синтетическое прохождение `tests_writing` канарейкой — стадия
  проходится по-настоящему ролью test_author, как и остальные роли.
- Правка `orchestrator/fsm.py` и `orchestrator/fsm_advance.py`.

## Материалы
- orchestrator/fsm.py, `_cmd_approve`/`_approve_spec_gate` для
  `spec_gate` (строки 681–732) — образец корректного чтения SPEC.
- orchestrator/artifact_source.py — резолвер ветки-источника
  `tasks/<id>/`.
- orchestrator/fsm_advance.py, `_missing_plank_refuses` (около строк
  1131–1145) — тот же приём чтения источника у гейта планки.
- orchestrator/fsm.py, `_read_branch_text_or_refuse` (строки 271–289) —
  общий узел чтения текста артефакта с ветки задачи; `canary.py` уже
  импортирует модуль `fsm` (см. `orchestrator/canary.py:92-94`), так что
  использование этого узла не заводит новый цикл импорта.
- `.artel/canary/20260911T230900Z/01M29BPKYG5841MGMPHZVPCBEP/steps.txt`
  — журнал красного прогона, из которого выведена задача.
- docs/backlog.md, строка П1 от 12.09 — источник задачи.
