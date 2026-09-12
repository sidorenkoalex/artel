---
task: 01M2ARQRDV4YY9TVPHXN2E7136
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Сухой сбор планки на выходе tests_writing

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. `acceptance.collect(tdir, cwd)` | OK | `orchestrator/acceptance.py:114-161` — переиспользует `_pytest_command`, различает коды возврата 0/5/иное. Поведение эмпирически перепроверено (см. «Проверено исполнением»): RC=0 зелёная планка, RC=2 ImportError/SyntaxError, RC=5 планка без тестов — ровно то, что описывает докстринг и AC-1/AC-2/AC-3. |
| 2. Выход `tests_writing` делает сухой сбор после трассируемости AC, до `in_dev` | OK | `orchestrator/fsm_advance.py:550-558` — `_tests_writing_dry_collect_gate` вызван вторым гейтом, `store.set_state(..., "in_dev", ...)` — только после обоих гейтов (строка 559). |
| 3. Посторонние файлы планки `test_author` — отказ шага, не предупреждение | OK | `_tests_writing_stray_plank_files_gate` (fsm_advance.py:411-469) читает `store.task_steps`, фильтрует `actor == "lease"`, ищет визит от последней `state -> tests_writing`, блокирует, если запись `checkpoint.STRAY_ACCEPTANCE_FILES_ACTION` — последняя. Для прочих ролей поведение не тронуто (`checkpoint.py` — чистый вынос констант, строки детали идентичны прежним литералам). |
| 4. Unified diff к `skills/test-authoring.md` приложением к PLAN.md | OK | Приложен, `git apply --check` на чистом дереве ветки задачи — применяется без конфликтов (перепроверено самостоятельно, не только со слов PLAN). Сам файл не закоммичен — верно, защищённый путь. |
| 5. Тестовое покрытие пп.1-3 без ослабления существующих тестов | OK | Два новых файла `tests/test_acceptance_collect.py` (8 тестов), `tests/test_fsm_advance_tests_writing_dry_collect.py` (6 тестов) — все зелёные. Ни один существующий файл `tests/` не тронут (diff --stat подтверждает: только 2 новых файла в tests/). `tests_writing`/`checkpoint`/`acceptance` регрессионные наборы — зелёные (см. ниже). |

Критерии приёмки AC-1…AC-9, AC-12, AC-13 — покрыты и исполняемы (юнит-тесты
и собственная планка задачи, все зелёные). AC-10, AC-11, AC-14 законно
размечены `manual` в планке задачи
(`test_ac10_ac11_ac12_ac13_ac14_manual_markers.py`) — это не «свойство,
которое можно испытать этой планкой», а факт диффа/приложения, проверяемый
ревью кода; сами AC-11/AC-12/AC-13 продублированы исполняемыми тестами в
`tests/` (ci-covered) — легальный случай по конвенции задачи.

## Замечания

Замечаний, требующих правки кода, нет.

Единственное, что рассмотрено и сознательно не заведено как замечание:
`_tests_writing_acceptance_dir` (fsm_advance.py:471-489) — новая функция,
намеренно дублирующая (не рефакторящая, по прямому обоснованию PLAN
«Подход») уже покрытый тестами трёхветочный выбор каталога
`_acceptance_run_refuses`. Новые тесты этой задачи упражняют только
дефолтную ветку (`tdir`/`config.ROOT`, через `LightTransitionSandbox`) —
ветки «внешний target» и «self на своей ветке» отдельно не
пере-тестированы для этой конкретной функции. Риск низкий: обе ветки —
однострочные вызовы уже проверенных примитивов (`acceptance.
materialize_from_branch`, `workspace.on_task_branch`, `workspace.path`),
параметры прослежены вручную и совпадают с сигнатурой аналога построчно;
ниже по конвейеру (`in_dev -> verifying`) та же материализация всё равно
проходит через плотно покрытый `_acceptance_run_refuses`. Не поднимаю до
уровня «minor» в реестре — не блокирует и не заслуживает отдельной
итерации ради дублирующего теста тривиальной глины.

## Реестр замечаний

Пусто — замечаний, требующих отдельной записи и статуса, нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_acceptance_collect.py tests/test_fsm_advance_tests_writing_dry_collect.py -q` — 14 passed.
- `python3 -m pytest tests/test_acceptance.py tests/test_acceptance_tests_flow.py tests/test_checkpoint_stray_acceptance_files.py -q` — 91 passed, 19 subtests passed (регресс `acceptance`/`checkpoint` не задет).
- `python3 -m pytest tests/test_fsm_advance_gate_framework.py tests/test_fsm_advance_gate_smoke.py tests/test_capacity_gate.py tests/test_mutation_claim_gate.py tests/test_protected_paths_gate.py tests/test_zones_gate.py tests/test_review_registry_gate.py tests/test_advance_guard.py tests/test_auto_cycle.py -q` — 125 passed, 34 subtests passed (каркас `_run_gates` и стоп-кран T038/AC-6 не задеты).
- `python3 -m pytest tasks/01M2ARQRDV4YY9TVPHXN2E7136/acceptance_tests -q` — 15 passed: собственная планка задачи (AC-1…AC-9, AC-12, AC-13) исполняется и проходит целиком, не только со слов PLAN.
- Эмпирическая перепроверка контракта pytet exit-кодов (независимо от
  докстринга `collect()`, отдельным прогоном `subprocess.run` на
  синтетических планках): `ModuleNotFoundError` -> RC 2, планка без
  тестов -> RC 5, синтаксическая ошибка -> RC 2 — подтверждает
  различение AC-2/AC-3 корректно на текущей версии pytest в этом
  окружении.
- `git apply --check` unified diff `skills/test-authoring.md` (AC-10) из
  приложения PLAN.md на чистом дереве ветки задачи — применяется без
  конфликтов.
- `python3 scripts/codebase_map.py` (регенерация карты) — diff с версией
  из ветки задачи ограничен строкой `built_at_sha` (ожидаемо, инструкция
  «built_at_sha не читай как признак дефекта»); содержимое карты
  актуально, дерево возвращено в исходное состояние после проверки
  (`git checkout -- docs/codebase-map.md`).
- `git diff ... --stat -- skills/ templates/ gates.yaml roles.yaml .github/` — пусто, защищённые пути не тронуты.
- Ручная сверка `orchestrator/checkpoint.py`: вынос строк в константы
  `STRAY_ACCEPTANCE_FILES_ACTION`/`STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX`
  — байт-в-байт совпадает с прежними литералами, поведение не изменено.
- Ручная сверка порядка вызовов в `tests_writing()`
  (fsm_advance.py:511-561): гейт посторонних файлов (AC-8) — первым,
  гейт сухого сбора — вторым, `store.set_state(..., "in_dev", ...)` и
  последующий лок `tests_locked_sha` — только после обоих; `store.
  task_steps` подтверждён `ORDER BY id` (store.py:566-569), что делает
  корректным поиск «последней записи визита».

## Предложения системе

