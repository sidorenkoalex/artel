---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0021, этап 1 (б1) — документы вне рабочей копии кода и доступ ролей

## Фаза A: план
- Таблица покрытия полна (требования 1–7 → шаги 1–7); шаги — единицы
  размера MR.
- Подход согласован с конвенциями: защищённые пути (инвариант 21,
  `tests/test_invariants.py`, `skills/`) идут приложениями; правка
  `docs/reference/role-home/claude/CLAUDE.md` покрыта ANSWER-2 п.3
  («Расширение зон разрешено»), раздел «Расширение зон» в PLAN есть.
- «Влияние на систему» соответствует diff: 32 файла stat-списка совпадают
  с перечнем PLAN; изменённые утверждения четырёх методов покрыты строкой
  мандата ANSWER-2 п.1; остальные правки `tests/` — пути фикстур/сидов
  (сверено по diff: утверждения не тронуты, кроме добавленного
  `assertFalse(docs_dir.exists())` в `test_step_autocommit`).
- Откат описан (revert merge-коммита).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artifact_branch.docs_root/docs_dir`, выкладка в `runner.role_cwd`, автокоммит из каталога документов (`checkpoint._commit_external_step_artifacts`); коммит только при изменении (`_same_as_ref`). |
| 2 | OK | claude — `--add-dir` до `--model`; codex — после `exec`, глобальные флаги до неё; cwd не изменён. Долгоживущий файл задачи зелёный. Версия 0.155.1 — по ANSWER-2 п.2 принята проверка на 0.157.1. |
| 3 | OK по коду | `plank_in_code_copy` (finally) в `advance_gates/acceptance`, `fsm_advance._review_approved` (внешний target), `amend`; `tests_writing` — `drop_from_code_copy` в finally; `pull` убирал и раньше. Сторожа в `tests/` — неполны, см. R1-F1. |
| 4 | OK | `_docs_ref_moved_past_pult`/`_record_step_fixation`: ссылка, сдвинутая ролью, не перефиксируется; лок и перечень сумм не ослаблены. Мутация «сторож снят» ловится `test_docs_dir_layout::RefMovedPastPultTest`. |
| 5 | OK | `docs/stack.md`: интерфейс `command(model, docs_dir)`, абзац «Каталог документов задачи», песочница codex, строка таблицы паритета — обе ячейки. |
| 6 | OK | Приложения 1–4 `git apply --check` — rc=0 у всех; с приложениями 1+2 `test_invariants.py` + `test_multitarget_invariants.py` — 78 passed. |
| 7 | Частично | Три из четырёх свойств имеют сторожа в `tests/`; «`acceptance_tests/` убирается после прогона при любом исходе» сторожится только на уровне контекст-менеджера, использование в гейтах держит лишь разовая планка (R1-F1). |

## Замечания

- **major** — `tests/test_docs_dir_layout.py:225-266` (класс `PlankInCodeCopyTest`) против `orchestrator/advance_gates/acceptance.py:241-248`, `orchestrator/fsm_advance.py:192-197`, `orchestrator/fsm_advance.py:413-418`, `orchestrator/amend.py:950` — SPEC требование 7 требует постоянного сторожа «`acceptance_tests/` убирается после прогона при любом исходе», а `tests/` проверяет только сам `acceptance.plank_in_code_copy`, не то, что гейты им пользуются. Проверено временной мутацией: в `_acceptance_run_body` оба `cleanup.enter_context(acceptance.plank_in_code_copy(...))` заменены прежним `acceptance.materialize_from_branch(...)` — `tests/test_docs_dir_layout.py`, `tests/test_acceptance_tests_flow.py`, `tests/test_long_lived_transitions.py` зелёные, красные только 3 теста планки `test_plank_only_during_run.py` (группа «разовый»; после мержа её не гоняет никто, ADR-0018 п.3). Последствие: регресс «гейт перестал убирать планку» после мержа пройдёт CI молча, и планка снова осядет в рабочей копии кода (AC-7..9). — Добавить в `tests/` сторожей на уровне вызова: прогон `_acceptance_run_refuses` зелёный/красный/исключение внутри прогона → `tasks/<id>/` в рабочей копии нет; то же для `tests_writing` (уборка в finally после сухого сбора, в т.ч. при отказе гейта), `_review_approved` внешнего target и `amend._check_code_head_long_lived`. Каждый — с заявкой «Ловит мутацию», проверенной временной мутацией.

- **major** — `orchestrator/checkpoint.py:993-1016` (`_merge_code_copy_docs`) — путь, который роль УДАЛИЛА в каталоге документов, но который остался в `tasks/<id>/` рабочей копии кода, воскрешается: `own = files.get(rel)` → `None`, условие `own is not None and …` ложно, `merged[rel] = content`; дальше `_step_artifact_deletion_candidates` не видит удаления (путь есть в `files`). Сценарий предсказуем, потому что его предписывает сама миссия (`role_prompt.docs_dir_note`: «скопируй планку в рабочий каталог … и прогони оттуда»): test_author копирует планку для прогона, затем переименовывает/удаляет файл планки в каталоге документов → в конце шага старое имя возвращается в ссылку; на `tests_writing` сухой сбор и трассируемость AC видят файл, которого роль уже нет, лишний тест попадает в лок. То же для developer, удалившего черновой файл документов. — Брать из рабочей копии кода только пути, которых нет ни в каталоге документов, ни в выкладке `baseline_sha` (т.е. действительно новые), либо пропускать путь, совпадающий байтами с выкладкой baseline (копия, а не правка); добавить сторож в `tests/test_docs_dir_layout.py` на сценарий «скопировал планку → удалил файл в каталоге документов → после автокоммита файла в ссылке нет».

- **minor** — `orchestrator/role_prompt.py:139-142` — миссия сначала говорит «запись вне него недоступна» (о рабочем каталоге), а следующим абзацем открывает каталог документов на запись. Противоречие внутри одного промпта; роль может отказаться писать по пути каталога документов. — Переформулировать первую строку при `docs_dir is not None` («запись вне него и вне каталога документов недоступна»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_docs_dir_layout.py:225; orchestrator/advance_gates/acceptance.py:241-248; orchestrator/fsm_advance.py:192-197, 413-418; orchestrator/amend.py:950 | Уборку планки гейтами после прогона сторожит только разовая планка; `tests/` проверяет лишь контекст-менеджер (мутация в `_acceptance_run_body` не краснит `tests/`) | Регресс уборки после мержа пройдёт CI, планка осядет в рабочей копии кода (SPEC треб. 7, AC-7..9) | Сторожа в `tests/` на уровне гейтов (зелёный/красный/исключение; tests_writing; review внешнего target; amend) с проверенными заявками мутации |
| R1-F2 | open | orchestrator/checkpoint.py:993-1016 | `_merge_code_copy_docs` воскрешает путь, удалённый ролью в каталоге документов, если его копия осталась в `tasks/<id>/` кода (копию планки велит делать миссия) | Удаление/переименование файла планки или документа молча отменяется, лишний файл уходит в ссылку и в лок | Брать из кода только действительно новые пути (нет в каталоге документов и в baseline) или пропускать копии, совпадающие с baseline; сторож в `tests/` |
| R1-F3 | open | orchestrator/role_prompt.py:139-142 | Миссия: «запись вне него недоступна» и тут же каталог документов открыт на запись | Роль может не писать в каталог документов, шаг без артефакта | Уточнить строку при `docs_dir` |

## Вердикт
changes_requested: R1-F1 (сторожа уборки планки на уровне гейтов в
`tests/`), R1-F2 (воскрешение удалённых документов из копии в коде).
R1-F3 — по желанию в той же итерации.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tasks/01M409YKM3QE5KVRGV0G94F5ZC/acceptance_tests tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py tests/test_docs_dir_layout.py tests/test_checkpoint_external_step_artifacts.py tests/test_step_autocommit.py tests/test_timeout_checkpoint.py tests/test_review_package.py tests/test_providers.py tests/test_providers_codex.py` — 318 passed, 100 subtests passed.
- Временная мутация (код возвращён, `git diff orchestrator/` пуст): `_docs_ref_moved_past_pult` → `return None` и `plank_in_code_copy` без `finally` — `tests/test_docs_dir_layout.py`: 2 failed (`RefMovedPastPultTest…`, `PlankInCodeCopyTest::test_plank_is_gone_after_an_exception_inside_the_block`) — заявки сторожей подтверждены.
- Временная мутация `_acceptance_run_body`: `plank_in_code_copy` → `materialize_from_branch` (оба места) — планка + `test_docs_dir_layout` + `test_acceptance_tests_flow` + `test_long_lived_transitions`: 3 failed, все в планке `test_plank_only_during_run.py`, `tests/` зелёные → R1-F1. Код возвращён.
- Приложения 1–4 PLAN извлечены и проверены `git apply --check` — rc=0 у всех четырёх.
- С приложениями 1 и 2: `tests/test_invariants.py tests/test_multitarget_invariants.py` — 78 passed, 215 subtests; затем `git checkout` обоих файлов, дерево чистое.
- Чтение `fsm_autogate._autogate_conditions` (зачем: проверить, не потерял ли автогейт self-target планку после выноса) — `acc_tdir` условием не используется, полный набор гоняется по `workspace.path`; дефекта нет. Чтение `pull._materialize_and_run_plank` — уборка в `finally` уже была.

## Предложения системе
- Планка задачи помечает свойства кода (уборка планки гейтами, AC-7..9) группой «разовый», и разработчик закрывает треб. 7 сторожем уровня хелпера — разрыв «сторож хелпера ≠ сторож вызова» стоит назвать в `skills/test-authoring.md` рядом с ADR-0018 п.3.
