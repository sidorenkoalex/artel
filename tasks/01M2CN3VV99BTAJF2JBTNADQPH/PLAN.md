---
task: 01M2CN3VV99BTAJF2JBTNADQPH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Рефакторинг R7: checkpoint.py — общий WIP-чекпоинт и фазы переноса артефактов

## Подход

Задача класса «рефакторинг» (skills/coding-standards.md, правила T015):
поведение не меняется, перенос кода дословный, дедупликация — только
байт-в-байт идентичных кусков. Один MR, один коммит кода (плюс
регенерация карты тем же коммитом).

Требование 1 (общий помощник трёх WIP-чекпоинтов): три тела
`commit_timeout_checkpoint`/`commit_abnormal_checkpoint`/
`commit_pause_now_checkpoint` были построчно одинаковы, различаясь
только текстом сообщения/действия журнала и флагом `timeout`. Введён
`_wip_checkpoint(conn, task_id, role, message, action, discard_action,
discard_detail, timeout)` (сигнатура — буквально по SPEC) — единственное
тело git-обвязки; три публичные функции стали тонкими обёртками,
собирающими свои уникальные строки и делегирующими помощнику.
Докстринги трёх публичных функций оставлены БЕЗ ИЗМЕНЕНИЙ (только
добавлена короткая финальная фраза-указатель на `_wip_checkpoint`) —
они продолжают существовать как публичные имена (AC-1), поэтому
исторический контекст (мандат `developer`, только догфуд, повторная
фиксация и т.д.) остаётся там же, где его ищет читатель; сам
`_wip_checkpoint` несёт компактный докстринг про то, чем именно
отличаются три вызова.

Требование 2 (пять фаз `_commit_external_step_artifacts`): функция
разбита на пять приватных функций-фаз с явными аргументами
(`files`, `existing`, `baseline_sha`, `own_commit_marker`, `task_id`),
без изменения сигнатуры/строки возврата/ранних `return ""`/порядка
записей журнала. Докстринг монолита (115 строк) распределён по фазам
без потери содержания — каждая фаза несёт объяснение своей части
(источник и обоснование фильтра `.gitignore`, критерий посторонних
файлов, конфликт-гвард, критерий удаления, push и журнал), сам
оркестратор несёт короткий обзор + список фаз с указателями.

`from . import alerts` / `from . import artifact_branch` — были
локальными импортами ВНУТРИ `_commit_external_step_artifacts` (не на
уровне модуля); перенесены КАЖДЫЙ в ту фазу, что реально использует
модуль (`alerts` — конфликт-гвард, `artifact_branch` — сбор
`branch_name` в оркестраторе и коммит в последней фазе), тот же приём
локального импорта, что и был — не поднято на уровень модуля (не
входит в задачу, ADR о причине локальности не пересматривается).

Бюджет SPEC ($35) не превышен, `budget_usd` не переоценивается.

## Шаги

1. `_wip_checkpoint` + тонкие `commit_timeout_checkpoint`/
   `commit_abnormal_checkpoint`/`commit_pause_now_checkpoint`
   (требование 1, AC-1).
2. Пять фаз `_commit_external_step_artifacts` + сама функция как
   тонкий оркестратор (требование 2, AC-2).
3. Регенерация `docs/codebase-map.md` (conventions-core — правка `*.py`
   в `orchestrator/`). Публичный API `checkpoint.py` не изменился
   (все новые имена приватные), правка карты — только `built_at_sha`.
4. Прогон полного набора `tests/` + смоук до/после (требования 3-4,
   AC-3/AC-4) — см. «Влияние на систему».

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (общий помощник `_wip_checkpoint`) | 1 |
| 2 (пять фаз `_commit_external_step_artifacts`) | 2 |
| 3 (поведение не меняется) | 4 |
| 4 (существующие тесты без правки сценариев/ассертов) | 4 |
| 5 (`fsm_advance.py` не правится) | 1, 2 (не тронут — см. «Влияние на систему») |

## Таблица переносов

Координаты — строки исходного `orchestrator/checkpoint.py` ДО этой
задачи (коммит `812c9064`, тот же файл, что цитирует SPEC).

| Символ/фрагмент | Откуда (строки) | Куда |
|---|---|---|
| Тело `commit_timeout_checkpoint` (после докстринга) | :159–183 | `_wip_checkpoint` (общее тело) + вызов из тонкой `commit_timeout_checkpoint` |
| Тело `commit_abnormal_checkpoint` (после докстринга) | :319–342 | `_wip_checkpoint` + вызов из тонкой `commit_abnormal_checkpoint` |
| Тело `commit_pause_now_checkpoint` (после докстринга) | :375–398 | `_wip_checkpoint` + вызов из тонкой `commit_pause_now_checkpoint` |
| Сбор файлов `task_dir` с диска + фильтр `.gitignore` | :658–666, :673(частично)–703 | `_collect_step_artifact_files` (фаза 1/5) |
| Журнал посторонних файлов `acceptance_tests/` и корня `tasks/<id>/` | :689(частично)–735 | `_journal_stray_step_artifacts` (фаза 2/5) |
| Конфликт-гвард против `baseline_sha` | :739–761 | `_apply_artifact_conflict_guard` (фаза 3/5) |
| Кандидаты на удаление по `own_commit_marker` | :763–785 | `_step_artifact_deletion_candidates` (фаза 4/5) |
| Коммит в артефактную ветку + push + журнал + фиксация | :787–801 | `_commit_step_artifacts_to_branch` (фаза 5/5) |
| `branch`/`own_commit_marker`/`message`/`existing` (общая подготовка) | :667–668, :684–688 | Остаётся в оркестраторе `_commit_external_step_artifacts` (аргументы фаз) |
| Ранний `return ""` — `ignored is None` | :679–684 | Сохранён: `_collect_step_artifact_files` возвращает `None`, оркестратор делает `return ""` на этом же месте по смыслу |
| Ранние `return ""` — `not files and not removed` / `not commit_sha` | :771–776 | Сохранены буквально внутри `_commit_step_artifacts_to_branch`, чьё возвращаемое значение оркестратор отдаёт как своё |

`_discard_out_of_mandate_changes` (:186–279), конфликт-гвард,
критерий удаления файлов, фильтр посторонних файлов — код тела не
менялся ни на символ, только переехал в новые функции без правок
(требование «не входит»).

## Влияние на систему

- **`orchestrator/fsm_advance.py`.** Не тронут (AC-5). `fsm_advance.
  tests_writing` (:459) сверяет действие журнала
  `checkpoint.STRAY_ACCEPTANCE_FILES_ACTION` и режет detail по
  `checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX` — оба имени и
  порядок вызова `store.journal` с ними не изменились (фаза 2
  `_journal_stray_step_artifacts` журналит их в том же порядке, что и
  монолит).
- **Публичный API `checkpoint.py`.** Все 7 публичных функций
  (`commit_timeout_checkpoint`, `commit_abnormal_checkpoint`,
  `commit_pause_now_checkpoint`, `commit_pull_checkpoint`,
  `commit_step_artifacts`, `commit_success_checkpoint`,
  `task_dir_zone`) сохранили сигнатуры — `docs/codebase-map.md` после
  регенерации отличается только `built_at_sha`, список публичных
  функций не изменился.
- **Тесты.** Ни один сценарий/ассерт `tests/test_timeout_checkpoint.py`,
  `tests/test_checkpoint_external_step_artifacts.py`,
  `tests/test_pause_now.py`, `tests/test_step_autocommit.py`,
  `tests/test_checkpoint_zone_filter.py` не менялся (диффа в `tests/`
  вообще нет — импорты и патчи уже адресовали публичные имена, которые
  не переехали). Прогон (см. ниже) зелёный.
- **`tests/test_pause_now.py:61`.** Патчит `checkpoint.
  commit_pause_now_checkpoint` — имя осталось публичным и вызываемым
  той же сигнатурой, патч не задет.
- **Откат.** Revert одного merge-коммита этой задачи в main — `checkpoint.py`
  и `docs/codebase-map.md` возвращаются к состоянию `812c9064`, тесты и
  остальной оркестратор не заметят разницы (публичный контракт не
  менялся ни на одном шаге).

## Смоук до/после (AC-4)

**Ограничение окружения.** Инвариант T056
(`orchestrator/artel.py::_refuse_if_worktree`) не даёт прогнать
`artel.py status/report/doctor` через `main()` из git-worktree роли —
тот же класс ограничения, что документирован в `tasks/T091/PLAN.md`
(«Смоук до/после», раздел «Предложения системе»). Метод —
идентичный T091: команды вызваны напрямую как функции
(`catalog.cmd_status`, `catalog.cmd_log`, `orchestrator.doctor.cli.
cmd_doctor`, `orchestrator.report.cmd_report`) на синтетической, но
реалистичной `state.db` (`tests.sandbox.RealGitSandbox` + 3 задачи в
состояниях `in_dev`/`review`/`done` с записями журнала и расходом),
один раз с исходным `checkpoint.py` (`git stash`), один раз с
рефакторингом (`git stash pop`).

**Результат.** Вывод `status`/`log T001`/`log T002`/`log T003`/
`doctor`/`report`/`report.html` идентичен между «до» и «после» за
вычетом:
- меток времени журнала и `ppid` (реальные `store.now()`/pid процесса
  прогона, не код);
- `disk-space` (76030 vs 76029 МБ) — реальное изменение свободного
  места на диске машины между двумя прогонами;
- пути временного каталога песочницы (`tempfile.TemporaryDirectory()`
  создаёт новое имя на каждый прогон) — фигурирует в тексте одной
  `[FAIL] targets-yaml`-строки и в пути `report.html`.

Ни одного расхождения в логике/тексте, порождённого кодом
`checkpoint.py`, не найдено.

**Прогон тестов:**
- `tests/test_timeout_checkpoint.py tests/test_checkpoint_external_step_artifacts.py tests/test_pause_now.py tests/test_step_autocommit.py tests/test_checkpoint_zone_filter.py` — 84 passed.
- Соседние файлы, ссылающиеся на `checkpoint.*` (`test_artifact_materialization.py`,
  `test_checkpoint_stray_acceptance_files.py`,
  `test_fsm_advance_tests_writing_dry_collect.py`,
  `test_fsm_map_conflict_autoresolve.py`, `test_fsm_review_rework_gate.py`,
  `test_git_fixation.py`, `test_guard_task_root_subdirectory.py`,
  `test_pull.py`, `test_review_package.py`, `test_step_refixation.py`,
  `test_zones_gate.py`) — 222 passed, 19 subtests passed.
- Полный набор `tests/` в шаге не прогонялся (skills/coding-standards.md:
  «Полный набор `tests/` в шаге НЕ запускай») — CI прогонит его на пуш
  ветки.

## Риски

- Докстринг-реорганизация фазы 2 требования — читатель, привыкший
  искать весь контекст одним куском в `_commit_external_step_artifacts`,
  теперь находит его распределённым по пяти функциям; смягчено списком
  фаз-указателей в докстринге оркестратора.

## Предложения системе
