---
task: 01M2A22CG2P0E69H00RDHFF3K4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: канарейка читает SPEC из артефактной ветки: задача с AC-разметкой идёт в tests_writing, а не мимо test_author в in_dev

## Подход
`canary._spec_gate_next_state` переведён на тот же резолвер источника,
что и `fsm._approve_spec_gate` для `spec_gate`: `artifact_source.
resolve(conn, task_id)` вместо `gitcmd.on_foreign_branch(t["branch"])`.
Ветка-источник сегодня всегда артефактная (`artifact_source.resolve`
безусловно возвращает `foreign=True`), но код сохраняет `if foreign/
else` симметрично `_approve_spec_gate` — как того явно требует SPEC
(требование 1: «симметрично `fsm._cmd_approve`»), а не схлопывает
условие в один путь.

Чтение текста SPEC.md с артефактной ветки переиспользует общий узел
`fsm._read_branch_text_or_refuse` (уже импортируемый `canary.py` модуль
`fsm`, как и указано в материалах SPEC) — он же журналирует и печатает
именованный отказ, если файл не читается («дерево не на ветке
задачи…»), и возвращает `None`.

`_spec_gate_next_state` теперь возвращает `str | None`: `None` — сигнал
«SPEC не найден ни в одном источнике» (требование 2), отличимый от
легитимного «SPEC есть, но без AC-разметки» (`"in_dev"`).
`_pass_spec_gate` при `None` не переводит задачу в `in_dev` — зовёт
`_kill_inconclusive` с текстом «canary: SPEC не найден в источнике
артефактов (<ветка>)» (AC-3), тем же путём, что и прочие «прогон дальше
не ведёт» этого модуля (стоп-предохранитель уже существовал для других
причин — `_last_role_skip_reason`, потолки эскалации/стагнации).

Признак `test_author=да/нет` строки отчёта — по факту записи `state ->
tests_writing` в журнале задачи (тот же приём устойчивости к подмене
`runner.cmd_run` в приёмочной песочнице, что уже несёт `_step_count`):
новая чистая функция `_test_author_visited(steps)`, включённая в
`_task_metrics` и в форматирование итоговой строки `_run_one_task`.

`gitcmd.on_foreign_branch` в `canary.py` для чтения SPEC больше не
вызывается нигде (требование 4/AC-4) — импорт `gitcmd` в файле остаётся:
он нужен другим функциям модуля (`_save_diagnostics`, `merges_since_
last_green_run` и т.д.), не только гейту SPEC.

**Правка по ANSWER-1** (возврат: планка красная —
`test_spec_gate_artifact_source.py:102,136,156` зовут
`_spec_gate_next_state(conn, task_id, t)` тремя позиционными). Первая
сдача убрала параметр `t` как «неиспользуемый» — залоченная приёмочная
планка (tasks/T023) зовёт функцию по фиксированной сигнатуре, и её
менять нельзя. Возвращён третий параметр `t` (не используется в теле —
источник по-прежнему определяется только через `artifact_source.
resolve`, AC-4); `_pass_spec_gate` сам получает `t` через `store.
get_task(conn, task_id)` и передаёт третьим позиционным. Оба места
вызова в `tests/test_canary.py` (`SpecGateArtifactSourceTest.
test_ac1_…`/`test_ac2_…`) поправлены на новую сигнатуру тем же приёмом.

## Шаги
1. `orchestrator/canary.py`: `_spec_gate_next_state` — резолвер
   источника через `artifact_source.resolve` + `fsm._read_branch_text_
   or_refuse`, возврат `str | None`; `_pass_spec_gate` — ветка `None` ->
   `_kill_inconclusive` с именованным текстом; новая `_test_author_
   visited(steps)`, включённая в `_task_metrics` и в строку отчёта
   `_run_one_task` («test_author=да/нет»). Регенерация `docs/
   codebase-map.md` тем же коммитом (новый импорт `artifact_source`).
2. `tests/test_canary.py`: `SpecGateArtifactSourceTest(RealGitSandbox)`
   — AC-1 (SPEC только на артефактной ветке -> `tests_writing`, тест
   одновременно ловит мутацию отката на `gitcmd.on_foreign_branch`,
   AC-6 — проверено вручную временным откатом кода, см. «Влияние на
   систему»), AC-2 (`skip_tests` на артефактной ветке -> `in_dev`), AC-3
   (SPEC не найден нигде -> `_kill_inconclusive`, не `in_dev`); AC-4—
   `mock.patch.object(canary.gitcmd, "on_foreign_branch")` +
   `assert_not_called()` внутри теста AC-1. `MetricsFromJournalTest` —
   два новых теста на `_test_author_visited`/`_task_metrics` (AC-5, «да»
   и «нет»).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 1, 2 |

## Влияние на систему
Зона задачи — `orchestrator/canary.py`, `tests/`, ровно как в SPEC.
`orchestrator/fsm.py`/`fsm_advance.py` не тронуты (запрещено «Не
входит»); `pin.py` не тронут. Существующие 67 тестов `tests/
test_canary.py` прогнаны без правок в сторону смягчения — все зелёные
(добавлено 5 новых, итого 72; ни один старый ассерт не ослаблен и не
удалён, AC-8). Приёмочная планка (`tasks/01M2A22CG2P0E69H00RDHFF3K4/
acceptance_tests/`) после правки по ANSWER-1 — все 6 тестов зелёные.
Регресс-свойство AC-6 проверено вручную: временный откат
`_spec_gate_next_state` на старую логику (`gitcmd.on_foreign_branch(t
["branch"])`) красит оба новых теста `test_ac1_…`/`test_ac3_…`
(результат `in_dev` вместо `tests_writing`, `cmd_kill` не позван) —
после отката правки тест снова зелёный. `docs/codebase-map.md`
регенерирован тем же коммитом (новый импорт `artifact_source` в
`canary.py`), CI-джоб свежести карты не покраснеет.

Откат — `git revert` этого коммита: `_spec_gate_next_state`/`_pass_
spec_gate` возвращаются к прежнему виду, строка отчёта — без признака
`test_author`.

## Риски
- `artifact_source.resolve` сегодня безусловно возвращает
  `foreign=True` — ветка `else` (диск) в `_spec_gate_next_state` не
  покрыта тестом (недостижима текущей реализацией резолвера), оставлена
  ради симметрии с `fsm._approve_spec_gate` и на случай будущего
  изменения резолвера — так же, как в образце.

## Предложения системе
(пусто)
